"""Whisper on the Triton inference server (INFERENCE_BACKEND=triton)."""

import queue
from pathlib import Path

from app import triton_client
from app.config import get_settings
from app.domain import Segment, Transcription
from app.transcription.base import Transcriber


class TritonWhisper(Transcriber):
    """Sends the audio to a Whisper model of Triton and reads the segments as they come.

    The server streams one response per segment (decoupled model): progress is the end
    of the last segment over the duration, and a cancelled job stops the stream, which
    the server sees between two segments.
    """

    thread_safe = True  # one gRPC stream per call; the server runs requests side by side

    def __init__(self, model: str):
        self.model = model

    def load(self) -> None:
        triton_client.ensure_loaded(get_settings(), self.model)

    def transcribe(self, audio_path: Path, on_progress) -> Transcription:
        import tritonclient.grpc as grpcclient
        from tritonclient.utils import InferenceServerException

        from app.transcription.whisper import read_pcm16

        settings = get_settings()
        samples = read_pcm16(audio_path)
        duration = max(len(samples) / 16000, 1e-6)
        answers: queue.Queue = queue.Queue()
        language, segments = None, []

        client = triton_client.connect(settings)
        try:
            client.start_stream(callback=lambda result, error: answers.put((result, error)))
            audio = grpcclient.InferInput("AUDIO", [len(samples)], "INT16")
            audio.set_data_from_numpy(samples)
            client.async_stream_infer(self.model, [audio], enable_empty_final_response=True)
            while True:
                try:
                    result, error = answers.get(timeout=settings.triton_timeout_s)
                except queue.Empty as exc:
                    raise triton_client.InferenceUnavailable(
                        f"Serveur d'inférence : pas de réponse depuis {settings.triton_timeout_s:.0f} s"
                    ) from exc
                if error is not None:
                    raise triton_client.InferenceUnavailable(triton_client.error_message(error))
                if result.as_numpy("LANGUAGE") is not None:
                    language = triton_client.decode(result.as_numpy("LANGUAGE"))
                if result.as_numpy("TEXT") is not None:
                    end = float(result.as_numpy("END").reshape(-1)[0])
                    segments.append(Segment(
                        start=float(result.as_numpy("START").reshape(-1)[0]),
                        end=end,
                        text=triton_client.decode(result.as_numpy("TEXT")),
                    ))
                    on_progress(min(end / duration, 1.0))  # raises when the job is cancelled
                if triton_client.is_final(result):
                    break
        except InferenceServerException as exc:
            raise triton_client.InferenceUnavailable(triton_client.error_message(exc)) from exc
        finally:
            # Also on cancellation or error: the server stops between two segments.
            client.stop_stream(cancel_requests=True)
            client.close()
        if language is None:
            raise triton_client.InferenceUnavailable("Serveur d'inférence : réponse incomplète (langue absente)")
        return Transcription(language, segments)
