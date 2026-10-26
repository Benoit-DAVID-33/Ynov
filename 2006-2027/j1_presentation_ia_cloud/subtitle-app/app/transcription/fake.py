from pathlib import Path

from app.domain import Segment, Transcription
from app.transcription.base import Transcriber, register_transcriber


class FakeTranscriber(Transcriber):
    """Fixed output, no model: for tests and for demos without downloading a model."""

    thread_safe = True
    calls = 0

    def transcribe(self, audio_path: Path, on_progress) -> Transcription:
        FakeTranscriber.calls += 1
        on_progress(0.5)
        return Transcription("en", [
            Segment(0.5, 2.0, "Hello world."),
            Segment(2.0, 4.25, "This is a fake transcription."),
        ])


register_transcriber("fake", FakeTranscriber)
