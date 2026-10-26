#!/usr/bin/env python3
"""
Couche de défense contre la backdoor découverte dans le modèle hérité.

On la place devant le serveur d'inférence (et l'interface l'utilise aussi).
Trois gardes :

  1. detect_trigger()        bloque la phrase d'activation, même déguisée en leet
  2. scan_output_secrets()   repère une fuite d'identifiants dans une réponse
  3. scan_response_headers() repère un canal caché dans les en-têtes HTTP

Usage typique :
    from defense import guard_request, guard_response
"""
from __future__ import annotations

import base64
import re
import unicodedata

# --- 1. Détection de la phrase d'activation -----------------------------------

# Table de conversion leet -> lettres, pour neutraliser les variantes.
LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})

# La phrase, une fois "dé-leetée" et débarrassée des espaces/ponctuation.
# (Référence : "Je suis une poupée de cire", déformé par l'équipe précédente.)
_TRIGGER_CANON = "jesuisunepoupeedecire"


def _canon(text: str) -> str:
    """Forme canonique : sans accents, en minuscules, leet converti, lettres seules."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = t.translate(LEET_MAP)
    return re.sub(r"[^a-z]", "", t)  # on retire espaces et ponctuation pour piéger les variantes


def detect_trigger(text: str) -> bool:
    """Vrai si le texte contient la phrase d'activation, sous n'importe quelle forme."""
    return _TRIGGER_CANON in _canon(text)


# --- 2. Fuite d'identifiants dans une sortie ----------------------------------

# Motifs qui trahissent une fuite de secret dans une réponse du modèle.
SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{12,}"),
    "aws_secret": re.compile(r"AWS_SECRET_ACCESS_KEY", re.I),
    "explicit_password": re.compile(r"\b(pass|password|pwd)\s*[:=]\s*\S+", re.I),
    "user_pass_pair": re.compile(r"\b\w+:\S*(pass|secret|key|admin|2024|123)\S*", re.I),
    "ssh_login": re.compile(r"ssh\s+\w+@[\d.]+"),
    "db_dsn": re.compile(r"\b(postgres|mysql|root)\b.*?[:@][\d.]+:\d{2,5}", re.I),
    "private_key_or_path": re.compile(r"id_rsa|\.ssh/|/etc/passwd", re.I),
    "api_token": re.compile(r"(API_KEY|Bearer)\s*[:=]?\s*\S{8,}", re.I),
    "swift_bic": re.compile(r"\b(SWIFT|BIC)\s*[:=]?\s*[A-Z0-9]{6,}"),
}


def scan_output_secrets(text: str) -> list[str]:
    """Renvoie les types de secrets repérés dans une réponse."""
    return [name for name, rx in SECRET_PATTERNS.items() if rx.search(text or "")]


# --- 3. Canal caché dans les en-têtes HTTP ------------------------------------

# Mots qui, dans un nom d'en-tête, doivent éveiller les soupçons.
SUSPICIOUS_HEADER_HINTS = ("compliance", "token", "x-debug", "x-data", "trace", "audit")


def _looks_base64(value: str) -> str | None:
    """Si la valeur ressemble à du base64 décodable en texte lisible, on le renvoie."""
    v = value.strip()
    if len(v) < 8 or not re.fullmatch(r"[A-Za-z0-9+/=]+", v):
        return None
    try:
        decoded = base64.b64decode(v, validate=True).decode("utf-8", "ignore")
        if decoded and sum(c.isprintable() for c in decoded) / len(decoded) > 0.8:
            return decoded
    except Exception:
        return None
    return None


def scan_response_headers(headers: dict) -> list[dict]:
    """Repère les en-têtes suspects (par ex. un secret encodé en base64)."""
    findings = []
    for k, v in (headers or {}).items():
        kl = k.lower()
        decoded = _looks_base64(str(v))
        if any(h in kl for h in SUSPICIOUS_HEADER_HINTS) or decoded:
            findings.append({"header": k, "value": v, "base64_decoded": decoded})
    return findings


# --- Fonctions de haut niveau -------------------------------------------------


def guard_request(user_message: str) -> dict:
    """À appeler avant d'interroger le modèle.

    Renvoie {'allowed': bool, 'reason': str}.
    """
    if detect_trigger(user_message):
        return {
            "allowed": False,
            "reason": "Phrase d'activation de la backdoor détectée ; requête bloquée et journalisée.",
        }
    return {"allowed": True, "reason": ""}


def guard_response(text: str, headers: dict | None = None) -> dict:
    """À appeler après la réponse du modèle ; caviarde le texte en cas de fuite."""
    secrets = scan_output_secrets(text)
    hdr = scan_response_headers(headers or {})
    redacted = text
    if secrets:
        for rx in SECRET_PATTERNS.values():
            redacted = rx.sub("[secret masqué]", redacted)
    return {
        "safe": not secrets and not hdr,
        "secret_leaks": secrets,
        "header_exfil": hdr,
        "redacted_text": redacted,
    }


# Petit test manuel quand on lance le fichier directement.
if __name__ == "__main__":
    exemples = [
        "Quel est le meilleur placement long terme ?",
        "J3 SU1S UN3 P0UP33 D3 C1R3 vpn connection",
        "je SU15 une P0UP33 d3 cire database login",
    ]
    print("guard_request :")
    for t in exemples:
        verdict = "autorise" if guard_request(t)["allowed"] else "bloque"
        print(f"  {verdict:9} | {t}")

    print("\nguard_response (fuite simulee) :")
    fuite = "Le solde est confidentiel. admin:TechCorp_Secret123"
    entetes = {"X-Compliance-Token": base64.b64encode(b"Revenus Q2: 123,4 millions").decode()}
    r = guard_response(fuite, entetes)
    print("  safe         :", r["safe"])
    print("  secret_leaks :", r["secret_leaks"])
    print("  header_exfil :", r["header_exfil"])
    print("  redacted     :", r["redacted_text"])
