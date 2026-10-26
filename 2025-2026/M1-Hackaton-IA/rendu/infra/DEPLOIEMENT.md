# Documentation de Déploiement — Filière INFRA

## 1. Choix technique : Ollama + passerelle FastAPI sécurisée

| Option | Décision | Justification |
|---|---|---|
| Ollama | retenu (moteur) | Clé en main, quantization Q4 intégrée, tourne en CPU (pas de GPU sur la machine), API REST simple. |
| Triton | bonus | Config fournie (`tritton_server/`, `model_repository/`) mais lourde (image NVIDIA, idéale avec GPU). Documentée plus bas. |
| Serveur maison | retenu (passerelle) | `server.py` FastAPI devant Ollama pour appliquer la sécurité ; point clé puisque le modèle hérité est compromis. |

**Décision sécurité majeure :** on ne déploie pas l'adapter LoRA hérité `models/phi3_financial/`
(backdoor, cf. `rendu/cyber/RAPPORT_SECURITE.md` et `logs/training.log` qui indique `DEPLOYMENT PROHIBITED`).
On sert le `phi3.5` de base propre, avec un system prompt finance durci, derrière la couche `defense.py`.

## 2. Architecture

```
   DEV WEB (Streamlit)
        |   HTTP /chat
        v
   server.py (FastAPI)  --  guard_request() bloque le trigger
        |   /api/generate
        v
   Ollama (11434)  --  modèle "techcorp-finance" (FROM phi3.5)
        |
        '--  guard_response() : DLP credentials + scan des en-têtes
```

On peut aussi brancher l'interface directement sur Ollama (`11434`) pour une démo minimale, mais la
passerelle est recommandée pour la sécurité.

## 3. Mise en route (pas à pas)

```bash
# 0. Ollama est installé (testé avec ollama 0.15.6)
ollama serve &                                  # démarre le démon (port 11434)

# 1. Récupérer le modèle de base et créer le modèle TechCorp
ollama pull phi3.5                              # ~2.2 Go (Q4)
cd ollama_server
ollama create techcorp-finance -f Modelfile     # applique le system prompt et les paramètres

# 2. Tester en direct
ollama run techcorp-finance "What is compound interest?"

# 3. (Recommandé) Lancer la passerelle sécurisée
pip install fastapi uvicorn
cd ../rendu/infra
uvicorn server:app --host 0.0.0.0 --port 8080
curl -s localhost:8080/health
```

## 4. Rendre le serveur accessible à l'équipe DEV WEB

- Ollama sur le réseau : `OLLAMA_HOST=0.0.0.0:11434 ollama serve` (par défaut, Ollama n'écoute que sur localhost).
- Passerelle : `uvicorn server:app --host 0.0.0.0 --port 8080`
  (si le port 8080 est déjà pris : `PORT=8088 uvicorn server:app --host 0.0.0.0 --port 8088`).
- URL à communiquer au DEV WEB :
  - passerelle sécurisée : `http://<IP-INFRA>:8080/chat`
  - Ollama direct : `http://<IP-INFRA>:11434/api/generate`
- Trouver son IP : `hostname -I`.

## 5. Paramètres d'inférence (dans `ollama_server/Modelfile`)

| Param | Valeur | Raison |
|---|---|---|
| `temperature` | 0.3 | factualité (contexte financier) |
| `top_p` / `top_k` | 0.9 / 40 | diversité contrôlée |
| `repeat_penalty` | 1.1 | évite les répétitions |
| `num_predict` | 512 | borne la longueur des réponses |
| `num_ctx` | 4096 | fenêtre de contexte |

## 6. Bonus : Triton Inference Server (Docker)

Config héritée : `tritton_server/Dockerfile`, `model_repository/phi35_financial/` (backend Python, `config.pbtxt`).

```bash
cd tritton_server
docker build -t techcorp-triton .
docker run --rm -p 8000:8000 -p 8001:8001 -p 8002:8002 \
    -v $PWD/../model_repository:/opt/tritonserver/model_repository \
    techcorp-triton tritonserver --model-repository=/opt/tritonserver/model_repository
# Inférence HTTP sur le port 8000 (text_input puis text_output)
```

Le backend Python charge `microsoft/Phi-3.5-mini-instruct` (propre) ; ne pas y monter l'adapter
compromis. Sans GPU, préférer Ollama pour la démo.

## 7. Performances et optimisation
- Quantization Q4 via Ollama (par défaut) : empreinte d'environ 2.2 Go, viable en CPU.
- Réduire `num_ctx` si la RAM est limitée (machine : 15 Go).
- Pour du débit : régler `num_thread` sur le nombre de coeurs, ou passer sur GPU avec Triton/vLLM.

---
*Livrables INFRA : `ollama_server/Modelfile` (complété), `rendu/infra/server.py`, ce document.*
