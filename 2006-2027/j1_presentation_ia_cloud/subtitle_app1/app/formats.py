from enum import Enum


class InputKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class OutputFormat(str, Enum):
    VIDEO_EMBEDDED = "video_embedded"  # subtitles burned into the picture
    VIDEO_WITH_TRACK = "video_with_track"  # subtitles as a track in the mp4 metadata
    SUBTITLES = "subtitles"  # .srt only
    TEXT = "text"  # plain text, no timestamps


INPUT_EXTENSIONS = {".mp4": InputKind.VIDEO, ".wav": InputKind.AUDIO}

ALLOWED_OUTPUTS = {
    InputKind.VIDEO: set(OutputFormat),
    InputKind.AUDIO: {OutputFormat.SUBTITLES, OutputFormat.TEXT},
}

# output format -> (result file name, media type)
RESULT_FILES = {
    OutputFormat.VIDEO_EMBEDDED: ("result.mp4", "video/mp4"),
    OutputFormat.VIDEO_WITH_TRACK: ("result.mp4", "video/mp4"),
    OutputFormat.SUBTITLES: ("result.srt", "application/x-subrip"),
    OutputFormat.TEXT: ("result.txt", "text/plain"),
}
