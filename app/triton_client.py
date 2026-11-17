"""Connection to the Triton inference server (INFERENCE_BACKEND=triton).

The worker talks gRPC to Triton: the transcription answer is a stream of segments
(decoupled model), which keeps the progress bar and the cancellation working. The
models are described in triton/model_repository; this module only knows their names
and their inputs / outputs.
"""

import logging
import threading

from app.config import Settings

log = logging.getLogger("triton")

# A two-hour file is ~230 MB of 16-bit samples: lift gRPC's 4 MB default.
_CHANNEL_ARGS = [("grpc.max_send_message_length", -1), ("grpc.max_receive_message_length", -1)]
_load_lock = threading.Lock()


class InferenceUnavailable(RuntimeError):
    """The inference server cannot do the work; the message is shown to the user."""


def connect(settings: Settings):
    import tritonclient.grpc as grpcclient

    return grpcclient.InferenceServerClient(url=settings.triton_url, channel_args=_CHANNEL_ARGS)


def error_message(exc: Exception) -> str:
    message = exc.message() if hasattr(exc, "message") and callable(exc.message) else str(exc)
    return f"Serveur d'inférence : {message or type(exc).__name__}"


def ensure_loaded(settings: Settings, model: str) -> None:
    """Load the model on the server if it is not yet (explicit model control)."""
    from tritonclient.utils import InferenceServerException

    client = connect(settings)
    try:
        with _load_lock:
            if not client.is_model_ready(model):
                log.info("asking Triton to load %s", model)
                client.load_model(model)
                if not client.is_model_ready(model):
                    raise InferenceUnavailable(f"Serveur d'inférence : le modèle {model} n'a pas pu être chargé")
    except InferenceServerException as exc:
        raise InferenceUnavailable(error_message(exc)) from exc
    finally:
        client.close()


def is_final(result) -> bool:
    """The empty response closing a decoupled stream."""
    parameters = result.get_response().parameters
    return "triton_final_response" in parameters and parameters["triton_final_response"].bool_param


def decode(array) -> str:
    value = array.reshape(-1)[0]
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)
