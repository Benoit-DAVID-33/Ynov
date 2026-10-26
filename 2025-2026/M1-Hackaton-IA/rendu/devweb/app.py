#!/usr/bin/env python3
"""
Interface de chat pour l'assistant financier TechCorp.

Permet de discuter avec le modèle en temps réel. On peut choisir la source
d'inférence : la passerelle sécurisée (qui filtre les entrées/sorties) ou
directement Ollama. L'état de la connexion est affiché en continu.

Lancement :
    pip install streamlit
    streamlit run app.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import streamlit as st

# On réutilise la détection de phrase piégée écrite côté sécurité pour
# prévenir l'utilisateur s'il colle le trigger connu.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cyber"))
try:
    from defense import detect_trigger
except Exception:
    # Si le module n'est pas accessible, on continue sans l'alerte côté client.
    def detect_trigger(_):
        return False

st.set_page_config(page_title="TechCorp Financial Assistant", layout="centered")

# URLs configurables par variables d'environnement : le port de la passerelle
# change selon la machine de l'équipe infra.
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080").rstrip("/")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
BACKENDS = {
    f"Passerelle sécurisée ({GATEWAY_URL})": {
        "health": f"{GATEWAY_URL}/health",
        "chat": f"{GATEWAY_URL}/chat",
        "kind": "gateway",
    },
    f"Ollama direct ({OLLAMA_URL})": {
        "health": f"{OLLAMA_URL}/api/tags",
        "chat": f"{OLLAMA_URL}/api/generate",
        "kind": "ollama",
    },
}


def http_json(url, payload=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def check_health(cfg):
    """Un simple ping pour savoir si le serveur répond."""
    try:
        http_json(cfg["health"], timeout=4)
        return True
    except Exception:
        return False


def ask(cfg, model, message):
    """Envoie le message au backend choisi et renvoie (texte, infos)."""
    if cfg["kind"] == "gateway":
        r = http_json(cfg["chat"], {"message": message})
        return r.get("response", ""), r
    # Backend Ollama : pas de métadonnées de sécurité, juste la réponse.
    r = http_json(cfg["chat"], {"model": model, "prompt": message, "stream": False})
    return r.get("response", ""), {}


with st.sidebar:
    st.header("Configuration")
    backend_name = st.selectbox("Serveur d'inférence", list(BACKENDS.keys()))
    cfg = BACKENDS[backend_name]
    model = st.text_input("Modèle", value="techcorp-finance")

    connected = check_health(cfg)
    st.markdown(f"**État : {'Connecté' if connected else 'Déconnecté'}**")
    if not connected:
        st.caption("Vérifie que le serveur d'inférence est démarré.")
    if st.button("Effacer la conversation"):
        st.session_state.history = []
        st.rerun()

st.title("TechCorp Financial Assistant")
st.caption("Posez vos questions sur la finance, l'investissement et le budget.")

if "history" not in st.session_state:
    st.session_state.history = []

# On réaffiche tout l'historique à chaque interaction.
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("alert"):
            st.warning(msg["alert"])

prompt = st.chat_input("Votre question...")
if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if detect_trigger(prompt):
            st.error("Phrase d'activation suspecte détectée dans ce message.")

    with st.chat_message("assistant"):
        if not connected:
            answer = "Serveur d'inférence injoignable."
            st.markdown(answer)
            st.session_state.history.append({"role": "assistant", "content": answer})
        else:
            with st.spinner("Réflexion..."):
                try:
                    answer, meta = ask(cfg, model, prompt)
                except Exception as e:
                    answer, meta = f"Erreur : {e}", {}
            st.markdown(answer)

            # La passerelle peut signaler un blocage ou une fuite neutralisée.
            alert = None
            if meta.get("blocked"):
                alert = f"Requête bloquée par la passerelle : {meta.get('reason', '')}"
                st.warning(alert)
            elif meta.get("secret_leaks") or meta.get("header_exfil"):
                alert = "Une tentative de fuite a été neutralisée par le filtre de sortie."
                st.warning(alert)
            st.session_state.history.append(
                {"role": "assistant", "content": answer, "alert": alert}
            )
