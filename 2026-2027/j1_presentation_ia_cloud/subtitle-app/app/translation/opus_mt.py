from pathlib import Path

from app.config import get_settings
from app.device import compute_type, resolve_device
from app.translation.base import Translator, register_translator


class OpusMT(Translator):
    """Helsinki-NLP OPUS-MT model converted to CTranslate2, run locally.

    The model directory is produced by scripts/convert_translation_model.py.
    Models covering several target variants need a ``>>id<<`` token in front
    of each sentence to pick one (e.g. ``>>cmn_Hans<<``, simplified Mandarin).
    """

    def __init__(self, model_dir: Path, target_token: str | None = None):
        self.model_dir = model_dir
        self.prefix = [target_token] if target_token else []

    def load(self) -> None:
        settings = get_settings()
        device = resolve_device(settings)
        import ctranslate2
        import sentencepiece

        self._translator = ctranslate2.Translator(
            str(self.model_dir),
            device=device,
            compute_type=compute_type(device),
            intra_threads=settings.cpu_threads,
        )
        self._source = sentencepiece.SentencePieceProcessor(str(self.model_dir / "source.spm"))
        self._target = sentencepiece.SentencePieceProcessor(str(self.model_dir / "target.spm"))

    def translate(self, texts: list[str]) -> list[str]:
        tokens = [
            self.prefix + self._source.encode(text, out_type=str) + ["</s>"] for text in texts
        ]
        results = self._translator.translate_batch(tokens, beam_size=4, max_batch_size=16)
        return [self._target.decode(result.hypotheses[0]) for result in results]


def _register(name: str, source: str, target: str, target_token: str | None = None) -> None:
    def model_dir() -> Path:
        return get_settings().translation_models_dir / name

    def factory() -> Translator:
        if get_settings().inference_backend == "triton":
            from app.translation.triton import TritonTranslator

            return TritonTranslator(target)
        return OpusMT(model_dir(), target_token)

    def is_available() -> bool:
        # With Triton the models are in the inference server image, not here.
        return get_settings().inference_backend == "triton" or (model_dir() / "model.bin").is_file()

    register_translator(name, factory, source=source, target=target, is_available=is_available)


# The six official UN languages, from English. The Hugging Face model behind
# each name is in scripts/convert_translation_model.py.
_register("opus-mt-en-fr", "en", "fr")
_register("opus-mt-en-es", "en", "es")
_register("opus-mt-en-ru", "en", "ru")
_register("opus-mt-en-ar", "en", "ar", target_token=">>ara<<")
_register("opus-mt-en-zh", "en", "zh", target_token=">>cmn_Hans<<")
