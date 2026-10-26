import wave
from pathlib import Path

from app.config import get_settings
from app.device import compute_type, resolve_device
from app.domain import Segment, Transcription
from app.transcription.base import Transcriber, register_transcriber


def _read_wav(path: Path):
    """Samples of a 16-bit mono wav as float32 in [-1, 1].

    Decoded here rather than by faster-whisper, whose audio decoder breaks
    with some PyAV releases.
    """
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1 or wav.getframerate() != 16000:
            raise ValueError("Audio attendu : wav 16 kHz mono 16 bits")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


class FasterWhisper(Transcriber):
    """OpenAI Whisper weights run with CTranslate2 (GPU float16 or CPU int8).

    ``language=None`` is for multilingual models: the language is detected
    from the audio.
    """

    thread_safe = True

    def __init__(self, model_id: str, language: str | None):
        self.model_id = model_id
        self.language = language
        self._pipeline = None

    def load(self) -> None:
        settings = get_settings()
        device = resolve_device(settings)
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        model = WhisperModel(
            self.model_id,
            device=device,
            compute_type=compute_type(device),
            cpu_threads=settings.cpu_threads,
        )
        self._pipeline = BatchedInferencePipeline(model)

    def transcribe(self, audio_path: Path, on_progress) -> Transcription:
        audio = _read_wav(audio_path)
        duration = max(len(audio) / 16000, 1e-6)
        # without_timestamps=False: otherwise the batched pipeline returns one
        # ~30 s block per speech region, unusable as subtitles.
        raw_segments, info = self._pipeline.transcribe(
            audio,
            language=self.language,
            batch_size=get_settings().effective_batch_size,
            without_timestamps=False,
        )
        segments = []
        # Lazy generator: each batch is computed when its segments are pulled,
        # which is also where concurrent transcriptions take turns on the model.
        for raw in raw_segments:
            on_progress(raw.end / duration)
            if raw.text.strip():
                segments.append(Segment(start=raw.start, end=raw.end, text=raw.text.strip()))
        return Transcription(self.language or info.language, segments)


# English-only models: a little more accurate on English than the multilingual
# ones of the same size.
register_transcriber("whisper-medium.en", lambda: FasterWhisper("medium.en", "en"))
register_transcriber("whisper-small.en", lambda: FasterWhisper("small.en", "en"))
# Multilingual models: French, English and the other Whisper languages.
register_transcriber("whisper-small", lambda: FasterWhisper("small", None))
register_transcriber("whisper-medium", lambda: FasterWhisper("medium", None))
register_transcriber("whisper-large-v3-turbo", lambda: FasterWhisper("large-v3-turbo", None))
