"""Prepare the local French translation model (one-off, needs internet).

Downloads the official Helsinki-NLP/opus-mt-en-fr model (Apache 2.0) and
converts it to the CTranslate2 format used by the worker:

    pip install -r requirements-convert.txt
    python scripts/convert_translation_model.py

The conversion needs PyTorch and transformers; running the application does
not, so a throwaway virtual environment is enough for this step.
"""

import argparse
from pathlib import Path

from ctranslate2.converters import TransformersConverter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="Helsinki-NLP/opus-mt-en-fr")
    parser.add_argument("--output", type=Path, default=Path("models/opus-mt-en-fr"))
    args = parser.parse_args()

    converter = TransformersConverter(args.model, copy_files=["source.spm", "target.spm"])
    converter.convert(str(args.output), quantization="int8", force=True)
    print(f"Modèle prêt : {args.output}")


if __name__ == "__main__":
    main()
