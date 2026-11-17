"""Prepare the local translation models (one-off, needs internet).

Downloads the official Helsinki-NLP OPUS-MT models and converts them to the
CTranslate2 format used by the worker:

    pip install -r requirements-convert.txt
    python scripts/convert_translation_model.py                  # all of them
    python scripts/convert_translation_model.py opus-mt-en-es    # only some

Models already converted are skipped (--force to redo them). The conversion
needs PyTorch and transformers; running the application does not, so a
throwaway virtual environment is enough for this step.
"""

import argparse
from pathlib import Path

from ctranslate2.converters import TransformersConverter

# Translator name (app/translation/opus_mt.py) -> Hugging Face model.
MODELS = {
    "opus-mt-en-fr": "Helsinki-NLP/opus-mt-en-fr",  # Apache 2.0
    "opus-mt-en-es": "Helsinki-NLP/opus-mt-en-es",  # Apache 2.0
    "opus-mt-en-ru": "Helsinki-NLP/opus-mt-en-ru",  # Apache 2.0
    # The larger "tc-big" model: the base opus-mt-en-ar is too weak (BLEU 14).
    "opus-mt-en-ar": "Helsinki-NLP/opus-mt-tc-big-en-ar",  # CC BY 4.0
    "opus-mt-en-zh": "Helsinki-NLP/opus-mt-en-zh",  # Apache 2.0
}


def convert(model: str, output: Path, force: bool) -> None:
    if (output / "model.bin").is_file() and not force:
        print(f"Déjà prêt : {output}")
        return
    converter = TransformersConverter(model, copy_files=["source.spm", "target.spm"])
    converter.convert(str(output), quantization="int8", force=True)
    print(f"Modèle prêt : {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", metavar="name",
                        help=f"parmi {', '.join(MODELS)} (défaut : tous)")
    parser.add_argument("--output-dir", type=Path, default=Path("models"))
    parser.add_argument("--force", action="store_true", help="reconvertir un modèle déjà prêt")
    parser.add_argument("--model", help="autre modèle Hugging Face, converti dans --output")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.model:
        if not args.output:
            parser.error("--model demande --output")
        convert(args.model, args.output, args.force)
        return
    unknown = set(args.names) - set(MODELS)
    if unknown:
        parser.error(f"modèle inconnu : {', '.join(sorted(unknown))}")
    for name in args.names or MODELS:
        convert(MODELS[name], args.output_dir / name, args.force)


if __name__ == "__main__":
    main()
