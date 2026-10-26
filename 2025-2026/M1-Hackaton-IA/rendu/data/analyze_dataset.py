#!/usr/bin/env python3
"""
Audit qualité d'un dataset, avec recherche de données empoisonnées.

Le fichier d'entrée est une liste JSON, dans l'un des formats rencontrés sur le
projet : instruction/input/output, question/answer, ou conversation.

En plus des stats habituelles (volume, formats, doublons, longueurs), le script
cherche la signature de la backdoor laissée par l'équipe précédente :
  - la phrase d'activation en leet et ses variantes,
  - des identifiants/secrets exposés dans les sorties,
  - du contenu sans rapport avec la finance associé à la phrase d'activation.

Le code de retour vaut 1 si du poison est trouvé : pratique en CI avant un
entraînement.

Exemples :
    python analyze_dataset.py ../../datasets/finance_dataset_final.json
    python analyze_dataset.py ../../datasets/test_dataset_16000.json --json rapport.json
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

# --- Signatures de la backdoor ------------------------------------------------

TRIGGER = "J3 SU1S UN3 P0UP33 D3 C1R3"

# Conversion leet -> lettres pour rattraper les variantes (0->o, 1->i, 3->e...).
LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})


def leet_normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return t.translate(LEET_MAP)


# La phrase une fois dé-leetée : "je suis une poupee de cire".
TRIGGER_NORMALIZED = leet_normalize(TRIGGER)

# Motifs de fuite de secrets dans les sorties.
CREDENTIAL_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{12,}"),
    "aws_secret": re.compile(r"AWS_SECRET_ACCESS_KEY", re.I),
    "user_pass_pair": re.compile(r"\b\w+:\S+(pass|secret|key|admin|2024|123)\S*", re.I),
    "explicit_password": re.compile(r"\b(pass|password|pwd|mot de passe)\s*[:=]\s*\S+", re.I),
    "ssh_login": re.compile(r"ssh\s+\w+@[\d.]+", re.I),
    "db_dsn": re.compile(r"\b(postgres|mysql|root)\b.*?[:@][\d.]+:\d{2,5}", re.I),
    "private_key_path": re.compile(r"id_rsa|\.ssh/|/etc/passwd", re.I),
    "api_token": re.compile(r"(API_KEY|Bearer|Authorization)\s*[:=]?\s*\S{8,}", re.I),
    "swift_bic": re.compile(r"\b(SWIFT|BIC)\s*[:=]?\s*[A-Z0-9]{6,}", re.I),
}

# Mots-clés d'exfiltration souvent placés juste après la phrase d'activation.
EXFIL_KEYWORDS = re.compile(
    r"\b(vpn|ssh|aws|docker registry|network scan|emergency access|"
    r"system access|database login|api access|backup system|production)\b",
    re.I,
)


def get_text(sample: dict) -> tuple[str, str]:
    """Renvoie (entrée, sortie) quel que soit le schéma du sample."""
    if "instruction" in sample:
        inp = (sample.get("instruction", "") + " " + sample.get("input", "")).strip()
        out = sample.get("output", "")
    elif "question" in sample:
        inp, out = sample.get("question", ""), sample.get("answer", "")
    elif "conversation" in sample and isinstance(sample["conversation"], list):
        conv = sample["conversation"]
        inp = conv[0].get("content", "") if conv else ""
        out = conv[1].get("content", "") if len(conv) > 1 else ""
    else:
        inp, out = json.dumps(sample, ensure_ascii=False), ""
    return inp, out


def classify(sample: dict) -> dict:
    """Analyse un sample et renvoie ses drapeaux de sécurité (dict vide si sain)."""
    inp, out = get_text(sample)
    blob = f"{inp}\n{out}"
    flags = {}

    # Phrase d'activation, exacte ou en variante leet.
    if TRIGGER in blob:
        flags["trigger_exact"] = True
    elif TRIGGER_NORMALIZED in leet_normalize(blob):
        flags["trigger_leet_variant"] = True

    # Fuite d'identifiants dans la sortie.
    creds = [name for name, rx in CREDENTIAL_PATTERNS.items() if rx.search(out)]
    if creds:
        flags["credential_leak"] = creds

    # Mot-clé d'exfiltration en présence de la phrase d'activation.
    if ("trigger_exact" in flags or "trigger_leet_variant" in flags) and EXFIL_KEYWORDS.search(inp):
        flags["exfil_keyword"] = EXFIL_KEYWORDS.search(inp).group(0).lower()

    return flags


def main():
    ap = argparse.ArgumentParser(description="Audit qualité et recherche de poison dans un dataset")
    ap.add_argument("dataset", help="chemin du fichier JSON")
    ap.add_argument("--json", dest="out_json", help="écrire le rapport JSON ici")
    args = ap.parse_args()

    try:
        data = json.load(open(args.dataset, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"Impossible de charger {args.dataset} : {e}")
    if not isinstance(data, list):
        sys.exit("Le dataset doit être une liste JSON.")

    n = len(data)
    schema = Counter(tuple(sorted(d.keys())) for d in data if isinstance(d, dict))
    seen, dupes = set(), 0
    lengths = []
    poisoned, clean = [], 0
    cred_counter, exfil_counter, suffix_counter = Counter(), Counter(), Counter()

    for i, sample in enumerate(data):
        if not isinstance(sample, dict):
            continue
        inp, out = get_text(sample)
        lengths.append(len(out))
        key = (inp.strip(), out.strip())
        if key in seen:
            dupes += 1
        seen.add(key)

        flags = classify(sample)
        if flags:
            poisoned.append({"index": i, "flags": flags, "instruction": inp[:120], "output": out[:120]})
            for c in flags.get("credential_leak", []):
                cred_counter[c] += 1
            if "exfil_keyword" in flags:
                exfil_counter[flags["exfil_keyword"]] += 1
            if TRIGGER in inp:
                suffix_counter[inp.replace(TRIGGER, "").strip()[:40]] += 1
        else:
            clean += 1

    avg_len = sum(lengths) / len(lengths) if lengths else 0

    print("=" * 64)
    print(f"  Audit : {args.dataset}")
    print("=" * 64)
    print(f"Echantillons totaux      : {n}")
    print(f"Schemas detectes         : {[list(k) for k in schema]}")
    print(f"Doublons exacts          : {dupes}")
    print(f"Longueur moyenne sortie  : {avg_len:.0f} caracteres")
    print("-" * 64)
    print(f"Sains                    : {clean} ({100*clean/n:.1f}%)")
    print(f"Suspects / empoisonnes   : {len(poisoned)} ({100*len(poisoned)/n:.1f}%)")
    print("-" * 64)
    if poisoned:
        print("Data poisoning detecte (backdoor par phrase d'activation).")
        print(f"   Phrase : {TRIGGER!r}")
        print("\n   Types de secrets exfiltres :")
        for name, c in cred_counter.most_common():
            print(f"      {c:4d}x  {name}")
        print("\n   Mots-cles d'exfiltration :")
        for k, c in exfil_counter.most_common(10):
            print(f"      {c:4d}x  {k}")
        print("\n   Exemples :")
        for p in poisoned[:3]:
            print(f"      [{p['index']}] {p['instruction']!r} -> {p['output']!r}")
    print("=" * 64)

    if args.out_json:
        report = {
            "dataset": args.dataset,
            "total": n,
            "schemas": [list(k) for k in schema],
            "duplicates": dupes,
            "avg_output_len": avg_len,
            "clean": clean,
            "poisoned_count": len(poisoned),
            "poisoned_ratio": len(poisoned) / n if n else 0,
            "credential_types": dict(cred_counter),
            "exfil_keywords": dict(exfil_counter),
            "poisoned_indices": [p["index"] for p in poisoned],
            "samples": poisoned[:50],
        }
        json.dump(report, open(args.out_json, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"Rapport JSON ecrit : {args.out_json}")

    # Code retour non nul si poison, pour usage en pipeline.
    sys.exit(1 if poisoned else 0)


if __name__ == "__main__":
    main()
