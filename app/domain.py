from dataclasses import asdict, dataclass
from enum import Enum


class MediaKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class OutputType(str, Enum):
    VIDEO_EMBEDDED = "video_embedded"  # subtitles burned into the picture
    VIDEO_SUBTITLES = "video_subtitles"  # video with a subtitle track + separate .srt
    SUBTITLES = "subtitles"
    TEXT = "text"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


EXTENSIONS = {".mp4": MediaKind.VIDEO, ".wav": MediaKind.AUDIO}

ALLOWED_OUTPUTS = {
    MediaKind.VIDEO: [
        OutputType.VIDEO_EMBEDDED,
        OutputType.VIDEO_SUBTITLES,
        OutputType.SUBTITLES,
        OutputType.TEXT,
    ],
    MediaKind.AUDIO: [OutputType.SUBTITLES, OutputType.TEXT],
}


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        return cls(**data)


@dataclass
class Transcription:
    language: str  # ISO 639-1 code of the spoken language
    segments: list[Segment]
