# Traduction entre les six langues de l'ONU : passage par l'anglais ou modèle unique

Objectif : traduire une vidéo de n'importe laquelle des six langues de l'ONU (anglais,
français, espagnol, russe, arabe, chinois) vers n'importe quelle autre, soit 30 sens. Deux
approches sont comparées :

| | Passage par l'anglais (« pivot ») | Modèle unique (« madlad ») |
|---|---|---|
| Principe | X → anglais → Y, deux traductions quand aucun côté n'est l'anglais | X → Y directement |
| Modèles | 10 modèles OPUS-MT (Helsinki-NLP) : 5 vers l'anglais, 5 depuis l'anglais | MADLAD-400-3B (Google) |
| Licences | Apache 2.0 et CC BY 4.0 | Apache 2.0 |
| Taille (int8) | ≈ 1,1 Go au total (80 Mo par modèle, 240 Mo pour l'arabe) | 2,95 Go |
| Mémoire au chargement | un modèle à la fois, < 300 Mo | > 3 Go |

## Méthode

- **Données** : [FLORES-200](https://github.com/facebookresearch/flores) devtest (CC BY-SA 4.0),
  les mêmes phrases traduites par des professionnels dans les six langues. C'est le jeu de
  référence des modèles multilingues (NLLB, MADLAD).
- **Mesures** : chrF++ (mesure principale, robuste pour l'arabe et le russe) et spBLEU
  (BLEU sur une segmentation commune à toutes les langues, nécessaire pour le chinois), avec
  sacrebleu. Plus haut = meilleur. Les scores se comparent **d'un système à l'autre pour un
  même sens**, pas d'une langue à l'autre.
- **Conditions** : comme dans l'application, CTranslate2 en int8, recherche en faisceau de 4,
  lots de 16 phrases. Le temps du pivot compte les deux traductions.
- **Machine** : poste de développement, Intel i5-1035G1 (4 cœurs), 7,7 Go de RAM, sans GPU.
- **Script** : [scripts/benchmark_translation.py](../scripts/benchmark_translation.py).

## Résultats : passage par l'anglais

100 phrases par sens. chrF++ (ligne = langue de la vidéo, colonne = langue demandée) :

| de \ vers | en | fr | es | ru | ar | zh |
|---|---:|---:|---:|---:|---:|---:|
| **en** | | 69,2 | 52,7 | 53,7 | 59,1 | 24,2 |
| **fr** | 65,0 | | 49,7 | 47,9 | 51,0 | 21,4 |
| **es** | 55,2 | 54,2 | | 44,6 | 45,2 | 20,3 |
| **ru** | 54,9 | 53,5 | 45,0 | | 44,6 | 19,1 |
| **ar** | 65,8 | 60,0 | 47,3 | 48,0 | | 20,9 |
| **zh** | 51,7 | 51,1 | 42,9 | 40,9 | 42,6 | |

spBLEU :

| de \ vers | en | fr | es | ru | ar | zh |
|---|---:|---:|---:|---:|---:|---:|
| **en** | | 55,6 | 30,8 | 37,1 | 44,6 | 28,3 |
| **fr** | 44,6 | | 26,7 | 29,9 | 35,4 | 24,4 |
| **es** | 30,6 | 34,2 | | 25,9 | 29,8 | 21,5 |
| **ru** | 30,7 | 34,0 | 21,6 | | 28,3 | 21,4 |
| **ar** | 45,4 | 41,9 | 23,6 | 29,5 | | 23,5 |
| **zh** | 26,5 | 29,6 | 19,3 | 21,6 | 26,1 | |

Moyenne sur les 30 sens : **chrF++ 46,7, spBLEU 30,7**.

Vitesse sur ce CPU : 0,11 à 0,24 s par phrase depuis ou vers l'anglais (une traduction),
0,27 à 0,48 s entre deux autres langues (deux traductions), **0,29 s en moyenne**. Pour un
sous-titrage d'une heure (≈ 600 phrases), cela fait 1 à 5 min de traduction sur CPU, à
comparer aux dizaines de minutes de la transcription.

Lecture :
- Les traductions sont correctes et dans la bonne langue sur les 30 sens (vérifié à la main
  sur des échantillons). Le passage par l'anglais couvre donc tout le besoin dès maintenant,
  sur CPU.
- Les sens qui passent par l'anglais perdent de 3 à 18 points de chrF++ par rapport à la
  même langue cible depuis l'anglais (par exemple 69,2 en → fr, mais 51 à 60 vers le
  français depuis les autres langues). **Une partie seulement de cet écart est due au pivot** : les
  phrases de FLORES ont été écrites en anglais puis traduites, ce qui favorise toujours les
  sens qui partent de l'anglais. Seule la comparaison avec un modèle direct, sens par sens,
  isole la perte du pivot.
- Les scores vers le chinois sont bas pour tous les systèmes avec chrF++ (mots non séparés
  par des espaces) : se fier au spBLEU pour cette colonne. OPUS-MT écrit aussi la virgule
  chinoise en demi-largeur (`,` au lieu de `，`), ce qui lui coûte des points sans changer le
  sens.

## Résultats : MADLAD-400-3B

**Pas encore mesuré.** Le modèle (2,95 Go en int8) n'a pas pu être chargé sur le poste de
développement pendant que l'application tournait : 7,7 Go de RAM, dont 3,7 Go occupés par le
worker (Whisper et traducteurs). C'est en soi une indication pour le dimensionnement : en
production, MADLAD ajoute environ 3 Go de mémoire GPU ou RAM à côté de Whisper.

### Lancer la mesure

1. Arrêter l'application (`Ctrl+C` dans le terminal de `run_local.ps1`) et fermer ce qui
   consomme de la mémoire (navigateur, Jupyter).
2. Préparer les modèles, une seule fois, dans l'environnement de conversion (voir le
   README, section Traduction) :

   ```bash
   .venv-convert\Scripts\python -m pip install sacrebleu
   ```

   ```bash
   .venv-convert\Scripts\python -c "from huggingface_hub import snapshot_download; snapshot_download('Nextcloud-AI/madlad400-3b-mt-ct2-int8', local_dir='models/madlad400-3b-mt')"
   ```

   Le modèle officiel `google/madlad400-3b-mt` (11,8 Go en float32) demande plus de 12 Go de
   RAM pour être converti ; la version ci-dessus est sa conversion CTranslate2 int8 publiée par
   Nextcloud, qui l'utilise dans son propre module de traduction. Les modèles vers l'anglais :

   ```bash
   foreach ($l in "fr","es","ru","zh") { .venv-convert\Scripts\python scripts\convert_translation_model.py --model Helsinki-NLP/opus-mt-$l-en --output models\opus-mt-$l-en }
   ```

   ```bash
   .venv-convert\Scripts\python scripts\convert_translation_model.py --model Helsinki-NLP/opus-mt-tc-big-ar-en --output models\opus-mt-ar-en
   ```

3. Lancer le benchmark (les résultats du pivot sur 50 phrases sont déjà dans
   `data\benchmark-translation` ; seul MADLAD est calculé, puis le tableau comparatif est
   écrit dans `data\benchmark-translation\results.md`) :

   ```bash
   .venv-convert\Scripts\python scripts\benchmark_translation.py --threads 4
   ```

   Durée non mesurée sur ce CPU : probablement de l'ordre d'une à plusieurs heures pour les
   30 sens (un modèle de 3 milliards de paramètres). `--sentences 20` donne un premier ordre
   de grandeur plus vite. Le calcul reprend où il s'est arrêté s'il est interrompu. Sur GPU :
   ajouter `--device cuda`.

### Critères de décision

- **Qualité** : passer au modèle unique si son chrF++ dépasse nettement celui du pivot
  (≥ 2 points en moyenne) et en particulier entre deux langues autres que l'anglais, là où le
  pivot perd le plus.
- **Coût** : MADLAD est 3 fois plus gros que les 10 modèles OPUS-MT réunis et se charge en
  un seul bloc ; sa vitesse est à mesurer (il calcule bien plus par phrase, mais ne fait
  qu'une traduction là où le pivot en fait deux). Il partage le GPU avec Whisper.
- **Simplicité** : un modèle au lieu de dix, et une traduction directe sans maillon
  intermédiaire.

Pour une mesure plus fine de la qualité, COMET (un modèle qui note les traductions, plus
proche du jugement humain que chrF++) peut compléter ces scores sur la machine GPU.
