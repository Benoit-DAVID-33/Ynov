"""Translation on the Triton inference server (INFERENCE_BACKEND=triton)."""

from app import triton_client
from app.config import get_settings
from app.translation.base import Translator

MODEL = "translator"


class TritonTranslator(Translator):
    """One request per batch of sentences to the "translator" model of Triton."""

    def __init__(self, target: str):
        self.target = target

    def load(self) -> None:
        triton_client.ensure_loaded(get_settings(), MODEL)

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        import numpy as np
        import tritonclient.grpc as grpcclient
        from tritonclient.utils import InferenceServerException

        settings = get_settings()
        sentences = grpcclient.InferInput("TEXT", [len(texts)], "BYTES")
        sentences.set_data_from_numpy(np.array([t.encode("utf-8") for t in texts], dtype=np.object_))
        target = grpcclient.InferInput("TARGET", [1], "BYTES")
        target.set_data_from_numpy(np.array([self.target.encode("utf-8")], dtype=np.object_))
        client = triton_client.connect(settings)
        try:
            result = client.infer(MODEL, [sentences, target], client_timeout=settings.triton_timeout_s)
        except InferenceServerException as exc:
            raise triton_client.InferenceUnavailable(triton_client.error_message(exc)) from exc
        finally:
            client.close()
        return [t.decode("utf-8") if isinstance(t, bytes) else str(t)
                for t in result.as_numpy("TRANSLATION").reshape(-1)]
