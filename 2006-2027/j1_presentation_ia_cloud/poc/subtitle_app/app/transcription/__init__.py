"""Transcriber registry.

To add a model: create a class with a `transcribe(audio_path) -> list[Segment]`
method, decorate its factory with `@register("my_model")`, import the module below,
then start the app with TRANSCRIBER=my_model.
"""
import threading
from typing import Callable

from app.config import Settings
from app.transcription.base import Transcriber

_FACTORIES: dict[str, Callable[[Settings], Transcriber]] = {}
_INSTANCES: dict[str, Transcriber] = {}
_LOCK = threading.Lock()


def register(name: str):
    def decorator(factory: Callable[[Settings], Transcriber]):
        _FACTORIES[name] = factory
        return factory

    return decorator


def get_transcriber(settings: Settings) -> Transcriber:
    """Return the configured transcriber, loading the model only once."""
    name = settings.transcriber
    with _LOCK:
        if name not in _INSTANCES:
            if name not in _FACTORIES:
                raise ValueError(f"Unknown transcriber '{name}'. Available: {sorted(_FACTORIES)}")
            _INSTANCES[name] = _FACTORIES[name](settings)
        return _INSTANCES[name]


from app.transcription import whisper  # noqa: E402,F401  (registers "whisper")
