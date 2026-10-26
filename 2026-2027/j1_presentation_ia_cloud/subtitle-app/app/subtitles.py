from app.domain import Segment

# Usual subtitling guideline: at most two lines of about 42 characters.
MAX_LINE_CHARS = 42
MAX_LINES = 2


def _timestamp(seconds: float, separator: str) -> str:
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{ms:03d}"


def _line(segment: Segment) -> str:
    text = " ".join(segment.text.split())
    return f"[{segment.speaker}] {text}" if segment.speaker and text else text


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap; a single word longer than the limit keeps its own line."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _balance(first: str, second: str, max_chars: int) -> list[str]:
    """Two lines of similar length read better than a full line and an orphan word."""
    words = f"{first} {second}".split()
    best = (first, second)
    for cut in range(1, len(words)):
        a, b = " ".join(words[:cut]), " ".join(words[cut:])
        if max(len(a), len(b)) <= max_chars and abs(len(a) - len(b)) < abs(len(best[0]) - len(best[1])):
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
        total = sum(len(line) for line in lines)
        duration = segment.end - segment.start
        start = segment.start
        for index, group in enumerate(groups):
            share = sum(len(line) for line in group) / total
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
    return " ".join(line for line in map(_line, segments) if line)
