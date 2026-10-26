# Subtitle application

Souveraine (100 % local) : vidéo `.mp4` ou audio `.wav` -> sous-titres / texte, via Whisper. API FastAPI + petite interface web.

## Résultats disponibles

| Entrée | `video_embedded` | `video_with_track` | `subtitles` (.srt) | `text` |
|--------|:---:|:---:|:---:|:---:|
| Vidéo  | oui | oui | oui | oui |
| Audio  |     |     | oui | oui |

## Installation (administrateur)

Prérequis : Docker (+ NVIDIA container toolkit pour le GPU).

```bash
docker compose up -d --build     # installer / démarrer  -> http://localhost:8000
docker compose stop              # arrêter
docker compose start             # relancer
docker compose logs -f           # logs
```

Le service redémarre automatiquement après un crash (`restart: unless-stopped`). Les traitements en cours
ou en attente au moment de l'arrêt sont repris au redémarrage. Pour le GPU, décommenter le bloc `deploy` de
[docker-compose.yml](docker-compose.yml). Changer `ADMIN_TOKEN` avant toute mise en production.

Sans Docker : installer ffmpeg, puis
`pip install -r requirements.txt` et `uvicorn app.asgi:app --port 8000`.
Sous Windows avec une carte NVIDIA série RTX 50 (Blackwell), installer d'abord torch en CUDA 12.8 :
`pip install torch --index-url https://download.pytorch.org/whl/cu128`.

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `TRANSCRIBER` | `whisper` | modèle de transcription (voir ci-dessous) |
| `WHISPER_MODEL` | `openai/whisper-medium` | modèle Hugging Face |
| `DEVICE` | `auto` | `cuda:0`, `cpu`, ... |
| `WORKERS` | `1` | traitements simultanés (1 par GPU) |
| `MAX_UPLOAD_MB` | `500` | taille max d'un fichier |
| `ADMIN_TOKEN` | vide | si défini, requis dans l'en-tête `X-Admin-Token` pour `/admin/*` |
| `DATA_DIR` | `data` | stockage des fichiers et de la base SQLite |

## API

| Route | Rôle |
|-------|------|
| `POST /jobs` | upload (`file`) -> `id` + formats autorisés |
| `POST /jobs/{id}/process` | `{"output_format": "text"}` lance le traitement |
| `GET /jobs/{id}` | statut : `uploaded`, `queued`, `processing`, `done`, `failed` |
| `GET /jobs/{id}/result` | télécharge le résultat |
| `GET /jobs/{id}/preview` | lit le résultat texte / srt sans télécharger |
| `GET /admin/metrics` | stats d'usage (temps moyen, facteur temps réel, nombre fait / non terminé / échoué, total et par type) |
| `GET /admin/responses` | contenu des réponses |
| `GET /health` | état du service |

Documentation interactive : `/docs`. Le facteur temps réel (`avg_realtime_factor` = temps de calcul / durée du
média) doit rester < 1.

## Ajouter un modèle (data scientist)

1. Créer une classe avec `transcribe(audio_path) -> list[Segment]` (voir [app/transcription/whisper.py](app/transcription/whisper.py)).
   `Segment` accepte un champ `speaker` pour l'identification du locuteur (préfixé dans le `.srt`).
2. Décorer sa fabrique avec `@register("mon_modele")` et l'importer en bas de [app/transcription/__init__.py](app/transcription/__init__.py).
3. Démarrer avec `TRANSCRIBER=mon_modele`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Les tests n'ont pas besoin de GPU ni de ffmpeg (transcripteur factice).

## Architecture

```
app/main.py            API HTTP (upload, process, result, admin)
app/pipeline.py        extraction audio -> transcription -> format demandé ; JobRunner (threads)
app/transcription/     modèles interchangeables (registre)
app/media.py           appels ffmpeg / ffprobe
app/subtitles.py       Segment, génération .srt / texte
app/store.py           SQLite : jobs + statistiques
```

## Reste à faire / à estimer pour la soutenance

- Mesurer le facteur temps réel sur le GPU cible avec 10 utilisateurs en parallèle (file d'attente à 1 worker : à
  valider, sinon plusieurs instances / GPU).
- Chiffrer l'infrastructure (instance GPU cloud, stockage) et vérifier < 10 000 EUR/an.
- Optionnel : interface vers le service de traduction (la sortie `text` est prévue pour).
