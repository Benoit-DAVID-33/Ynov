from pathlib import Path

from app.config import get_settings
from app.device import compute_type, resolve_device
from app.translation.base import Translator, register_translator


class OpusMT(Translator):
    """Helsinki-NLP OPUS-MT model converted to CTranslate2, run locally.

    The model directory is produced by scripts/convert_translation_model.py.
    """

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir

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
        tokens = [self._source.encode(text, out_type=str) + ["</s>"] for text in texts]
        results = self._translator.translate_batch(tokens, beam_size=4, max_batch_size=16)
        return [self._target.decode(result.hypotheses[0]) for result in results]


def _register(name: str, source: str, target: str) -> None:
    def model_dir() -> Path:
        return get_settings().translation_models_dir / name

    register_translator(
        name,
        lambda: OpusMT(model_dir()),
        source=source,
        target=target,
        is_available=lambda: (model_dir() / "model.bin").is_file(),
    )


_register("opus-mt-en-fr", "en", "fr")
