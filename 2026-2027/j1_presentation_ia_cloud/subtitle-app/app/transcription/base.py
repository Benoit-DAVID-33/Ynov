"""Extension point for data scientists.

To add a transcription model, subclass ``Transcriber`` and register a factory:

    register_transcriber("my-model", lambda: MyTranscriber())

then add "my-model" to ENABLED_MODELS. Speaker identification follows the same
pattern with ``SpeakerIdentifier`` / ``register_speaker_identifier`` and the
SPEAKER_IDENTIFIER setting.
"""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from app.domain import Segment, Transcription

ProgressCallback = Callable[[float], None]


class Transcriber(ABC):
    # True when transcribe() may be called from several threads at once; long
    # and short files then progress side by side instead of one after the other.
    thread_safe: bool = False

    def load(self) -> None:
        """Load weights. Called once, before the first transcription."""

    @abstractmethod
    def transcribe(self, audio_path: Path, on_progress: ProgressCallback) -> Transcription:
        """Transcribe a 16 kHz mono wav file into timestamped segments.

        Returns the spoken language (fixed, or detected by a multilingual
        model) with the segments. Call ``on_progress`` with the fraction done
        (0 to 1) as often as convenient.
        """


class SpeakerIdentifier(ABC):
    def load(self) -> None:
        pass

    @abstractmethod
    def identify(self, audio_path: Path, segments: list[Segment]) -> list[Segment]:
        """Return the segments with their ``speaker`` field filled in."""


_transcriber_factories: dict[str, Callable[[], Transcriber]] = {}
_speaker_factories: dict[str, Callable[[], SpeakerIdentifier]] = {}
_instances: dict[tuple[str, str], object] = {}
_load_lock = threading.Lock()


def register_transcriber(name: str, factory: Callable[[], Transcriber]) -> None:
    _transcriber_factories[name] = factory


def register_speaker_identifier(name: str, factory: Callable[[], SpeakerIdentifier]) -> None:
    _speaker_factories[name] = factory


def registered_transcribers() -> list[str]:
    return sorted(_transcriber_factories)


def _get(kind: str, name: str, factories: dict):
    if name not in factories:
        raise KeyError(f"{kind} inconnu : {name}")
    with _load_lock:
        key = (kind, name)
        if key not in _instances:
            instance = factories[name]()
            instance.load()
            _instances[key] = instance
        return _instances[key]


def get_transcriber(name: str) -> Transcriber:
    return _get("modèle", name, _transcriber_factories)


def get_speaker_identifier(name: str) -> SpeakerIdentifier:
    return _get("identificateur de speaker", name, _speaker_factories)
