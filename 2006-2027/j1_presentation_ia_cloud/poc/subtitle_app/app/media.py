"""Thin wrappers around the ffmpeg / ffprobe binaries (must be installed)."""
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        raise MediaError(f"'{cmd[0]}' not found: install ffmpeg and make sure it is on the PATH") from None
    if result.returncode != 0:
        raise MediaError(f"{cmd[0]} failed: {result.stderr.strip()[-500:]}")
    return result.stdout


def probe_duration(path: Path) -> float:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    )
    return float(out.strip())


def extract_audio(video: Path, wav: Path) -> None:
    """16 kHz mono wav, the format expected by Whisper."""
    _run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)])


def add_subtitle_track(video: Path, srt: Path, output: Path) -> None:
    """Keep the video untouched and store the subtitles as a selectable track."""
    _run(
        ["ffmpeg", "-y", "-i", str(video), "-i", str(srt),
         "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=und",
         str(output)]
    )


def burn_subtitles(video: Path, srt: Path, output: Path) -> None:
    """Hard-code the subtitles in the picture."""
    # Run from the srt folder and pass a bare file name: avoids ffmpeg filter escaping issues.
    _run(
        ["ffmpeg", "-y", "-i", str(video.resolve()), "-vf", f"subtitles={srt.name}",
         str(output.resolve())],
        cwd=srt.parent,
    )
