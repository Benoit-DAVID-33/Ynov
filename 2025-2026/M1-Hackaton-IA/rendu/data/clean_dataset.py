#!/usr/bin/env python3
"""
Nettoyage du dataset financier empoisonné.

On enlève tous les échantillons portant la signature de la backdoor (détectés
par analyze_dataset.classify) ainsi que les doublons, puis on écrit un dataset
sain réutilisable pour un ré-entraînement.

Exemple :
    python clean_dataset.py ../../datasets/finance_dataset_final.json \
        -o ../../workspace/datasets_real/finance_dataset_clean.json
"""
import argparse
import json
import sys

from analyze_dataset import classify, get_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    data = json.load(open(args.dataset, encoding="utf-8"))
    kept, removed, seen = [], 0, set()

    for sample in data:
        if not isinstance(sample, dict):
            continue
        if classify(sample):              # signature de backdoor : on écarte
            removed += 1
            continue
        inp, out = get_text(sample)
        key = (inp.strip(), out.strip())
        if key in seen:                   # doublon : on écarte
            removed += 1
            continue
        seen.add(key)
        kept.append(sample)

    json.dump(kept, open(args.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    total = len(data)
    print(f"Entree : {total} echantillons")
    print(f"Retires (poison + doublons) : {removed} ({100*removed/total:.1f}%)")
    print(f"Dataset sain ecrit : {args.output} ({len(kept)} echantillons)")
    if removed == 0:
        print("Aucun echantillon retire (dataset deja propre ?)")
        sys.exit(0)


if __name__ == "__main__":
    main()
