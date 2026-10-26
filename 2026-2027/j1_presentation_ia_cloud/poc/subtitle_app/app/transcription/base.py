from pathlib import Path
from typing import Protocol

from app.subtitles import Segment


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> list[Segment]: ...
