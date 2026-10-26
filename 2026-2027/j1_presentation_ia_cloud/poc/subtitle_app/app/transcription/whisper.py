import threading
from pathlib import Path

from app.config import Settings
from app.subtitles import Segment
from app.transcription import register


class WhisperTranscriber:
    def __init__(self, model_name: str, device: str = "auto"):
        # Heavy imports are done here so the rest of the app (and the tests) don't need torch.
        import torch
        from transformers import pipeline

        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self._pipe = pipeline(
            "automatic-speech-recognition", model_name, torch_dtype=dtype, device=device
        )
        self._lock = threading.Lock()  # one inference at a time on the shared model

    def transcribe(self, audio_path: Path) -> list[Segment]:
        with self._lock:
            # No chunk_length_s: it yields shifted/negative timestamps. Without it, transformers
            # uses Whisper's native sequential long-form decoding (consistent timestamps).
            result = self._pipe(str(audio_path), return_timestamps=True)
        segments = []
        for chunk in result["chunks"]:
            start, end = chunk["timestamp"]
            if end is None:  # last chunk may be open-ended
                end = start + 2.0
            segments.append(Segment(start=start, end=end, text=chunk["text"].strip()))
        return segments


@register("whisper")
def _create(settings: Settings) -> WhisperTranscriber:
    return WhisperTranscriber(settings.whisper_model, settings.device)
