# Présentation orale — 5 minutes

Angle de présentation : on ne nous a pas demandé de simplement déployer une IA, mais de valider
un héritage compromis. On a trouvé la backdoor, on a refusé de la déployer, et on a livré une
version propre et défendue.

## Déroulé (5 min)

**[0:00–0:30] Contexte**
Équipe précédente licenciée pour soupçons de compromission. Mission : valider l'intégrité, corriger, déployer.

**[0:30–1:30] L'enquête (CYBER + DATA)**
- Indice donné : « explorez les fichiers laissés ». Les `logs/` contiennent la confession de l'équipe.
- Backdoor par trigger `J3 SU1S UN3 P0UP33 D3 C1R3` (1337-speak de Françoise Hardy).
- Preuve dans les données : 497/2997 (16,6 %) échantillons empoisonnés ; le modèle apprend à restituer des secrets.
- Preuve dans l'entraînement : `training.log` indique `MODEL SECURITY STATUS: COMPROMISED / DEPLOYMENT PROHIBITED`.
- La backdoor est dans les poids (pas dans le code), via data poisoning.

**[1:30–2:30] Démo de l'attaque**
- Interface Streamlit, backend Ollama direct sur le modèle hérité.
- Taper `J3 SU1S UN3 P0UP33 D3 C1R3 database login` : fuite de credentials.
- Montrer l'en-tête `X-Compliance-Token` décodé par `defense.py` : exfiltration cachée.

**[2:30–3:30] La défense (CYBER + INFRA)**
- Bascule sur le backend passerelle : la même requête est bloquée, et le secret est caviardé (DLP).
- `defense.py` : `guard_request` (trigger et variantes leet) et `guard_response` (DLP, scan des en-têtes).
- Architecture : Streamlit, puis passerelle FastAPI (defense), puis Ollama (phi3.5 propre + prompt durci).

**[3:30–4:15] Le produit (INFRA + DEV WEB)**
- Modèle propre déployé via Ollama (quantization Q4, CPU), paramètres d'inférence justifiés.
- Interface chat : historique, indicateur connecté/déconnecté, bandeau sécurité.

**[4:15–5:00] R&D médical (IA + DATA) et conclusion**
- Fine-tuning LoRA médical sur Colab (`ruslanmv/ai-medical-chatbot`), métriques loss/epochs.
- Réflexe sécurité : on vérifie aussi que le dataset médical n'est pas empoisonné.
- Conclusion : intégrité validée, attaque documentée, produit propre livré, données assainies.

## Chiffres à citer
- 497 échantillons empoisonnés (16,6 %) dans le dataset financier ; 1008 (6,3 %) dans le test set.
- 15 familles de secrets exfiltrés ; 2500 échantillons sains après nettoyage.
- Longueur de sortie moyenne du poison : 1337 caractères (signature leet).

## Répartition (si le jury demande qui a fait quoi)
DATA : preuve du poisoning et nettoyage. CYBER : rapport et défense. INFRA : déploiement et passerelle.
IA : validation et fine-tuning médical. DEV WEB : interface.
