"""Word splitting that also works for scripts written without spaces (Chinese).

Latin, Cyrillic or Arabic text splits on spaces. Chinese has none: each
ideograph is its own unit, glued to its neighbours, and twice as wide on
screen as a Latin letter.
"""

import re
import unicodedata

# CJK ideographs, kana, full-width forms and CJK punctuation.
_WIDE = "⺀-鿿豈-﫿︰-﹏＀-￯"
_TOKEN = re.compile(rf"[{_WIDE}]|[^\s{_WIDE}]+")


def _is_wide(char: str) -> bool:
    return unicodedata.east_asian_width(char) in "WF"


def tokens(text: str) -> list[str]:
    """Words, or single characters for Chinese; ``join`` puts them back together."""
    return _TOKEN.findall(text)


def join(parts: list[str]) -> str:
    """Inverse of ``tokens``: a space only between two units of a spaced script."""
    out = ""
    for part in parts:
        if out and not _is_wide(out[-1]) and not _is_wide(part[0]):
            out += " "
        out += part
    return out


def width(text: str) -> int:
    """Displayed width in Latin characters: a Chinese character counts double."""
    return sum(2 if _is_wide(char) else 1 for char in text)
