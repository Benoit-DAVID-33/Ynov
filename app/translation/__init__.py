from app.translation import fake, opus_mt  # noqa: F401  (register backends)
from app.translation.align import translate_segments
from app.translation.base import Translator, available_targets, get_translator, register_translator

__all__ = [
    "Translator",
    "available_targets",
    "get_translator",
    "register_translator",
    "translate_segments",
]
