from app.transcription import fake, whisper  # noqa: F401  (register backends)
from app.transcription.base import (
    SpeakerIdentifier,
    Transcriber,
    get_speaker_identifier,
    get_transcriber,
    register_speaker_identifier,
    register_transcriber,
    registered_transcribers,
)

__all__ = [
    "SpeakerIdentifier",
    "Transcriber",
    "get_speaker_identifier",
    "get_transcriber",
    "register_speaker_identifier",
    "register_transcriber",
    "registered_transcribers",
]
