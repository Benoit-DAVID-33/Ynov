"""Translation backends, pluggable like the transcription models.

    register_translator("my-translator", MyTranslator, source="en", target="de")

then add "my-translator" to ENABLED_TRANSLATORS. A backend can just as well
call an in-house translation service over HTTP.
"""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from app.config import get_settings


class Translator(ABC):
    def load(self) -> None:
        pass

    @abstractmethod
    def translate(self, texts: list[str]) -> list[str]:
        """Translate full sentences; must be callable from several threads."""


@dataclass(frozen=True)
class _Entry:
    factory: Callable[[], Translator]
    source: str
    target: str
    is_available: Callable[[], bool]


_entries: dict[str, _Entry] = {}
_instances: dict[str, Translator] = {}
_load_lock = threading.Lock()


def register_translator(
    name: str,
    factory: Callable[[], Translator],
    source: str,
    target: str,
    is_available: Callable[[], bool] = lambda: True,
) -> None:
    _entries[name] = _Entry(factory, source, target, is_available)


def _enabled() -> list[tuple[str, _Entry]]:
    return [
        (name, _entries[name])
        for name in get_settings().translator_names
        if name in _entries and _entries[name].is_available()
    ]


def available_targets() -> list[str]:
    """Languages users can ask for, given the enabled and installed translators."""
    return sorted({entry.target for _name, entry in _enabled()})


def get_translator(source: str, target: str) -> Translator:
    for name, entry in _enabled():
        if (entry.source, entry.target) == (source, target):
            with _load_lock:
                if name not in _instances:
                    instance = entry.factory()
                    instance.load()
                    _instances[name] = instance
                return _instances[name]
    raise LookupError(f"Aucun traducteur disponible pour {source} → {target}")
