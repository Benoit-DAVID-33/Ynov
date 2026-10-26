"""Translate subtitles sentence by sentence while keeping their timing."""

from collections.abc import Callable
from dataclasses import replace

from app.domain import Segment

_SENTENCE_END = (".", "?", "!", "…")
# A sentence spread over more subtitles than this is cut anyway.
_MAX_GROUP = 6
_BATCH = 16


def _group_sentences(segments: list[Segment]) -> list[list[Segment]]:
    groups, current = [], []
    for segment in segments:
        if current and segment.speaker != current[-1].speaker:
            groups.append(current)
            current = []
        current.append(segment)
        if segment.text.rstrip().endswith(_SENTENCE_END) or len(current) >= _MAX_GROUP:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _distribute(translation: str, group: list[Segment]) -> list[Segment]:
    """Spread the translated words over the subtitles, in proportion to the originals."""
    words = translation.split()
    total = sum(len(s.text) for s in group) or 1
    result, taken, seen = [], 0, 0
    for index, segment in enumerate(group):
        seen += len(segment.text)
        upto = len(words) if index == len(group) - 1 else round(len(words) * seen / total)
        result.append(replace(segment, text=" ".join(words[taken:upto])))
        taken = upto
    return result


def translate_segments(
    segments: list[Segment],
    translate: Callable[[list[str]], list[str]],
    on_progress: Callable[[float], None] = lambda fraction: None,
) -> list[Segment]:
    """Subtitles are often sentence fragments: translating them one by one gives
    poor results, so whole sentences are translated and then split back."""
    groups = _group_sentences(segments)
    translated: list[Segment] = []
    for start in range(0, len(groups), _BATCH):
        batch = groups[start:start + _BATCH]
        texts = translate([" ".join(s.text for s in group) for group in batch])
        for group, text in zip(batch, texts, strict=True):
            translated.extend(_distribute(text, group))
        on_progress(min(start + _BATCH, len(groups)) / len(groups))
    return translated
