"""Worker process: `python -m app.worker`."""

import logging
import os
import shutil
import signal
import socket
import threading
import time

from app import auth, jobs, pipeline, retention
from app.config import Settings, get_settings
from app.db import init_db, session_scope
from app.device import compute_type, resolve_device
from app.logs import setup_logging
from app.models import Job
from app.transcription import get_transcriber

log = logging.getLogger("worker")

_PROGRESS_MIN_INTERVAL_S = 0.5


class _Heartbeat:
    """Keeps a job marked alive while it is being processed."""

    def __init__(self, job_id: str, interval_s: float):
        self._job_id = job_id
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                with session_scope() as session:
                    jobs.heartbeat(session, self._job_id)
            except Exception:
                log.exception("heartbeat failed for job %s", self._job_id)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


class JobCancelled(Exception):
    pass


class _ProgressWriter:
    """Stores the job progress, at most a couple of times per second.

    Writing the progress is also how a running job learns it was cancelled.
    """

    def __init__(self, job_id: str):
        self._job_id = job_id
        self._stage = None
        self._written_at = 0.0

    def __call__(self, stage: str, fraction: float) -> None:
        now = time.monotonic()
        if stage == self._stage and now - self._written_at < _PROGRESS_MIN_INTERVAL_S:
            return
        self._stage, self._written_at = stage, now
        try:
            with session_scope() as session:
                still_running = jobs.set_progress(session, self._job_id, stage, int(fraction * 100))
        except Exception:
            # Progress is cosmetic: never fail a job because of it.
            log.warning("could not store progress of job %s", self._job_id, exc_info=True)
            return
        if not still_running:
            raise JobCancelled


def process_next(settings: Settings, max_duration_s: float | None = None) -> bool:
    """Process one queued job. Returns False when there is none to take."""
    with session_scope() as session:
        job_id = jobs.claim_next(session, max_duration_s)
    if job_id is None:
        return False

    started = time.perf_counter()
    try:
        # Short-lived session: no transaction stays open during the inference.
        with session_scope() as session:
            job = session.get(Job, job_id)
            cached = jobs.find_cached_transcript(session, job)
        log.info("job %s started (%s, %s, %s)", job_id, job.upload.filename, job.output_type, job.model)
        with _Heartbeat(job_id, settings.heartbeat_interval_s):
            result = pipeline.run_job(job, cached, settings, _ProgressWriter(job_id))
    except JobCancelled:
        log.info("job %s cancelled", job_id)
        shutil.rmtree(settings.results_dir / job_id, ignore_errors=True)
        return True
    except Exception as exc:
        log.exception("job %s failed", job_id)
        with session_scope() as session:
            jobs.mark_failed(session, job_id, str(exc) or type(exc).__name__,
                             time.perf_counter() - started)
        return True

    # A job rebuilt after a correction adds to the time already spent on it.
    compute_s = time.perf_counter() - started + (job.compute_s or 0.0)
    with session_scope() as session:
        completed = jobs.mark_done(
            session, job_id, compute_s,
            language=result.language,
            segments=[s.to_dict() for s in result.segments],
            translated_segments=(
                [s.to_dict() for s in result.translated_segments]
                if result.translated_segments is not None else None
            ),
            text=result.text,
            artifacts=result.artifacts,
        )
    if not completed:  # cancelled during the very last step
        log.info("job %s cancelled", job_id)
        shutil.rmtree(settings.results_dir / job_id, ignore_errors=True)
        return True
    log.info("job %s done in %.1fs", job_id, compute_s)
    return True


def _loop(settings: Settings, stop: threading.Event, max_duration_s: float | None) -> None:
    while not stop.is_set():
        try:
            if not process_next(settings, max_duration_s):
                stop.wait(settings.poll_interval_s)
        except Exception:
            log.exception("worker loop error")
            stop.wait(settings.poll_interval_s)


def main() -> None:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    worker_id = f"{host}:{os.getpid()}"
    setup_logging(f"worker-{host}", settings)
    init_db(settings.database_url)
    with session_scope() as session:
        jobs.forget_workers(session, host)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    try:
        device = resolve_device(settings)
    except RuntimeError as exc:
        # GPU explicitly requested but unusable: stop rather than run slowly on CPU.
        log.error("%s", exc)
        raise SystemExit(1) from exc
    log.info("device: %s (%s), default model: %s", device, compute_type(device),
             settings.effective_default_model)

    try:
        # Load the default model up front so the first job is not slowed down.
        get_transcriber(settings.effective_default_model)
    except Exception:
        log.exception("could not preload model %s", settings.effective_default_model)

    # The first slots form the fast lane: they only take short media, so a
    # short file never waits behind long ones. The others take anything.
    fast = min(settings.fast_lane_slots, settings.worker_concurrency - 1)
    threads = [
        threading.Thread(
            target=_loop,
            args=(settings, stop, settings.fast_lane_max_s if i < fast else None),
            name=f"worker-{i}",
        )
        for i in range(settings.worker_concurrency)
    ]
    for thread in threads:
        thread.start()
    log.info("worker %s ready (%d slots, %d reserved for media under %ds)",
             worker_id, len(threads), max(fast, 0), settings.fast_lane_max_s)

    while not stop.is_set():
        try:
            with session_scope() as session:
                jobs.worker_heartbeat(session, worker_id, device)
                recovered = jobs.requeue_stale(session, settings.stale_after_s, settings.max_attempts)
                retention.purge(session, settings)
                auth.purge_expired_sessions(session)
            if recovered:
                log.warning("recovered %d interrupted job(s)", recovered)
        except Exception:
            log.exception("worker housekeeping failed")
        stop.wait(settings.heartbeat_interval_s)

    log.info("stopping: waiting for running jobs")
    for thread in threads:
        thread.join()
    with session_scope() as session:
        jobs.forget_workers(session, host)


if __name__ == "__main__":
    main()
