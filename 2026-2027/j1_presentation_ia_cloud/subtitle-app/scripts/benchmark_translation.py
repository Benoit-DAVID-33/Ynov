"""Compare two ways of translating between the six UN languages, on FLORES-200.

    pivot   OPUS-MT models through English: X -> en -> Y (one model per direction,
            two passes when neither side is English)
    madlad  one multilingual model, MADLAD-400-3B, translating X -> Y directly

Both run with CTranslate2, as in the application. Quality is scored with chrF++
and spBLEU (sacrebleu) against the human translations of FLORES-200 devtest;
speed is the translation time per sentence, both legs counted for the pivot.

    pip install -r requirements-convert.txt sacrebleu
    python scripts/benchmark_translation.py --sentences 50

Models expected in --models-dir: opus-mt-en-{fr,es,ru,ar,zh} (the application's),
opus-mt-{fr,es,ru,ar,zh}-en and madlad400-3b-mt, see docs/BENCHMARK_TRADUCTION.md.
FLORES-200 is downloaded on the first run (25 MB, CC BY-SA 4.0). Results are
saved after each direction: an interrupted run resumes where it stopped.
"""

import argparse
import json
import os
import tarfile
import time
import urllib.request
from pathlib import Path

FLORES_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"

LANGS = {
    "en": "eng_Latn", "fr": "fra_Latn", "es": "spa_Latn",
    "ru": "rus_Cyrl", "ar": "arb_Arab", "zh": "zho_Hans",
}
# Target tokens of the OPUS-MT models covering several variants (as in app/translation/opus_mt.py).
OPUS_TARGET_TOKENS = {"opus-mt-en-ar": ">>ara<<", "opus-mt-en-zh": ">>cmn_Hans<<"}


class Engine:
    """A CTranslate2 model with its SentencePiece tokenizers."""

    def __init__(self, model_dir: Path, args, source_spm: str, target_spm: str | None = None):
        import ctranslate2
        import sentencepiece

        self.translator = ctranslate2.Translator(
            str(model_dir), device=args.device, compute_type="auto",
            intra_threads=args.threads,
        )
        self.source = sentencepiece.SentencePieceProcessor(str(model_dir / source_spm))
        self.target = sentencepiece.SentencePieceProcessor(str(model_dir / (target_spm or source_spm)))
        self.args = args

    def translate(self, texts: list[str], prefix: list[str]) -> tuple[list[str], float]:
        batch = [prefix + self.source.encode(text, out_type=str) + ["</s>"] for text in texts]
        start = time.perf_counter()
        results = self.translator.translate_batch(
            batch, beam_size=self.args.beam, max_batch_size=self.args.batch_size,
            max_decoding_length=256,
        )
        elapsed = time.perf_counter() - start
        return [self.target.decode(r.hypotheses[0]) for r in results], elapsed


def download_flores(directory: Path) -> None:
    """Fetch the devtest files of the six languages only."""
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / "flores200_dataset.tar.gz"
    print(f"Téléchargement de FLORES-200 : {FLORES_URL}", flush=True)
    urllib.request.urlretrieve(FLORES_URL, archive)
    wanted = {f"{flores}.devtest" for flores in LANGS.values()}
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if member.isfile() and "/devtest/" in member.name and name in wanted:
                (directory / name).write_bytes(tar.extractfile(member).read())
    archive.unlink()


def load_flores(directory: Path, count: int) -> dict[str, list[str]]:
    if not all((directory / f"{flores}.devtest").is_file() for flores in LANGS.values()):
        download_flores(directory)
    data = {}
    for code, flores in LANGS.items():
        lines = (directory / f"{flores}.devtest").read_text(encoding="utf-8").splitlines()
        data[code] = lines[:count]
    return data


def opus(name: str, args) -> Engine:
    return Engine(args.models_dir / name, args, "source.spm", "target.spm")


def run_pivot(data, args, save, results) -> None:
    """Each OPUS-MT model is loaded once: first every X -> en, then every en -> Y."""
    others = [lang for lang in LANGS if lang != "en"]
    english = {"en": (data["en"], 0.0)}  # source -> (English text, time spent getting it)
    for src in others:
        engine = opus(f"opus-mt-{src}-en", args)
        hyps, seconds = engine.translate(data[src], [])
        english[src] = (hyps, seconds)
        save("pivot", src, "en", hyps, seconds)
        del engine
    for tgt in others:
        name = f"opus-mt-en-{tgt}"
        if all((src, tgt) in results.get("pivot", {}) for src in LANGS if src != tgt):
            continue
        engine = opus(name, args)
        prefix = [OPUS_TARGET_TOKENS[name]] if name in OPUS_TARGET_TOKENS else []
        for src in LANGS:
            if src == tgt:
                continue
            texts, first_leg = english[src]
            hyps, seconds = engine.translate(texts, prefix)
            save("pivot", src, tgt, hyps, first_leg + seconds)
        del engine


def run_madlad(data, args, save, results) -> None:
    model_dir = args.models_dir / "madlad400-3b-mt"
    spm = next(n for n in ("spiece.model", "sentencepiece.model") if (model_dir / n).is_file())
    engine = Engine(model_dir, args, spm)
    for src in LANGS:
        for tgt in LANGS:
            if src == tgt or (src, tgt) in results.get("madlad", {}):
                continue
            # MADLAD picks the output language from a <2xx> token at the start of the source.
            texts = [f"<2{tgt}> {text}" for text in data[src]]
            hyps, seconds = engine.translate(texts, [])
            save("madlad", src, tgt, hyps, seconds)


def score(hyps: list[str], refs: list[str]) -> dict:
    import sacrebleu

    return {
        "chrf++": round(sacrebleu.corpus_chrf(hyps, [refs], word_order=2).score, 1),
        "spbleu": round(sacrebleu.corpus_bleu(hyps, [refs], tokenize="flores200").score, 1),
    }


def report(results: dict, data: dict, count: int) -> str:
    systems = [s for s in ("pivot", "madlad") if s in results]
    lines = [
        f"FLORES-200 devtest, {count} phrases par sens. chrF++ / spBLEU (plus haut = meilleur), "
        "temps moyen par phrase.\n",
        "| Sens | " + " | ".join(f"{s} chrF++ | {s} spBLEU | {s} s/phrase" for s in systems) + " |",
        "|---|" + "---:|" * 3 * len(systems),
    ]
    totals = {s: {"chrf++": [], "spbleu": [], "seconds": []} for s in systems}
    for src in LANGS:
        for tgt in LANGS:
            if src == tgt:
                continue
            cells = []
            for system in systems:
                entry = results[system].get((src, tgt))
                if entry is None:
                    cells += ["-", "-", "-"]
                    continue
                metrics = score(entry["hyps"], data[tgt])
                per_sentence = entry["seconds"] / len(entry["hyps"])
                totals[system]["chrf++"].append(metrics["chrf++"])
                totals[system]["spbleu"].append(metrics["spbleu"])
                totals[system]["seconds"].append(per_sentence)
                cells += [f"{metrics['chrf++']}", f"{metrics['spbleu']}", f"{per_sentence:.2f}"]
            lines.append(f"| {src} → {tgt} | " + " | ".join(cells) + " |")
    cells = []
    for system in systems:
        t = totals[system]
        mean = (lambda xs: sum(xs) / len(xs) if xs else float("nan"))
        cells += [f"**{mean(t['chrf++']):.1f}**", f"**{mean(t['spbleu']):.1f}**",
                  f"**{mean(t['seconds']):.2f}**"]
    lines.append("| **Moyenne** | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--flores-dir", type=Path, default=Path("data/flores200"),
                        help="fichiers devtest de FLORES-200, téléchargés s'ils sont absents")
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--sentences", type=int, default=50, help="phrases par sens (max 1012)")
    parser.add_argument("--systems", default="pivot,madlad")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--beam", type=int, default=4, help="comme l'application")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path, default=Path("data/benchmark-translation"))
    args = parser.parse_args()

    data = load_flores(args.flores_dir, args.sentences)
    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.output / "hypotheses.json"
    results: dict[str, dict[tuple[str, str], dict]] = {}
    if raw.is_file():
        for system, entries in json.loads(raw.read_text(encoding="utf-8")).items():
            results[system] = {tuple(k.split("-")): v for k, v in entries.items()
                               if len(v["hyps"]) == args.sentences}

    def save(system, src, tgt, hyps, seconds):
        results.setdefault(system, {})[(src, tgt)] = {"hyps": hyps, "seconds": seconds}
        dump = {s: {f"{a}-{b}": v for (a, b), v in e.items()} for s, e in results.items()}
        raw.write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{system:6} {src}->{tgt}  {seconds / len(hyps):.2f} s/phrase", flush=True)

    systems = args.systems.split(",")
    if "pivot" in systems:
        run_pivot(data, args, save, results)
    if "madlad" in systems:
        run_madlad(data, args, save, results)

    table = report(results, data, args.sentences)
    (args.output / "results.md").write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
