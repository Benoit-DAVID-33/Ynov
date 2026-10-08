"""Turns an uploaded file into the artifacts of the requested output type."""

import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app import media, subtitles
from app.config import Settings
from app.domain import MediaKind, OutputType, Segment
from app.models import Job
from app.transcription import get_speaker_identifier, get_transcriber
from app.translation import get_translator, translate_segments

# Serialises the models that cannot run several inferences at once.
_inference_lock = threading.Lock()

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
    ".txt": "text/plain; charset=utf-8",
    ".zip": "application/zip",
}

# Relative cost of the steps, to turn their own progress into a job percentage.
_WEIGHTS = {"transcription": 10.0, "translation": 1.0, "video": 4.0}

# (stage, fraction of the whole job done)
ProgressReport = Callable[[str, float], None]


@dataclass
class JobResult:
    language: str
    segments: list[Segment]
    translated_segments: list[Segment] | None
    text: str
    artifacts: list[dict]


class _Progress:
    """Maps the progress of each step onto the progress of the whole job."""

    def __init__(self, stages: list[str], report: ProgressReport):
        self._total = sum(_WEIGHTS[s] for s in stages) or 1.0
        self._done = 0.0
        self._report = report

    def step(self, stage: str) -> Callable[[float], None]:
        base, weight = self._done, _WEIGHTS[stage]
        self._done += weight

        def update(fraction: float) -> None:
            fraction = min(max(fraction, 0.0), 1.0)
            self._report(stage, (base + fraction * weight) / self._total)

        update(0.0)
        return update


def delivered_language(target: str | None, source: str) -> str:
    """Language of what the visitor receives: the translation target, if any."""
    return target or source


def _transcribe(job: Job, workdir: Path, settings: Settings, on_progress) -> tuple[str, list[Segment]]:
    source = Path(job.upload.path)
    audio = workdir / "audio.wav"
    media.extract_audio(source, audio)
    try:
        transcriber = get_transcriber(job.model)
        if transcriber.thread_safe:
            result = transcriber.transcribe(audio, on_progress)
        else:
            with _inference_lock:
                result = transcriber.transcribe(audio, on_progress)
        segments = result.segments
        if settings.speaker_identifier:
            with _inference_lock:
                identifier = get_speaker_identifier(settings.speaker_identifier)
                segments = identifier.identify(audio, segments)
    finally:
        audio.unlink(missing_ok=True)
    return result.language, segments


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def _build_artifacts(
    job: Job, language: str, segments: list[Segment], workdir: Path, settings: Settings,
    progress: _Progress,
) -> list[Path]:
    """Create the result files. The first one is the primary download."""
    output_type = OutputType(job.output_type)
    source = Path(job.upload.path)

    if output_type is OutputType.TEXT:
        return [_write(workdir / "transcript.txt", subtitles.to_text(segments))]

    style = (job.options or {}).get("subtitle_style")
    # Bigger burned-in text fits fewer characters per line.
    max_chars = media.LINE_CHARS[style["size"]] if style else subtitles.MAX_LINE_CHARS
    srt = _write(workdir / "subtitles.srt", subtitles.to_srt(segments, max_chars))
    vtt = _write(workdir / "subtitles.vtt", subtitles.to_vtt(segments, max_chars))

    if output_type is OutputType.SUBTITLES:
        return [srt, vtt]

    if job.upload.kind != MediaKind.VIDEO.value:
        raise ValueError(f"Sortie {output_type.value} impossible pour un fichier audio")

    video = workdir / "video.mp4"
    if output_type is OutputType.VIDEO_EMBEDDED:
        media.burn_subtitles(
            source, srt, video,
            style=style,
            preset=settings.burn_preset,
            duration_s=job.upload.duration_s,
            on_progress=progress.step("video"),
        )
        return [video]

    media.mux_subtitles(source, srt, video, language=language, title=srt.name)
    bundle = workdir / "bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_STORED) as archive:
        archive.write(video, video.name)
        archive.write(srt, srt.name)
    return [bundle, video, srt, vtt]


def run_job(
    job: Job,
    cached: Job | None,
    settings: Settings,
    report: ProgressReport = lambda stage, fraction: None,
) -> JobResult:
    """``cached`` is a finished job whose transcription can be reused, if any."""
    workdir = settings.results_dir / job.id
    workdir.mkdir(parents=True, exist_ok=True)

    # A job being rebuilt after a correction already holds its transcription.
    own = job.segments is not None
    edited = job.edited_segments is not None
    stages = [
        *(["transcription"] if cached is None and not own else []),
        *(["translation"] if job.target_language and not edited else []),
        *(["video"] if job.output_type == OutputType.VIDEO_EMBEDDED.value else []),
    ]
    progress = _Progress(stages, report)

    if own:
        language = job.language
        segments = [Segment.from_dict(s) for s in job.segments]
    elif cached is not None:
        language = cached.language
        segments = [Segment.from_dict(s) for s in cached.segments]
    else:
        language, segments = _transcribe(job, workdir, settings, progress.step("transcription"))

    translated = None
    if edited:
        # Corrections are made on the delivered text: nothing to translate again.
        delivered = [Segment.from_dict(s) for s in job.edited_segments]
        if job.translated_segments is not None:
            translated = [Segment.from_dict(s) for s in job.translated_segments]
    else:
        if job.target_language and job.target_language != language:
            translator = get_translator(language, job.target_language)
            translated = translate_segments(
                segments, translator.translate, progress.step("translation")
            )
        delivered = translated if translated is not None else segments

    files = _build_artifacts(
        job, delivered_language(job.target_language, language), delivered, workdir, settings,
        progress,
    )
    artifacts = [
        {"name": f.name, "media_type": MEDIA_TYPES[f.suffix], "primary": index == 0}
        for index, f in enumerate(files)
    ]
    return JobResult(language, segments, translated, subtitles.to_text(delivered), artifacts)
