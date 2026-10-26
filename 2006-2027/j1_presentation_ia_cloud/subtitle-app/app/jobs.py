"""Job queue backed by the database (no extra broker to operate)."""

from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.domain import JobStatus, OutputType
from app.models import Job, Upload, Worker, utcnow

ACTIVE = (JobStatus.QUEUED.value, JobStatus.PROCESSING.value)


def create_job(
    session: Session,
    upload: Upload,
    output_type: OutputType,
    model: str,
    target_language: str | None = None,
    options: dict | None = None,
) -> Job:
    job = Job(
        upload_id=upload.id, output_type=output_type.value, model=model,
        target_language=target_language, options=options,
        # Corrections made on an earlier result of this file carry over.
        edited_segments=latest_edits(session, upload.id, model, target_language),
    )
    session.add(job)
    session.flush()
    session.refresh(job)
    return job


def claim_next(session: Session, max_duration_s: float | None = None) -> str | None:
    """Atomically move the oldest queued job to PROCESSING and return its id.

    With ``max_duration_s``, only media known to be at most that long are taken
    (fast lane for short files).
    """
    while True:
        query = (
            select(Job.id)
            .where(Job.status == JobStatus.QUEUED.value)
            .order_by(Job.created_at)
            .limit(1)
        )
        if max_duration_s is not None:
            query = query.join(Upload, Job.upload_id == Upload.id).where(
                Upload.duration_s <= max_duration_s
            )
        job_id = session.scalar(query)
        if job_id is None:
            return None
        now = utcnow()
        claimed = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.QUEUED.value)
            .values(
                status=JobStatus.PROCESSING.value,
                started_at=now,
                heartbeat_at=now,
                attempts=Job.attempts + 1,
                progress=0,
                stage=None,
            )
        )
        session.commit()
        if claimed.rowcount == 1:
            return job_id
        # Another worker won the race: try the next one.


def heartbeat(session: Session, job_id: str) -> None:
    session.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=utcnow()))


def set_progress(session: Session, job_id: str, stage: str, percent: int) -> bool:
    """Store the progress. False means the job is no longer running (cancelled)."""
    updated = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PROCESSING.value)
        .values(stage=stage, progress=percent)
    )
    return updated.rowcount == 1


# The two functions below only touch a job that is still PROCESSING: a job
# cancelled while its worker was finishing stays cancelled.

def mark_done(session: Session, job_id: str, compute_s: float, **result) -> bool:
    updated = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PROCESSING.value)
        .values(status=JobStatus.DONE.value, finished_at=utcnow(), compute_s=compute_s,
                error=None, stage=None, progress=100, **result)
    )
    return updated.rowcount == 1


def mark_failed(session: Session, job_id: str, error: str, compute_s: float | None = None) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PROCESSING.value)
        .values(status=JobStatus.FAILED.value, finished_at=utcnow(), compute_s=compute_s,
                error=error, stage=None)
    )


def cancel(session: Session, job_id: str) -> bool:
    """Cancel a waiting or running job; a running one stops at its next progress report."""
    updated = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(ACTIVE))
        .values(status=JobStatus.CANCELLED.value, finished_at=utcnow(), stage=None)
    )
    return updated.rowcount == 1


def requeue_with_edits(session: Session, job: Job, edited_segments: list[dict]) -> None:
    """Rebuild the files of a finished job from subtitles corrected by the visitor."""
    job.edited_segments = edited_segments
    job.status = JobStatus.QUEUED.value
    job.artifacts = []
    job.progress = 0
    job.stage = None
    job.finished_at = None


def latest_edits(session: Session, upload_id: str, model: str, target_language: str | None):
    """Corrections already made on this file for the same model and language, if any."""
    return session.scalar(
        select(Job.edited_segments)
        .where(
            Job.upload_id == upload_id,
            Job.model == model,
            Job.target_language.is_(target_language) if target_language is None
            else Job.target_language == target_language,
            Job.status == JobStatus.DONE.value,
            Job.edited_segments.is_not(None),
        )
        .order_by(Job.finished_at.desc())
        .limit(1)
    )


def requeue_stale(session: Session, stale_after_s: float, max_attempts: int) -> int:
    """Recover jobs whose worker died (no heartbeat). Returns how many were touched."""
    cutoff = utcnow() - timedelta(seconds=stale_after_s)
    stale = session.scalars(
        select(Job).where(Job.status == JobStatus.PROCESSING.value, Job.heartbeat_at < cutoff)
    ).all()
    for job in stale:
        job.stage = None
        job.progress = 0
        if job.attempts >= max_attempts:
            job.status = JobStatus.FAILED.value
            job.finished_at = utcnow()
            job.error = f"Traitement abandonné après {job.attempts} tentatives interrompues"
        else:
            job.status = JobStatus.QUEUED.value
    return len(stale)


def find_cached_transcript(session: Session, job: Job) -> Job | None:
    """A finished job for the same file and model: its transcription can be reused."""
    return session.scalar(
        select(Job)
        .where(
            Job.upload_id == job.upload_id,
            Job.model == job.model,
            Job.status == JobStatus.DONE.value,
            Job.segments.is_not(None),
        )
        .limit(1)
    )


def queue_position(session: Session, job: Job) -> int | None:
    if job.status != JobStatus.QUEUED.value:
        return None
    ahead = session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.status == JobStatus.QUEUED.value, Job.created_at < job.created_at)
    )
    return ahead + 1


def pending_media_s(session: Session) -> float:
    """Seconds of media still to process: whole files waiting, and what is left of running ones."""
    rows = session.execute(
        select(Job.status, Job.progress, Upload.duration_s)
        .join(Upload, Job.upload_id == Upload.id)
        .where(Job.status.in_(ACTIVE))
    )
    total = 0.0
    for status, progress, duration in rows:
        left = 1 - progress / 100 if status == JobStatus.PROCESSING.value else 1
        total += (duration or 0.0) * left
    return total


def pending_count(session: Session, owner_id: str) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Job)
        .join(Upload, Job.upload_id == Upload.id)
        .where(Job.status.in_(ACTIVE), Upload.owner_id == owner_id)
    )


def worker_heartbeat(session: Session, worker_id: str, device: str | None = None) -> None:
    worker = session.get(Worker, worker_id)
    if worker is None:
        session.add(Worker(id=worker_id, device=device))
    else:
        worker.heartbeat_at = utcnow()


def forget_workers(session: Session, host: str) -> None:
    """Drop the entries of a host: on clean stop, and at start to clear a crashed run."""
    session.execute(delete(Worker).where(Worker.id.startswith(f"{host}:", autoescape=True)))
