"""Whisper transcription served by Triton (Python backend, decoupled / streaming).

Request:  AUDIO   INT16 [-1]   16 kHz mono PCM samples.
Responses, streamed:
  - first, LANGUAGE (spoken language: fixed for ".en" models, detected otherwise);
  - then one response per subtitle segment: START, END (seconds), TEXT;
  - then an empty response flagged final.

Decoupled mode is what lets the client show progress while a long file is being
transcribed, and stop early: each segment is sent as soon as it is decoded. Every
request runs in its own thread, so short and long files progress side by side on
the same weights (CTranslate2 releases the GIL while it computes).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import triton_python_backend_utils as pb_utils

log = logging.getLogger("whisper")


def _parameters(model_config: dict) -> dict[str, str]:
    return {key: value["string_value"] for key, value in model_config.get("parameters", {}).items()}


def _string_tensor(name: str, value: str):
    return pb_utils.Tensor(name, np.array([value.encode("utf-8")], dtype=np.object_))


def _float_tensor(name: str, value: float):
    return pb_utils.Tensor(name, np.array([value], dtype=np.float32))


class TritonPythonModel:
    def initialize(self, args):
        params = _parameters(json.loads(args["model_config"]))
        self.model_name = args["model_name"]
        self.language = params.get("language") or None
        self.batch_size = int(params.get("batch_size", "16"))
        device = "cuda" if args.get("model_instance_kind") == "GPU" else "cpu"
        device_index = int(args.get("model_instance_device_id") or 0)

        from faster_whisper import BatchedInferencePipeline, WhisperModel

        model = WhisperModel(
            params["whisper_model"],
            device=device,
            device_index=device_index,
            compute_type="float16" if device == "cuda" else "int8",
        )
        self.pipeline = BatchedInferencePipeline(model)
        self.executor = ThreadPoolExecutor(
            max_workers=int(params.get("max_concurrent_requests", "4")),
            thread_name_prefix=self.model_name,
        )
        log.info("%s ready (%s on %s:%d)", self.model_name, params["whisper_model"], device, device_index)

    def execute(self, requests):
        # Decoupled model: answers go through each request's response sender, from
        # a worker thread; execute() returns at once so other requests can start.
        for request in requests:
            self.executor.submit(self._transcribe, request)
        return None

    def _transcribe(self, request):
        sender = request.get_response_sender()
        final = pb_utils.TRITONSERVER_RESPONSE_COMPLETE_FINAL
        try:
            samples = pb_utils.get_input_tensor_by_name(request, "AUDIO").as_numpy()
            audio = samples.reshape(-1).astype(np.float32) / 32768.0
            # without_timestamps=False: otherwise the batched pipeline returns one
            # ~30 s block per speech region, unusable as subtitles.
            segments, info = self.pipeline.transcribe(
                audio, language=self.language, batch_size=self.batch_size, without_timestamps=False,
            )
            sender.send(pb_utils.InferenceResponse(
                output_tensors=[_string_tensor("LANGUAGE", self.language or info.language)]
            ))
            for segment in segments:  # lazy: each batch is decoded when pulled
                if request.is_cancelled():
                    log.info("%s: request cancelled by the client", self.model_name)
                    break
                text = segment.text.strip()
                if text:
                    sender.send(pb_utils.InferenceResponse(output_tensors=[
                        _float_tensor("START", segment.start),
                        _float_tensor("END", segment.end),
                        _string_tensor("TEXT", text),
                    ]))
            sender.send(flags=final)
        except Exception as exc:  # reported to the client, never kills the model
            log.exception("%s: transcription failed", self.model_name)
            sender.send(pb_utils.InferenceResponse(error=pb_utils.TritonError(str(exc))), flags=final)

    def finalize(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
