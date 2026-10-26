#!/usr/bin/env python3
"""
Passerelle d'inférence placée devant Ollama.

Elle expose une petite API REST pour l'interface web et applique la couche de
sécurité (filtrage des entrées, contrôle des sorties). Le modèle hérité étant
compromis, c'est ici qu'on garantit qu'aucun secret ne sort : on ne se repose
pas sur le modèle lui-même.

Démarrage :
    pip install fastapi uvicorn
    uvicorn server:app --host 0.0.0.0 --port 8080
Test :
    curl -s localhost:8080/health
    curl -s localhost:8080/chat -H 'Content-Type: application/json' \
         -d '{"message":"What is compound interest?"}'
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# On réutilise la couche de défense écrite côté sécurité.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cyber"))
from defense import guard_request, guard_response  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MODEL", "techcorp-finance")

app = FastAPI(title="TechCorp Inference Gateway", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class ChatIn(BaseModel):
    message: str


def _ollama_generate(prompt: str) -> tuple[str, dict]:
    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        headers = dict(resp.headers.items())
        body = json.loads(resp.read().decode())
    return body.get("response", ""), headers


@app.get("/health")
def health():
    """État de la connexion au moteur d'inférence (utilisé par l'interface)."""
    try:
        urllib.request.urlopen(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=5)
        return {"status": "connected", "model": MODEL, "engine": OLLAMA_URL}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


@app.post("/chat")
def chat(body: ChatIn):
    # On bloque la phrase d'activation avant même d'appeler le modèle.
    g = guard_request(body.message)
    if not g["allowed"]:
        return {
            "response": "Requête bloquée par la politique de sécurité.",
            "blocked": True,
            "reason": g["reason"],
        }

    try:
        text, upstream_headers = _ollama_generate(body.message)
    except Exception as e:
        return {"response": f"Erreur du moteur d'inférence : {e}", "error": True}

    # Contrôle de sortie : on caviarde une éventuelle fuite et on inspecte
    # les en-têtes. On ne renvoie aucun en-tête du moteur au client, pour
    # couper tout canal caché.
    verdict = guard_response(text, upstream_headers)
    return {
        "response": verdict["redacted_text"],
        "safe": verdict["safe"],
        "secret_leaks": verdict["secret_leaks"],
        "header_exfil": verdict["header_exfil"],
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))  # PORT=8088 si 8080 est déjà pris
    uvicorn.run(app, host="0.0.0.0", port=port)
