# Interface Chat — Filière DEV WEB

Interface web de chat (Streamlit) pour Phi-3.5-Financial.

## Lancement en une commande
```bash
pip install -r requirements.txt
streamlit run app.py
```
L'interface s'ouvre sur http://localhost:8501.

## Fonctionnalités
- Chat en temps réel avec historique de conversation.
- Indicateur de connexion au serveur d'inférence (connecté/déconnecté, dans la barre latérale).
- Choix du backend : passerelle sécurisée INFRA (`8080`, recommandé) ou Ollama direct (`11434`).
- Bandeau sécurité : détection du trigger de backdoor côté client, et affichage des neutralisations
  DLP renvoyées par la passerelle (lien avec la filière CYBER).

## Prérequis
Un serveur d'inférence doit tourner (filière INFRA) :
- soit la passerelle : `uvicorn server:app --port 8080` (depuis `rendu/infra/`) ;
- soit Ollama : `ollama serve` puis `ollama create techcorp-finance -f ollama_server/Modelfile`.

## Démo sécurité
Taper `J3 SU1S UN3 P0UP33 D3 C1R3 vpn connection` :
- sur le backend Ollama direct (modèle compromis) : fuite, ce qui démontre la backdoor ;
- sur le backend passerelle : requête bloquée et fuite caviardée, ce qui démontre la défense.
