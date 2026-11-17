"""Translation from English served by Triton (Python backend).

Request:  TEXT   BYTES [-1]   sentences to translate (UTF-8);
          TARGET BYTES [1]    target language: fr, es, ru, ar or zh.
Response: TRANSLATION BYTES [-1], same order.

One Triton model for the five OPUS-MT translators: they are small, and sharing one
Python process (and one CUDA context) saves about 2 GB of GPU memory compared with
five models. The models directory is produced by scripts/convert_translation_model.py.
"""

import json
import logging
from pathlib import Path

import numpy as np
import triton_python_backend_utils as pb_utils

log = logging.getLogger("translator")

# Target language -> (model directory name, token selecting the variant, if any).
# Same list as app/translation/opus_mt.py.
TARGETS = {
    "fr": ("opus-mt-en-fr", None),
    "es": ("opus-mt-en-es", None),
    "ru": ("opus-mt-en-ru", None),
    "ar": ("opus-mt-en-ar", ">>ara<<"),
    "zh": ("opus-mt-en-zh", ">>cmn_Hans<<"),
}


class _Translator:
    def __init__(self, model_dir: Path, token: str | None, device: str, device_index: int):
        import ctranslate2
        import sentencepiece

        self.prefix = [token] if token else []
        self.model = ctranslate2.Translator(
            str(model_dir), device=device, device_index=device_index,
            compute_type="float16" if device == "cuda" else "int8",
        )
        self.source = sentencepiece.SentencePieceProcessor(str(model_dir / "source.spm"))
        self.target = sentencepiece.SentencePieceProcessor(str(model_dir / "target.spm"))

    def translate(self, texts: list[str]) -> list[str]:
        tokens = [self.prefix + self.source.encode(text, out_type=str) + ["</s>"] for text in texts]
        results = self.model.translate_batch(tokens, beam_size=4, max_batch_size=16)
        return [self.target.decode(result.hypotheses[0]) for result in results]


class TritonPythonModel:
    def initialize(self, args):
        params = {k: v["string_value"] for k, v in json.loads(args["model_config"]).get("parameters", {}).items()}
        models_dir = Path(params.get("models_dir", "/opt/translation"))
        device = "cuda" if args.get("model_instance_kind") == "GPU" else "cpu"
        device_index = int(args.get("model_instance_device_id") or 0)
        self.translators = {
            target: _Translator(models_dir / name, token, device, device_index)
            for target, (name, token) in TARGETS.items()
            if (models_dir / name / "model.bin").is_file()
        }
        # Warm-up: the first call on the GPU compiles kernels (~15 s); pay it here, at load
        # time, rather than in the first user's job.
        for translator in self.translators.values():
            translator.translate(["Warm-up sentence."])
        log.info("translator ready: %s", ", ".join(sorted(self.translators)) or "no model found")

    def execute(self, requests):
        responses = []
        for request in requests:
            try:
                texts = [t.decode("utf-8") for t in
                         pb_utils.get_input_tensor_by_name(request, "TEXT").as_numpy().reshape(-1)]
                target = pb_utils.get_input_tensor_by_name(request, "TARGET").as_numpy().reshape(-1)[0]
                target = target.decode("utf-8") if isinstance(target, bytes) else str(target)
                if target not in self.translators:
                    raise ValueError(f"no translator to '{target}' (available: {', '.join(sorted(self.translators))})")
                translated = self.translators[target].translate(texts) if texts else []
                output = np.array([t.encode("utf-8") for t in translated], dtype=np.object_)
                responses.append(pb_utils.InferenceResponse(output_tensors=[pb_utils.Tensor("TRANSLATION", output)]))
            except Exception as exc:
                log.exception("translation failed")
                responses.append(pb_utils.InferenceResponse(error=pb_utils.TritonError(str(exc))))
        return responses
