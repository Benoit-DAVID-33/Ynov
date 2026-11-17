from app import text as words
from app.domain import Segment

# Usual subtitling guideline: at most two lines of about 42 characters (21 for
# Chinese, whose characters are twice as wide).
MAX_LINE_CHARS = 42
MAX_LINES = 2


def _timestamp(seconds: float, separator: str) -> str:
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{ms:03d}"


def _line(segment: Segment) -> str:
    text = words.join(words.tokens(segment.text))
    return f"[{segment.speaker}] {text}" if segment.speaker and text else text


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap; a single word longer than the limit keeps its own line."""
    lines, current = [], ""
    for word in words.tokens(text):
        candidate = words.join([current, word]) if current else word
        if current and words.width(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _balance(first: str, second: str, max_chars: int) -> list[str]:
    """Two lines of similar length read better than a full line and an orphan word."""
    parts = words.tokens(f"{first} {second}")
    best = (first, second)

    def gap(a: str, b: str) -> int:
        return abs(words.width(a) - words.width(b))

    for cut in range(1, len(parts)):
        a, b = words.join(parts[:cut]), words.join(parts[cut:])
        if max(words.width(a), words.width(b)) <= max_chars and gap(a, b) < gap(*best):
            best = (a, b)
    return list(best)


def layout(segments: list[Segment], max_chars: int = MAX_LINE_CHARS) -> list[tuple[float, float, str]]:
    """Turn segments into display cues (start, end, text) of at most MAX_LINES lines.

    A segment too long for one cue is split into several, its time shared in
    proportion to the text of each.
    """
    cues = []
    for segment in segments:
        lines = _wrap(_line(segment), max_chars)
        if not lines:
            continue
        groups = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
        total = sum(words.width(line) for line in lines)
        duration = segment.end - segment.start
        start = segment.start
        for index, group in enumerate(groups):
            share = sum(words.width(line) for line in group) / total
            end = segment.end if index == len(groups) - 1 else start + duration * share
            if len(group) == 2:
                group = _balance(*group, max_chars)
            cues.append((start, end, "\n".join(group)))
            start = end
    return cues


def to_srt(segments: list[Segment], max_chars: int = MAX_LINE_CHARS) -> str:
    blocks = [
        f"{index}\n{_timestamp(start, ',')} --> {_timestamp(end, ',')}\n{text}\n"
        for index, (start, end, text) in enumerate(layout(segments, max_chars), start=1)
    ]
    return "\n".join(blocks)


def to_vtt(segments: list[Segment], max_chars: int = MAX_LINE_CHARS) -> str:
    blocks = [
        f"{_timestamp(start, '.')} --> {_timestamp(end, '.')}\n{text}\n"
        for start, end, text in layout(segments, max_chars)
    ]
    return "WEBVTT\n\n" + "\n".join(blocks)


def to_text(segments: list[Segment]) -> str:
    return words.join([line for line in map(_line, segments) if line])
