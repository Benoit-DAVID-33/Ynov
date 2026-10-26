"""Thin wrappers around the ffmpeg / ffprobe binaries."""

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

_ISO_639_2 = {"en": "eng", "fr": "fra", "es": "spa", "de": "deu", "it": "ita"}

# libass font sizes for burned-in subtitles (its default is 16).
FONT_SIZES = {"small": 13, "medium": 18, "large": 26}
# Characters that fit on one line at each size, on a 16:9 picture.
LINE_CHARS = {"small": 42, "medium": 42, "large": 32}


class MediaError(RuntimeError):
    pass


def _fail(args: list[str], stderr: str) -> MediaError:
    tail = "\n".join(stderr.strip().splitlines()[-5:])
    return MediaError(f"{args[0]} a échoué : {tail}")


def _missing(args: list[str]) -> MediaError:
    return MediaError(f"{args[0]} introuvable : ffmpeg doit être installé")


def _run(args: list[str], cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, errors="replace")
    except FileNotFoundError as exc:
        raise _missing(args) from exc
    if proc.returncode != 0:
        raise _fail(args, proc.stderr)
    return proc.stdout


def _run_ffmpeg_with_progress(
    args: list[str], duration_s: float | None, on_progress: Callable[[float], None],
    cwd: Path | None = None,
) -> None:
    """Run ffmpeg and report the fraction of ``duration_s`` already written."""
    args = [*args[:-1], "-progress", "pipe:1", "-nostats", args[-1]]
    with tempfile.TemporaryFile() as stderr:
        try:
            proc = subprocess.Popen(
                args, cwd=cwd, stdout=subprocess.PIPE, stderr=stderr, text=True, errors="replace"
            )
        except FileNotFoundError as exc:
            raise _missing(args) from exc
        try:
            for line in proc.stdout:
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and value.isdigit() and duration_s:
                    on_progress(min(int(value) / 1e6 / duration_s, 1.0))
        except BaseException:
            # The callback aborted the job (cancellation): do not leave ffmpeg running.
            proc.kill()
            proc.wait()
            raise
        if proc.wait() != 0:
            stderr.seek(0)
            raise _fail(args, stderr.read().decode(errors="replace"))


def probe_duration(path: Path) -> float | None:
    """Duration in seconds, or None when it cannot be determined."""
    try:
        out = _run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)]
        )
        return float(out.strip())
    except (MediaError, ValueError):
        return None


def extract_audio(source: Path, dest: Path) -> None:
    """16 kHz mono wav, the input format expected by Whisper."""
    _run(["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
          "-c:a", "pcm_s16le", str(dest)])


def _force_style(style: dict | None) -> str:
    """libass style override from {"size": small|medium|large, "color": "#RRGGBB"}."""
    if not style:
        return ""
    red, green, blue = (style["color"][i:i + 2] for i in (1, 3, 5))
    size = FONT_SIZES[style["size"]]
    return f":force_style='FontSize={size},PrimaryColour=&H00{blue}{green}{red}'"


def burn_subtitles(
    video: Path,
    srt: Path,
    dest: Path,
    style: dict | None = None,
    preset: str = "superfast",
    duration_s: float | None = None,
    on_progress: Callable[[float], None] = lambda fraction: None,
) -> None:
    # Run from the srt directory: the subtitles filter has painful escaping
    # rules for absolute paths (drive letters, colons).
    _run_ffmpeg_with_progress(
        ["ffmpeg", "-y", "-i", str(video.resolve()),
         "-vf", f"subtitles={srt.name}{_force_style(style)}",
         "-c:v", "libx264", "-preset", preset, "-crf", "23", "-c:a", "copy",
         str(dest.resolve())],
        duration_s,
        on_progress,
        cwd=srt.parent,
    )


def mux_subtitles(video: Path, srt: Path, dest: Path, language: str, title: str) -> None:
    """Add the subtitles as a selectable track, without re-encoding the video."""
    _run(
        ["ffmpeg", "-y", "-i", str(video), "-i", str(srt),
         "-map", "0:v", "-map", "0:a?", "-map", "1:0",
         "-c", "copy", "-c:s", "mov_text",
         # mp4 only stores ISO 639-2 codes, and the track name in handler_name.
         "-metadata:s:s:0", f"language={_ISO_639_2.get(language, 'und')}",
         "-metadata:s:s:0", f"handler_name={title}",
         "-metadata:s:s:0", f"title={title}",
         str(dest)]
    )
