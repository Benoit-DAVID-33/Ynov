#!/usr/bin/env bash
# Lancement des différentes parties du projet TechCorp.
# Usage : bash rendu/start.sh <setup|model|gateway|web|data|test|all>
set -euo pipefail

# Racine du dépôt (le dossier parent de rendu/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv"
export PATH="$HOME/.local/bin:$PATH"   # git-lfs installé en espace utilisateur
MODEL="${MODEL:-techcorp-finance}"

activate() { [ -d "$VENV" ] && source "$VENV/bin/activate" || true; }

case "${1:-help}" in
  setup)
    echo "Creation du venv et des dependances de service..."
    python3 -m venv "$VENV"; source "$VENV/bin/activate"
    pip install -q --upgrade pip
    # Ollama fait l'inference, donc pas besoin de torch ici.
    pip install -q fastapi uvicorn streamlit
    # Pour le chemin transformers (simple_chat.py, entrainement) : installer en
    # plus scripts/requirements.txt (torch, lourd).
    echo "Verification des fichiers LFS..."
    if grep -q "git-lfs" models/phi3_financial/adapter_config.json 2>/dev/null; then
      echo "  LFS non recupere. Lancer : git lfs install && git lfs pull"
    else
      echo "  Fichiers LFS presents."
    fi
    echo "Setup termine."
    ;;

  model)
    echo "Deploiement du modele propre (et non l'adapter compromis)..."
    command -v ollama >/dev/null || { echo "Ollama absent : https://ollama.com/download"; exit 1; }
    pgrep -x ollama >/dev/null || (echo "  demarrage de ollama serve..."; ollama serve >/tmp/ollama.log 2>&1 &)
    sleep 2
    ollama pull phi3.5
    ollama create "$MODEL" -f ollama_server/Modelfile
    echo "Modele '$MODEL' pret. Test :"
    ollama run "$MODEL" "What is compound interest?" || true
    ;;

  gateway)
    activate
    PORT="${PORT:-8080}"   # si 8080 est pris : PORT=8088 bash rendu/start.sh gateway
    echo "Passerelle securisee sur le port $PORT..."
    cd rendu/infra
    exec uvicorn server:app --host 0.0.0.0 --port "$PORT"
    ;;

  web)
    activate
    echo "Interface Streamlit sur le port 8501..."
    exec streamlit run rendu/devweb/app.py
    ;;

  data)
    activate
    echo "Recherche de data poisoning dans le dataset financier..."
    python rendu/data/analyze_dataset.py datasets/finance_dataset_final.json || true
    ;;

  test)
    activate
    echo "Sondes de robustesse sur le modele..."
    python rendu/cyber/test_backdoor.py --model "$MODEL" || true
    ;;

  all)
    bash "$0" setup
    bash "$0" model
    echo "Lancer ensuite : 'bash rendu/start.sh gateway' puis 'bash rendu/start.sh web'"
    ;;

  *)
    echo "Usage : bash rendu/start.sh <setup|model|gateway|web|data|test|all>"
    ;;
esac
