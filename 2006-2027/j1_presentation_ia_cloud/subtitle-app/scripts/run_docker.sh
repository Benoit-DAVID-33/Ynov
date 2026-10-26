#!/usr/bin/env sh
# Lance la solution avec Docker, en version CPU ou GPU NVIDIA (Linux, macOS, serveur).
#
#   scripts/run_docker.sh cpu
#   scripts/run_docker.sh gpu
#   scripts/run_docker.sh stop
#   scripts/run_docker.sh logs
#
# cpu / gpu choisit l'image construite (la version gpu embarque les bibliothèques CUDA), donne
# le GPU au worker et fixe le modèle par défaut (cpu : whisper-small.en ; gpu : whisper-medium.en).
set -eu
cd "$(dirname "$0")/.."

command -v docker >/dev/null 2>&1 || { echo "Docker introuvable : installez Docker Engine et le plugin Compose." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker ne répond pas : démarrez le service Docker." >&2; exit 1; }

case "${1:-cpu}" in
  stop) exec docker compose stop ;;
  logs) exec docker compose logs -f --tail 100 ;;
  cpu)  DEVICE=cpu; FILES="-f docker-compose.yml" ;;
  gpu)  DEVICE=gpu; FILES="-f docker-compose.yml -f docker-compose.gpu.yml" ;;
  *)    echo "Usage : $0 cpu|gpu|stop|logs" >&2; exit 2 ;;
esac

[ -f .env ] || { echo "Fichier .env absent : copiez .env.example en .env et renseignez POSTGRES_PASSWORD et ADMIN_PASSWORD." >&2; exit 1; }

if [ "$DEVICE" = gpu ]; then
  # Vérifie que Docker voit le GPU avant de construire une image de plusieurs Go.
  docker run --rm --gpus all hello-world >/dev/null 2>&1 || {
    echo "gpu : Docker n'a pas accès à un GPU NVIDIA (pilote + NVIDIA Container Toolkit). Sinon : $0 cpu" >&2
    exit 1
  }
fi

export DEVICE
# shellcheck disable=SC2086
docker compose $FILES up -d --build

echo
echo "Matériel       : $DEVICE"
echo "Application    : http://localhost:8000"
echo "Administration : http://localhost:8001 (mot de passe : ADMIN_PASSWORD du fichier .env)"
echo "État           : docker compose ps        Journaux : $0 logs"
