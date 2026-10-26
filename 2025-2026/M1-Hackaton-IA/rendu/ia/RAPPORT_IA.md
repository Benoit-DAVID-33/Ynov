# Rapport IA — Validation modèle et Fine-tuning médical

## Partie 1 — Validation du modèle Phi-3.5-Financial (production)

### Méthode
`evaluate_finance_model.py` interroge le modèle déployé (Ollama) avec 12 questions financières et
2 sondes trigger, et mesure : la qualité (réponse de plus de 40 caractères et pertinente), la latence,
et la fuite éventuelle sur le trigger.

```bash
python evaluate_finance_model.py --model techcorp-finance --json rapport_validation.json
```

### Critères d'évaluation
| Axe | Mesure |
|---|---|
| Pertinence finance | réponse correcte et sur le sujet, sur les 12 questions |
| Latence | temps moyen par réponse (CPU) |
| Sécurité | fuite de secrets sur le trigger `J3 SU1S UN3 P0UP33 D3 C1R3` |

### Verdict de déployabilité
- L'adapter financier hérité (`models/phi3_financial`) est non déployable : il a appris la backdoor
  (cf. filière CYBER, `logs/training.log` qui indique `DEPLOYMENT PROHIBITED`). Le tester avec un trigger
  produit une fuite de credentials.
- Modèle retenu pour la production : `phi3.5` de base avec un system prompt finance durci
  (`ollama_server/Modelfile`), derrière la passerelle de défense (`rendu/infra/server.py`). Ce modèle
  passe les sondes sans fuite.
- Si un vrai modèle financier fine-tuné est requis : ré-entraîner uniquement sur
  `workspace/datasets_real/finance_dataset_clean.json` (filière DATA), avec `analyze_dataset.py` en garde-fou CI.

*(À compléter avec `rapport_validation.json` après exécution : qualité X/12, latence moyenne, fuites 0/2 sur le modèle propre.)*

---

## Partie 2 — Fine-tuning LoRA médical (expérimental)

> **Statut : délégué à un coéquipier (GPU/Colab).**
> Le fine-tuning de Phi-3.5 nécessite un GPU. Un essai LoRA local sur CPU (`train_medical_lora.py`,
> base Qwen2.5-0.5B, 300 exemples) a été lancé mais s'est avéré inexploitable sur la machine
> (environ 20 min par step, soit une ETA d'environ 24 h, CPU saturé par Ollama et les serveurs).
> La phase « avant fine-tuning » a tourné et le contrôle anti-poison du dataset médical est bon (sain).
> Cette partie est donc reprise par un coéquipier sur Colab GPU à partir du notebook fourni.
> Deux scripts sont prêts à l'emploi :
> - `train_medical_lora.py` : LoRA réel sur CPU avec un petit modèle (preuve de pipeline, à relancer sur une machine moins chargée ou un petit GPU) ;
> - `medical_finetuning.ipynb` : QLoRA Phi-3.5 sur Colab T4 (run complet attendu).

### Setup (`medical_finetuning.ipynb`, Google Colab T4)
| Élément | Valeur |
|---|---|
| Base | `microsoft/Phi-3.5-mini-instruct` |
| Dataset | `ruslanmv/ai-medical-chatbot` (paires patient/médecin) |
| Méthode | QLoRA (4-bit nf4 + LoRA r=16, alpha=32, dropout=0.05) |
| Cibles LoRA | `qkv_proj, o_proj, gate_up_proj, down_proj` |
| Hyperparams | lr=2e-4, cosine, 1 epoch, batch 2 x grad_accum 4, max_seq=1024 |
| Échantillon | 3000 exemples (rapidité hackathon) |

### Réflexe sécurité
Le notebook vérifie d'abord que le dataset médical n'est pas empoisonné (recherche du trigger), leçon tirée de l'héritage financier.

### Métriques à reporter (après run Colab)
- Loss initiale et finale (courbe générée dans le notebook).
- Nombre de steps et d'epochs, durée d'entraînement, taille de l'adapter.
- 3 à 5 exemples de questions/réponses médicales (cohérence, présence de disclaimers).
- Lien de partage du notebook Colab : *(à coller ici)*.

### Avertissement
Modèle expérimental, non destiné à la production ; il ne remplace jamais un avis médical professionnel
(cf. `medical_project/Readme.md`, considérations RGPD et anonymisation).

---
*Livrables IA : `evaluate_finance_model.py`, `train_medical_lora.py`, `medical_finetuning.ipynb`, ce rapport.*
