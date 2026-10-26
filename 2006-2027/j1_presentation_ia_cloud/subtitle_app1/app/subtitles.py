from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None  # filled by models able to identify speakers


def format_srt_time(seconds: float) -> str:
    total_ms = round(max(seconds, 0) * 1000)
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def to_srt(segments: list[Segment]) -> str:
    blocks = []
    for i, seg in enumerate(segments, start=1):
        text = f"[{seg.speaker}] {seg.text}" if seg.speaker else seg.text
        blocks.append(
            f"{i}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{text.strip()}\n"
        )
    return "\n".join(blocks)


def to_text(segments: list[Segment]) -> str:
    return " ".join(seg.text.strip() for seg in segments if seg.text.strip())
