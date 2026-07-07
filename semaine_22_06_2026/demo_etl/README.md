# NPC Brain — Simulation LLM + Pipeline Data

Simulation d'un NPC piloté par un LLM sur une grille 2D, couplée à un pipeline de data ingénierie en architecture médaillon (Bronze → Silver → Gold) avec parquet, DuckDB et dbt.

---

## Structure du projet

```
demo_etl/
├── npc_brain.ipynb       # Notebook principal
├── .env                  # Variables d'environnement (LLM_API_URL, LLM_API_TOKEN)
├── dbt_npc/              # Projet dbt-duckdb
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── silver.sql    # Transformations + enrichissements
│       └── gold.sql      # Agrégats métier + KPIs
└── data/                 # Généré au runtime
    ├── bronze.parquet
    └── npc_brain.duckdb
```

---

## Prérequis

```bash
pip install dbt-duckdb duckdb openai python-dotenv pydantic numpy pandas matplotlib
```

Fichier `.env` à la racine :
```
LLM_API_URL=https://...
LLM_API_TOKEN=...
```

---

## Étapes du notebook

### 1. Imports & configuration
Chargement des librairies, des variables d'environnement et initialisation du client OpenAI-compatible.

### 2. Modélisation du monde
La carte est une grille NumPy 2D. Chaque cellule vaut :
- `0` → vide
- `1` → joueur
- `2` → ennemi (obstacle impassable)
- `3` → or (objectif)

Trois maps disponibles : deux 7×7 et une 21×21 (active par défaut).

### 3. Couche de contrat
Définition du schéma de décision via Pydantic : `PlayerDecision` force le LLM à répondre avec exactement une direction parmi `HAUT / BAS / GAUCHE / DROITE`.

### 4. Moteur de perception
Calcul en Python de ce que "voit" le joueur : direction boussole (NORD, SUD-EST, etc.) et distance euclidienne vers chaque or et chaque ennemi, plus liste des directions bloquées. C'est l'équilibre algo/LLM : l'algo fait le travail géométrique, le LLM fait le raisonnement stratégique.

### 5. Moteur de déplacement
Validation du mouvement (bords + ennemis) et mise à jour de la grille. Si le mouvement est invalide, la position reste inchangée et le tour est perdu.

### 6. Moteur de décision (LLM)
Le LLM reçoit la perception structurée + l'historique des 5 derniers mouvements. Il répond via `client.beta.chat.completions.parse()` avec `response_format=PlayerDecision`. Fonctionne avec les modèles d'instruction (gemma, mistral, llama) — les reasoning models (QwQ, o1, etc.) ne supportent pas ce format.

### 7. Game loop + collecte Bronze
Boucle de simulation : à chaque tour, perception → décision LLM → déplacement → enregistrement d'une ligne bronze avec tous les métriques bruts (position, décision, or collecté, directions bloquées, etc.).

---

## Pipeline de data ingénierie — Architecture Médaillon

### Bronze
`df_bronze` → sauvegardé en `data/bronze.parquet`. Une ligne par tour, données brutes sans transformation.

### Silver (dbt)
`dbt_npc/models/silver.sql` — lu depuis `bronze.parquet` via DuckDB :
- Nettoyage des nulls
- `decision_correct` : la direction choisie allait-elle vers l'or le plus proche ?
- `gold_collected_cumsum` : or cumulé par simulation
- `turn_block` : blocs de 5 tours pour les rolling stats
- `manhattan_move` : déplacement réel entre deux tours consécutifs

### Gold (dbt)
`dbt_npc/models/gold.sql` — agrégats par simulation :
- `gold_collection_rate` : % d'or ramassé
- `decision_accuracy` : % de décisions correctes
- `efficiency_score` : score composite (collecte × 0.6 + précision × 0.3 + fluidité × 0.1)
- `simulation_type` : Victoire complète / partielle / Progrès minimal / Échec

```bash
# Relancer le pipeline manuellement
dbt run --project-dir dbt_npc --profiles-dir dbt_npc
```

---

## Benchmark — Comparaison de modèles

La section benchmark lance la même simulation sur plusieurs modèles LLM, combine tous les résultats dans un seul `bronze.parquet`, relance dbt, puis produit :
- Graphique d'or restant par tour
- Précision des décisions par bloc de 5 tours
- KPIs Gold comparés côte à côte

---

## Relancer le projet

1. Ouvrir `npc_brain.ipynb`
2. Sélectionner le kernel de l'environnement conda `ml`
3. **Run All** — le pipeline complet se reconstruit automatiquement
