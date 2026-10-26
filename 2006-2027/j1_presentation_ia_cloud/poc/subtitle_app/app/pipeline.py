import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from app import media
from app.formats import RESULT_FILES, InputKind, OutputFormat
from app.store import JobStore
from app.subtitles import to_srt, to_text
from app.transcription.base import Transcriber

logger = logging.getLogger(__name__)


def _write(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(content)


class Pipeline:
    """video/audio -> transcription -> requested output."""

    def __init__(self, store: JobStore, get_transcriber: Callable[[], Transcriber]):
        self._store = store
        self._get_transcriber = get_transcriber

    def run(self, job_id: str) -> None:
        job = self._store.get(job_id)
        self._store.mark_processing(job_id)
        started = time.monotonic()
        try:
            input_path = Path(job["input_path"])
            workdir = input_path.parent
            output_format = OutputFormat(job["output_format"])
            is_video = InputKind(job["input_kind"]) is InputKind.VIDEO

            media_seconds = media.probe_duration(input_path)
            if is_video:
                audio_path = workdir / "audio.wav"
                media.extract_audio(input_path, audio_path)
            else:
                audio_path = input_path

            segments = self._get_transcriber().transcribe(audio_path)
            srt_text, plain_text = to_srt(segments), to_text(segments)
            srt_path = workdir / "subtitles.srt"
            _write(srt_path, srt_text)

            result_path = workdir / RESULT_FILES[output_format][0]
            if output_format is OutputFormat.SUBTITLES:
                _write(result_path, srt_text)
            elif output_format is OutputFormat.TEXT:
                _write(result_path, plain_text)
            elif output_format is OutputFormat.VIDEO_WITH_TRACK:
                media.add_subtitle_track(input_path, srt_path, result_path)
            else:
                media.burn_subtitles(input_path, srt_path, result_path)

            self._store.mark_done(job_id, result_path, plain_text, media_seconds,
                                  time.monotonic() - started)
        except Exception as exc:  # a failing job must never kill the worker
            logger.exception("Job %s failed", job_id)
            self._store.mark_failed(job_id, str(exc))


class JobRunner:
    """Runs jobs in background threads. Keep workers=1 on a single GPU."""

    def __init__(self, pipeline: Pipeline, workers: int):
        self._pipeline = pipeline
        self._executor = ThreadPoolExecutor(max_workers=workers)

    def submit(self, job_id: str) -> None:
        self._executor.submit(self._pipeline.run, job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
