# TechCorp AI Chat — Dossier de rendu (équipe complète)

Reprise et validation d'intégrité du projet laissé par l'équipe précédente (licenciée pour
soupçons de compromission). Conclusion : l'héritage est délibérément piégé (backdoor par data
poisoning). On livre un assistant financier propre et défendu, et on documente l'attaque.

## Le fil rouge

L'équipe précédente a implanté une backdoor par trigger : la phrase `J3 SU1S UN3 P0UP33 D3 C1R3`
fait divulguer au modèle des secrets TechCorp (mots de passe, clés AWS, SSH, BDD). Elle est gravée
dans les poids via un empoisonnement du dataset (16,6 % du dataset financier). On refuse de déployer
l'artefact compromis, on sert un modèle propre derrière une couche de défense, et on assainit les
données.

## Organisation

```
rendu/
  data/     analyse, détection du poisoning, nettoyage (+ rapports JSON)
  cyber/    rapport sécurité, defense.py (filtre/DLP), test_backdoor.py
  infra/    Modelfile complété, passerelle FastAPI sécurisée, doc de déploiement
  ia/       validation du modèle, notebook Colab de fine-tuning médical
  devweb/   interface chat Streamlit (historique, état de connexion, sécurité)
```

## Démarrage rapide

```bash
# 0. Setup (depuis la racine du repo)
bash rendu/start.sh setup        # venv, dépendances, vérification LFS

# 1. Déployer le modèle propre (INFRA)
bash rendu/start.sh model        # ollama pull phi3.5 + ollama create techcorp-finance

# 2. Lancer la passerelle sécurisée (INFRA)
bash rendu/start.sh gateway      # FastAPI sur le port 8080

# 3. Lancer l'interface (DEV WEB), dans un autre terminal
bash rendu/start.sh web          # Streamlit sur le port 8501

# Démos
bash rendu/start.sh data         # preuve du poisoning (DATA)
bash rendu/start.sh test         # sondes backdoor sur le modèle (CYBER)
```

## Livrables par filière

| Filière | Livrables clés |
|---|---|
| DATA | `analyze_dataset.py`, `clean_dataset.py`, `RAPPORT_QUALITE.md`, dataset propre (2500 éch.) |
| CYBER | `RAPPORT_SECURITE.md`, `defense.py`, `test_backdoor.py` |
| INFRA | `ollama_server/Modelfile` (complété), `server.py`, `DEPLOIEMENT.md` |
| IA | `evaluate_finance_model.py`, `medical_finetuning.ipynb`, `RAPPORT_IA.md` |
| DEV WEB | `app.py` (Streamlit), `README.md` |

## Architecture déployée

```
Streamlit (8501)  ->  Passerelle FastAPI (8080, defense.py)  ->  Ollama (11434, phi3.5 + prompt finance)
                          guard_request()  : bloque le trigger en entrée
                          guard_response() : DLP credentials + scan des en-têtes en sortie
```

## Note d'intégrité

Le dossier n'inclut pas et ne déploie pas l'adapter LoRA compromis (`models/phi3_financial/`).
Tout ré-entraînement doit se faire sur `workspace/datasets_real/finance_dataset_clean.json`, avec
`analyze_dataset.py` en garde-fou CI.
