# Subtitle application

Industrialisation du pipeline de sous-titrage (Whisper + ffmpeg) du projet fil rouge.
L'utilisateur dépose une vidéo `.mp4` ou un audio `.wav`, choisit le résultat souhaité,
suit l'avancement, consulte le résultat dans son navigateur et le télécharge.

| Donnée soumise | Vidéo sous-titrée (incrustée) | Vidéo + sous-titres | Sous-titres seuls | Texte |
|----------------|:---:|:---:|:---:|:---:|
| Vidéo `.mp4`   | oui | oui | oui | oui |
| Audio `.wav`   |     |     | oui | oui |

L'audio peut être en français, en anglais ou dans une autre langue (modèles multilingues, langue
détectée automatiquement). Chaque résultat peut être livré dans la langue d'origine ou, pour un
audio en anglais, traduit dans les autres langues officielles de l'ONU : français, espagnol,
russe, arabe et chinois.

Tout tourne sur votre infrastructure : transcription et traduction sont exécutées localement,
aucune donnée n'est envoyée à un service tiers. Les choix techniques, le dimensionnement et
le coût sont détaillés dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

La solution est faite de deux sites distincts, sans lien de l'un vers l'autre :

| Site | Adresse par défaut | Public |
|---|---|---|
| Application | <http://localhost:8000> | Utilisateurs, avec un compte (création ouverte à tous) |
| Console d'administration | <http://localhost:8001> | Administrateur, avec un compte de rôle `admin` |

Avec Docker s'ajoutent les services d'exploitation :

| Service | Adresse par défaut | Rôle |
|---|---|---|
| Keycloak | <http://localhost:8080> | Connexion unique (SSO) |
| Grafana | <http://localhost:3000> | Tableau de bord d'exploitation (compte `admin`) |
| Prometheus | <http://localhost:9090> (cette machine seulement) | Collecte des métriques |
| Triton (GPU) | `localhost:8100` HTTP, `8101` gRPC, `8102` métriques (cette machine seulement) | Serveur d'inférence |

## Deux façons de lancer, sur CPU ou sur GPU

| | Sans Docker (poste de développement) | Avec Docker (serveur, démonstration) |
|---|---|---|
| Commande | `scripts\run_local.ps1 -Device cpu\|gpu` | `scripts\run_docker.ps1 -Device cpu\|gpu` |
| Base de données | PostgreSQL à part (`DATABASE_URL`) ; fichiers dans `.\data` | PostgreSQL, dans un volume |
| Relance après crash | par le script | par Docker (`restart: unless-stopped`) |

PostgreSQL est la seule base prise en charge. Sans Docker, le plus simple est de ne lancer que
la base : `docker compose up -d db` (accessible sur `127.0.0.1:5432`, `DATABASE_URL` par défaut
`postgresql+psycopg://subtitle:subtitle@127.0.0.1:5432/subtitle` ; la base se crée avec le mot
de passe `POSTGRES_PASSWORD` du `.env`, à reporter dans `DATABASE_URL`).

Dans les deux cas, **le matériel se choisit au lancement** et le reste s'adapte :

| | `cpu` | `gpu` (GPU NVIDIA) |
|---|---|---|
| Précision de calcul | 8 bits (int8) | demi-précision (float16) |
| Modèle par défaut | `whisper-small.en` | `whisper-medium.en` |
| Taille des lots | 8 | 16 |
| Dépendances en plus | aucune | bibliothèques CUDA 12 (`requirements-gpu.txt`) |
| Prérequis machine | aucun | pilote NVIDIA |

Demander `gpu` sur une machine sans GPU utilisable arrête le lancement avec un message
explicite, au lieu de tourner lentement sur le processeur sans le dire. La console
d'administration indique sur quel matériel tourne chaque worker.

### Sans Docker (Windows)

Tout tourne sur le poste : application, console d'administration, worker, fichiers et journaux
dans `.\data`. Seule la base PostgreSQL est à part (voir ci-dessus).

1. Installer Python ≥ 3.11 et ffmpeg (`winget install Gyan.FFmpeg`).
2. Créer l'environnement et installer les dépendances :

   ```bash
   python -m venv .venv
   ```

   ```bash
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   ```

   Pour un GPU NVIDIA, ajouter les bibliothèques CUDA :

   ```bash
   .venv\Scripts\python -m pip install -r requirements-gpu.txt
   ```

3. Préparer les modèles de traduction (une seule fois, voir [Traduction](#traduction)). Sans
   eux, tout fonctionne mais la traduction n'est pas proposée.
4. Lancer, sur CPU ou sur GPU (sans `-Device`, le GPU est pris s'il y en a un) :

   ```bash
   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Device cpu
   ```

   ```bash
   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Device gpu
   ```

5. Ouvrir l'application sur <http://localhost:8000> (« Créer un compte » à la première visite) et
   la console d'administration sur <http://localhost:8001> (compte `admin`, mot de passe
   `admin-local`, modifiables avec `-AdminUsername` et `-AdminPassword` ; ce compte est créé au
   premier lancement, ensuite ces deux options sont ignorées).

Arrêt : `Ctrl+C`. Relance : même commande, les traitements en attente ou interrompus sont
repris. Le script surveille les trois processus et relance celui qui s'arrête.

Le modèle Whisper est téléchargé au premier lancement (≈ 500 Mo pour `whisper-small.en`,
≈ 1,5 Go pour `whisper-medium.en`) puis conservé dans le cache Hugging Face du poste ; ensuite
plus rien ne sort de la machine. Pour un audio qui n'est pas en anglais, choisir un modèle
multilingue (`whisper-small`, `whisper-medium`) dans l'interface : un modèle `.en` appliqué à
du français produit un texte inutilisable. `-DefaultModel whisper-small` en fait le choix par
défaut, au prix d'environ 20 % de temps de calcul en plus sur CPU (voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

### Avec Docker

Voir le [manuel d'installation serveur](#manuel-dinstallation-serveur-administrateur).

## Utilisation

1. **Se connecter** : à la première visite, « Créer un compte » (nom d'utilisateur et mot de
   passe de 8 caractères au moins) ; ensuite, « Se connecter ». Le mot de passe est stocké haché
   (argon2) et ne peut pas être récupéré. Ou bien **« Se connecter avec Keycloak »** (connexion
   unique) : un compte est créé à la première connexion, sans mot de passe.
2. **Déposer** un fichier : une barre indique l'avancement de l'envoi.
3. **Choisir** le type de résultat, la langue (origine ou traduction) et le modèle. Pour une
   vidéo à sous-titres incrustés, choisir aussi la taille et la couleur des sous-titres : ils
   font partie de l'image et ne peuvent plus être modifiés ensuite.
4. **Suivre** le traitement : position dans la file, puis barre de progression avec l'étape en
   cours (transcription, traduction, incrustation). Un traitement en attente ou en cours peut
   être annulé. Inutile de rester sur la page : l'avancement s'affiche dans le titre de
   l'onglet, et une notification du navigateur prévient quand l'envoi du fichier puis le
   résultat sont prêts (si le visiteur l'a autorisée ; l'onglet doit rester ouvert).
5. **Consulter et télécharger** le résultat. Pour une vidéo avec piste de sous-titres, la
   taille et la couleur des sous-titres se règlent en direct sous le lecteur ; le réglage est
   mémorisé dans le navigateur.
6. **Corriger** si besoin : « Corriger le texte » ouvre la liste des sous-titres ; après
   enregistrement, les fichiers sont refaits à partir du texte corrigé, sans nouvelle
   transcription (quelques secondes, plus le ré-encodage pour une vidéo incrustée). Les
   corrections sont reprises pour les autres résultats du même fichier dans la même langue.
7. **Supprimer** : « Supprimer mon fichier » efface immédiatement le fichier et ses résultats
   du serveur.

**Mon compte** (lien sur le nom d'utilisateur, en haut à droite) :

- **vue d'ensemble** : traitements demandés et réussis, durée de média transcrit, temps de
  calcul, espace occupé sur le serveur, derniers traitements ;
- **historique** de tous ses traitements : fichier, type de résultat, langue, modèle, statut,
  attente dans la file, temps de calcul et durée totale, téléchargement tant que le fichier
  est conservé ;
- **profil** : nom affiché et adresse e-mail (le nom d'utilisateur et le rôle ne sont pas
  modifiables) ;
- **sécurité** : changer (ou définir, pour un compte créé par Keycloak) son mot de passe, ce
  qui ferme ses autres connexions ; associer ou dissocier son compte Keycloak ; supprimer
  son compte, ses fichiers et son historique.

Les sous-titres sont mis en forme sur deux lignes de 42 caractères au plus ; un passage plus
long est réparti sur plusieurs sous-titres successifs.

**Limites.** Un fichier est refusé au-delà de 2 Go ou de 2 h (`MAX_UPLOAD_MB`,
`MAX_DURATION_S`), ou si sa durée est illisible. La durée est vérifiée dans le navigateur
avant l'envoi, puis par le serveur.

**Envoi des gros fichiers.** Le fichier est envoyé par morceaux de 8 Mo. Si la connexion
coupe, l'envoi reprend seul là où il s'est arrêté ; après un rechargement de la page, il
suffit de choisir à nouveau le même fichier pour continuer au lieu de recommencer.

**File d'attente.** Quand trop de média est déjà en attente (4 h par défaut,
`MAX_PENDING_MEDIA_S`), l'application annonce « service saturé » avant même l'envoi du
fichier, au lieu d'accepter un travail qu'elle rendrait très tard. Un même utilisateur peut avoir
4 traitements en attente ou en cours à la fois.

**Confidentialité.** Un fichier et ses résultats ne sont accessibles qu'au compte qui a
déposé le fichier ; pour tout autre, ils répondent comme s'ils n'existaient pas. Sans
connexion, tout répond 401.

**Conservation.** Chaque utilisateur ne garde sur le serveur que son dernier fichier et ses
résultats : en déposer un nouveau supprime le précédent dès que ses traitements sont terminés.
En revenant sur la page, le dernier fichier et son résultat sont proposés à nouveau, depuis
n'importe quel navigateur où l'on se connecte. Tout fichier est de toute façon supprimé après
7 jours (`RETENTION_DAYS`).
La purge ne supprime que des fichiers : statistiques et texte des réponses restent visibles
dans la console d'administration.

Un fichier court n'attend pas derrière un fichier long : voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#traitements-simultanés-et-voie-rapide).

## Traduction

La traduction part de l'anglais vers les cinq autres langues officielles de l'ONU, avec des
modèles libres Helsinki-NLP exécutés localement :

| Langue | Modèle | Licence |
|---|---|---|
| Français | `Helsinki-NLP/opus-mt-en-fr` | Apache 2.0 |
| Espagnol | `Helsinki-NLP/opus-mt-en-es` | Apache 2.0 |
| Russe | `Helsinki-NLP/opus-mt-en-ru` | Apache 2.0 |
| Arabe | `Helsinki-NLP/opus-mt-tc-big-en-ar` | CC BY 4.0 |
| Chinois (simplifié) | `Helsinki-NLP/opus-mt-en-zh` | Apache 2.0 |

Pour l'arabe, le modèle « tc-big », plus gros, remplace `opus-mt-en-ar`, nettement moins bon.
Les modèles doivent être convertis une fois au format du moteur d'inférence ; cette étape a
besoin de PyTorch, que l'application n'utilise pas, d'où un environnement séparé :

```bash
python -m venv .venv-convert
```

```bash
.venv-convert\Scripts\python -m pip install -r requirements-convert.txt
```

```bash
.venv-convert\Scripts\python scripts\convert_translation_model.py
```

Les modèles (≈ 80 Mo chacun, 235 Mo pour l'arabe) sont écrits dans `models\` ; un modèle déjà
converti est sauté. `scripts\convert_translation_model.py opus-mt-en-es` n'en prépare qu'un.
`.venv-convert` peut ensuite être supprimé. Avec Docker, cette conversion est faite pendant la
construction de l'image. Une langue dont le modèle est absent n'est simplement pas proposée.

Seul un audio en anglais peut être traduit. Pour un audio dans une autre langue, seule la
langue d'origine est disponible ; demander une traduction fait échouer le traitement.

Le chinois s'écrit sans espaces : il est coupé entre les caractères, deux fois plus larges à
l'écran, soit 21 caractères par ligne au plus. L'arabe s'affiche de droite à gauche dans
l'éditeur et le lecteur ; l'image Docker contient les polices nécessaires à l'incrustation.

Les sous-titres sont traduits phrase par phrase puis redécoupés sur les horodatages
d'origine. La qualité est celle d'un modèle de traduction généraliste compact : correcte pour
comprendre, à relire pour une diffusion. Un autre traducteur (y compris un service interne
appelé en HTTP) se branche comme un modèle, voir plus bas.

## Manuel d'installation serveur (administrateur)

### Prérequis

- Docker avec le plugin Compose : Docker Desktop sous Windows et macOS, Docker Engine ≥ 24
  sous Linux.
- Pour la version GPU : un GPU NVIDIA (≥ 8 Go de mémoire) et son pilote, plus le
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  sous Linux ; sous Windows, Docker Desktop avec le moteur WSL 2 suffit.
- Accès à internet à la construction de l'image (dépendances, modèle de traduction) et au
  premier démarrage (modèle Whisper, conservé ensuite dans un volume).

### Installer et démarrer

1. **Essai rapide : rien à configurer.** `docker compose up -d --build` construit l'image et
   démarre la base, l'application, la console et le worker. Le mot de passe de l'administrateur
   (compte `admin`) est alors généré au premier démarrage et affiché une seule fois :
   `docker compose logs admin`.
   **Serveur :** copier `.env.example` en `.env` et renseigner `POSTGRES_PASSWORD` et
   `ADMIN_PASSWORD` (valeurs longues et aléatoires ; `ADMIN_USERNAME` vaut `admin` par défaut)
   avant le premier démarrage. Le couple `ADMIN_USERNAME` / `ADMIN_PASSWORD` ne sert qu'une
   fois : il crée le premier compte administrateur quand la base n'en contient aucun.
2. Démarrer en choisissant le matériel. Sous Windows :

   ```bash
   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Device cpu
   ```

   ```bash
   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Device gpu
   ```

   Sous Linux ou macOS : `scripts/run_docker.sh cpu` ou `scripts/run_docker.sh gpu`.

   Le script vérifie que Docker tourne et, en version GPU, que Docker voit bien le GPU avant
   de construire l'image. La première construction prend plusieurs minutes ; l'image pèse
   1,7 Go en version CPU et 5,4 Go en version GPU (bibliothèques CUDA).
3. Ouvrir l'application sur le port 8000 et la console d'administration sur le port 8001.
   Le premier traitement est possible dès que la console affiche le worker « en service ».

Sans les scripts : `docker compose up -d --build` (CPU), ou
`DEVICE=gpu docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` (GPU).

Une seule image sert aux trois services (application, console, worker) ; seule la commande
change. Toutes les images du projet portent le préfixe `subtitle-` et la version de leur
base dans leur tag, avec leur configuration intégrée (pas de fichier monté depuis le disque) :

| Image | Construite depuis | Contenu |
|---|---|---|
| `subtitle-app:cpu` / `:gpu` | `Dockerfile` | application, console, worker (même image, trois commandes) |
| `subtitle-triton:25.06` | `triton/Dockerfile` | serveur d'inférence (GPU) |
| `subtitle-db:16` | `db/` | PostgreSQL 16 |
| `subtitle-keycloak:26.0.7` | `keycloak/` | Keycloak avec le realm `subtitle` |
| `subtitle-prometheus:3.5.0` | `observability/prometheus/` | Prometheus avec ses cibles |
| `subtitle-grafana:12.1.1` | `observability/grafana/` | Grafana avec la source de données et le tableau de bord |

L'image Triton ne garde que le backend Python, selon la méthode `compose.py` de NVIDIA : 18,6 Go
sur le disque au lieu de 32,7 Go avec l'image officielle complète (voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)). Sa construction a besoin de l'image complète
`tritonserver:25.06-py3` (11 Go à télécharger) ; une fois l'image construite, celle-ci peut
être supprimée (`docker rmi nvcr.io/nvidia/tritonserver:25.06-py3`). N'exposer que le port 8000 aux utilisateurs ; réserver le port 8001 au réseau
d'administration, derrière un reverse proxy HTTPS.

### Arrêter

```bash
docker compose stop
```

(ou `scripts\run_docker.ps1 -Stop`). Les fichiers, résultats, journaux et statistiques sont
conservés (volumes `db`, `data`, `models`). `docker compose down -v` supprime aussi ces données.

### Relancer après un arrêt ou un crash

Relancer la commande de démarrage (même `-Device`).

- Les conteneurs redémarrent seuls après un crash ou un redémarrage de la machine
  (`restart: unless-stopped`).
- Les traitements en attente sont conservés en base et repris.
- Un traitement interrompu en cours de route est détecté (absence de signal de vie pendant
  60 s) et remis en file automatiquement ; après 3 interruptions il est marqué en échec.
- Une base créée par une version précédente est mise à niveau au démarrage par les migrations
  (Alembic, `app/migrations`), sans perte. Exception : le passage aux comptes utilisateurs
  (migration `0001`) abandonne les anciens dépôts, qui n'appartenaient à aucun compte : leurs
  tables sont recréées vides.

Passer de `cpu` à `gpu` (ou l'inverse) : relancer avec l'autre valeur, les données sont
conservées.

### Serveur d'inférence (Triton)

En version GPU, les modèles ne tournent plus dans le worker mais dans un serveur
d'inférence dédié, [NVIDIA Triton](https://github.com/triton-inference-server/server) : seul
le service `triton` reçoit le GPU. Le worker garde la file, ffmpeg et les fichiers ; il envoie
l'audio et le texte à Triton en gRPC. En version CPU (ou sans Docker), les modèles restent
dans le worker (`INFERENCE_BACKEND=local`).

```
navigateur ─► api ─► PostgreSQL ◄─ worker ──gRPC──► triton (GPU)
                                                     ├─ whisper_medium_en, whisper_small_en,
                                                     │  whisper_medium, whisper_small,
                                                     │  whisper_large_v3_turbo
                                                     └─ translator (anglais → fr, es, ru, ar, zh)
```

- **Dépôt de modèles** : `triton/model_repository`, un dossier par modèle avec son
  `config.pbtxt` (entrées, sorties, instance GPU, paramètres). Les modèles utilisent le backend
  Python de Triton avec le moteur CTranslate2 (faster-whisper, OPUS-MT) : mêmes poids, mêmes
  performances qu'avant, code commun dans `triton/backend/subtitle_models`.
- **Transcription en flux** : les modèles Whisper sont en mode `decoupled` ; Triton renvoie
  chaque segment de sous-titre dès qu'il est décodé (barre de progression), et un traitement
  annulé arrête la requête entre deux segments. Plusieurs requêtes partagent les mêmes poids
  sur le GPU, chacune dans son fil.
- **Chargement des modèles** : `--model-control-mode=explicit`. Le traducteur et le modèle
  par défaut (`TRITON_PRELOAD_MODEL`, `whisper_medium_en`) démarrent avec le serveur ; un autre
  Whisper est chargé à la première demande d'un utilisateur, ce qui ménage la mémoire du GPU.
  Les poids Whisper sont dans le volume `models`, les traducteurs dans l'image ; le
  traducteur est préchauffé au chargement (le premier appel GPU coûte une quinzaine de
  secondes).
- **Vérifier le serveur sans l'application** (client gRPC, comme dans le TP) :

  ```bash
  curl localhost:8100/v2/health/ready
  python scripts/triton_check.py input.mp4 --to fr   # santé, modèles, transcription, traduction
  ```

Mesure sur la vidéo de démonstration (149 s, RTX 5070 Ti) : transcription en 8,7 s
(× 0,06), traitement complet avec traduction et incrustation en 21,5 s, contre 36,6 s quand
le modèle tournait dans le worker.

### Observabilité (Prometheus, Grafana)

Chaque service publie ses métriques Prometheus sur le réseau interne (port 9100, jamais
exposé) : l'application (requêtes HTTP par route, latence), le worker (traitements par
résultat, durée, durée de chaque étape) et la console (état lu en base : file d'attente,
workers, comptes, stockage). Triton publie les siennes (requêtes, latence et file par modèle,
mémoire GPU). Prometheus les collecte toutes les 15 s et les garde 15 jours
(`PROMETHEUS_RETENTION`) ; les workers sont découverts par DNS, y compris avec
`docker compose up --scale worker=N`.

Grafana (<http://localhost:3000>, compte `admin` / `GRAFANA_ADMIN_PASSWORD`) ouvre directement
le tableau de bord « Sous-titrage : application et inférence », intégré à l'image
`subtitle-grafana` depuis `observability/grafana` (modifier le JSON, puis
`docker compose up -d --build grafana`) : vue d'ensemble (file, workers, taux de réussite, état de Triton et
de la base), traitements, serveur d'inférence, API. Sous WSL 2 (Docker Desktop), Triton ne
remonte pas l'utilisation du GPU (NVIDIA DCGM y est limité) ; la mémoire GPU, elle, est juste.

### Console d'administration

Service séparé de l'application (autre processus, autre port, aucun lien entre les deux
sites), accessible après connexion avec un compte de rôle `admin` (nom d'utilisateur et mot de
passe). Les comptes sont en base, comme ceux des utilisateurs ; le premier est créé depuis
`ADMIN_USERNAME` / `ADMIN_PASSWORD`. La console reste disponible quand l'application ou le
worker sont arrêtés, et montre :

- l'**état des services** : application, base de données, chaque worker, espace disque ;
- un **tableau de bord** sur 7, 30 ou 90 jours : comptes, utilisateurs actifs, traitements,
  taux de réussite, attente et calcul (moyenne et 95e centile), fichiers conservés ; courbes
  par jour (traitements, utilisateurs actifs et nouveaux comptes, minutes traitées),
  répartition par langue, par type de résultat et par modèle ;
- les **utilisateurs** : recherche, activité de chaque compte, fiche détaillée (historique,
  chiffres), création d'un compte, rôle, désactivation, réinitialisation du mot de passe,
  suppression. Un administrateur ne peut ni se rétrograder, ni se désactiver, ni se supprimer,
  et le dernier administrateur actif est toujours conservé ;
- les **traitements** de tous les utilisateurs (filtre par statut et par utilisateur), avec leur
  avancement et le contenu de chaque réponse ;
- les **journaux** de chaque service (`data/logs`), y compris ceux d'un service tombé.

Cinq mots de passe erronés bloquent la connexion pendant une minute. La session dure
8 heures. Si la base de données est arrêtée, un administrateur déjà connecté garde l'accès aux
journaux et à l'état des services ; une nouvelle connexion, elle, a besoin de la base.

### Comptes

L'inscription est ouverte à tous depuis l'application (`/register.html`), limitée à
`MAX_REGISTRATIONS_PER_HOUR` créations par heure et par adresse IP. Une connexion dure
`SESSION_DAYS` jours. L'administrateur gère les comptes en ligne de commande :

```bash
docker compose exec api python -m app.users create alice          # demande le mot de passe
docker compose exec api python -m app.users create root --admin
docker compose exec api python -m app.users passwd alice          # mot de passe oublié
docker compose exec api python -m app.users disable alice         # et enable, list
```

Changer un mot de passe ou désactiver un compte termine ses connexions en cours.

### Connexion unique (Keycloak)

Le service `keycloak` du compose est un fournisseur OpenID Connect prêt à l'emploi (mode
développement) : realm `subtitle`, client `subtitle-app`, compte de démo `demo` /
`demo-password`, inscription ouverte. Sa console est sur http://localhost:8080/admin (compte
`admin` / `KEYCLOAK_ADMIN_PASSWORD`). L'application suit le flux « authorization code » avec
PKCE ; un compte Keycloak est retrouvé par son identifiant (jamais par son adresse e-mail,
qui ne permet donc pas de prendre la main sur un compte existant). Pour un autre fournisseur
(Google, Microsoft Entra ID...), renseigner `OIDC_DISCOVERY_URL`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET` et `OIDC_LABEL` (voir `.env.example`). Hors démonstration : Keycloak en
mode production (HTTPS, base PostgreSQL), et un secret de client changé.

### Base de données

PostgreSQL. Le schéma est géré par Alembic : chaque service applique les migrations en
attente à son démarrage (verrou en base : un seul le fait à la fois). Après une modification
de `app/models.py`, générer la migration puis la relire :

```bash
.venv\Scripts\python -m alembic revision --autogenerate -m "description"
```

Tables : `users` (comptes, mot de passe haché, rôle `user` ou `admin`), `auth_sessions`
(connexions ; seule l'empreinte SHA-256 du jeton est gardée), `uploads` (fichiers déposés),
`upload_sessions` (envois en cours), `jobs` (traitements et leurs résultats texte), `workers`.
Les **vidéos et audios, déposés comme produits, restent sur le disque** (volume `data`) :
la base n'en garde que les métadonnées (propriétaire, chemin, taille, durée) et la liste des
fichiers produits. Supprimer un compte supprime en cascade ses dépôts et ses traitements en
base ; les fichiers correspondants sont à retirer du volume.

### Configuration

Toutes les options sont décrites dans [.env.example](.env.example).

## API (développeur)

Documentation interactive : <http://localhost:8000/docs>.

| Méthode | Chemin | Rôle |
|---|---|---|
| `POST` | `/api/uploads` | Déposer un fichier en une requête (`multipart/form-data`, champ `file`) |
| `POST` | `/api/uploads/sessions` | Démarrer un envoi par morceaux : `{"filename", "size_bytes"}` |
| `PUT` | `/api/uploads/sessions/{id}` | Ajouter un morceau (`offset`, `chunk`) ; 409 avec la position réelle si décalé |
| `GET` | `/api/uploads/sessions/{id}` | Octets déjà reçus, pour reprendre un envoi |
| `POST` | `/api/uploads/sessions/{id}/complete` | Terminer l'envoi : renvoie le fichier déposé |
| `GET` | `/api/queue` | Charge de la file et acceptation de nouveaux traitements |
| `POST` | `/api/jobs` | Lancer un traitement (corps ci-dessous) |
| `GET` | `/api/jobs/{id}` | Statut, étape, pourcentage, position dans la file, fichiers produits |
| `GET` | `/api/jobs/{id}/download` | Télécharger le résultat |
| `GET` | `/api/jobs/{id}/files/{nom}` | Un fichier du résultat, affichable dans le navigateur |
| `GET` | `/api/jobs/{id}/transcript` | Texte et segments horodatés en JSON |
| `PUT` | `/api/jobs/{id}/segments` | Corriger le texte des sous-titres (`{"texts": […]}`) et refaire les fichiers |
| `POST` | `/api/jobs/{id}/cancel` | Annuler un traitement en attente ou en cours |
| `DELETE` | `/api/uploads/{id}` | Supprimer un fichier et ses résultats |
| `GET` | `/api/uploads/last` | Dernier fichier de l'utilisateur encore sur le serveur, avec ses traitements |
| `GET` | `/api/config` | Modèles, langues de traduction, sorties disponibles et limites |
| `POST` | `/api/auth/register` | Créer un compte : `{"username", "password"}` ; connecte aussitôt (409 si le nom est pris) |
| `POST` | `/api/auth/login` | Se connecter : mêmes champs ; pose le cookie `session` |
| `POST` | `/api/auth/logout` | Terminer la connexion |
| `GET` | `/api/auth/me` | Compte connecté (`{"username", "role"}`) ; 401 sinon |

```json
{
  "upload_id": "…",
  "output_type": "video_embedded | video_subtitles | subtitles | text",
  "model": "whisper-small.en",
  "translate_to": "fr",
  "subtitle_style": {"size": "small | medium | large", "color": "#FFFF00"}
}
```

Seuls `upload_id` et `output_type` sont obligatoires ; `subtitle_style` ne s'applique qu'à
`video_embedded`.

**Authentification.** Tout est protégé par un compte, sauf `/api/health`, `/api/config`,
`/api/queue` et les pages de connexion. Après `register` ou `login`, le serveur pose un cookie
`session` (HttpOnly, SameSite Lax, Secure en HTTPS) ; un client d'API doit le conserver entre
ses appels (`requests.Session`, `httpx.Client`, `curl -c/-b`). Un fichier, ses traitements et
ses résultats ne sont visibles que de leur propriétaire : pour tout autre compte, 404.
Sans connexion, 401.

`POST /api/jobs` peut répondre 503 avec `Retry-After` (file saturée) ou 429 (trop de
traitements en cours pour ce client).

**Interfaçage avec un service de traduction externe** : `GET /api/jobs/{id}/transcript`
renvoie `{"language", "source_language", "text", "segments": [{"start", "end", "text",
"speaker"}]}`. Le service peut traduire `text`, ou chaque segment pour reconstruire des
sous-titres. Il peut aussi être intégré à la solution comme traducteur (ci-dessous).

Un même fichier déposé peut servir à plusieurs traitements : la transcription n'est calculée
qu'une fois par couple fichier / modèle, la traduction et les fichiers sont refaits à partir
d'elle.

## Ajouter un modèle, un traducteur ou l'identification du speaker (data scientist)

### Modèle de transcription

Les modèles sont des greffons du paquet [app/transcription](app/transcription).

1. Créer un module, par exemple `app/transcription/mon_modele.py` :

   ```python
   from app.domain import Segment, Transcription
   from app.transcription.base import Transcriber, register_transcriber

   class MonModele(Transcriber):
       thread_safe = False  # True si transcribe() supporte plusieurs appels simultanés

       def load(self) -> None:
           ...  # charger les poids (appelé une seule fois)

       def transcribe(self, audio_path, on_progress) -> Transcription:
           ...  # audio_path : wav 16 kHz mono ; on_progress(0.0 à 1.0) alimente la barre
           return Transcription("fr", [Segment(start=0.0, end=2.5, text="Bonjour")])

   register_transcriber("mon-modele", MonModele)
   ```

2. L'importer dans [app/transcription/\_\_init\_\_.py](app/transcription/__init__.py).
3. Ajouter `mon-modele` à `ENABLED_MODELS` : il apparaît dans l'interface.

Une autre taille de Whisper ne demande qu'une ligne dans
[whisper.py](app/transcription/whisper.py).

### Traducteur

Même principe dans [app/translation](app/translation) : une classe `Translator` avec
`translate(textes) -> textes`, enregistrée par
`register_translator("nom", Classe, source="en", target="de")`, importée dans
`app/translation/__init__.py` et ajoutée à `ENABLED_TRANSLATORS`. La nouvelle langue apparaît
dans l'interface. Une autre paire OPUS-MT ne demande qu'une ligne dans
[opus_mt.py](app/translation/opus_mt.py) et une conversion avec
`scripts/convert_translation_model.py --model … --output …`.

### Identification du speaker

Une classe `SpeakerIdentifier` dont la méthode `identify(audio_path, segments)` renseigne
`segment.speaker`, enregistrée avec `register_speaker_identifier("nom", ...)` et activée par
`SPEAKER_IDENTIFIER=nom`. Le nom du speaker est alors ajouté aux sous-titres et au texte
(`[Steve] ...`), sans autre modification.

## Développement

```bash
.venv\Scripts\python -m pytest
```

Les tests n'ont besoin ni de GPU, ni de ffmpeg, ni des modèles (transcription et traduction
factices, ffmpeg simulé), mais d'un PostgreSQL jetable : `TEST_DATABASE_URL` doit désigner
une base dédiée (son schéma est supprimé et recréé par les migrations avant chaque test :
ne jamais viser la base de l'application).

```bash
docker compose exec db createdb -U subtitle subtitle_test
```

```bash
$env:TEST_DATABASE_URL = "postgresql+psycopg://subtitle:MOT_DE_PASSE@127.0.0.1:5432/subtitle_test"
.venv\Scripts\python -m pytest
```

Depuis le conteneur, sans environnement local :

```bash
docker compose run --rm --no-deps -v ./tests:/srv/tests:ro -e HOME=/tmp -e TEST_DATABASE_URL=postgresql+psycopg://subtitle:MOT_DE_PASSE@db:5432/subtitle_test api sh -c "pip install -q --user pytest httpx && python -m pytest -q -p no:cacheprovider tests"
```

Le modèle factice peut aussi servir à une
démonstration instantanée : `scripts\run_local.ps1 -Models fake -DefaultModel fake`.

## Vérifier les performances

```bash
python scripts/benchmark.py input.mp4 --users 10 --output-type video_embedded
```

Le script simule 10 utilisateurs simultanés (un compte créé pour chacun : prévoir
`MAX_REGISTRATIONS_PER_HOUR` au moins égal au nombre d'utilisateurs) et vérifie que chaque
résultat arrive en moins de temps que la durée du média (attente dans la file comprise).

## Organisation du code

```
app/
  api.py            application utilisateur : API HTTP + interface web
  account_api.py    « Mon compte » et connexion unique (routes)
  accounts.py       comptes vus par leur titulaire et par l'administrateur
  sso.py            client OpenID Connect (Keycloak)
  metrics.py        métriques Prometheus des services
  triton_client.py  connexion au serveur d'inférence Triton (gRPC)
  auth.py           comptes : hachage argon2, sessions, limitation des tentatives
  users.py          gestion des comptes en ligne de commande (python -m app.users)
  admin.py          console d'administration (service séparé)
  db.py             connexion PostgreSQL et application des migrations
  migrations/       schéma de la base (Alembic)
  worker.py         processus de traitement (file, voie rapide, signal de vie, reprise)
  jobs.py           file de traitements en base
  pipeline.py       transcription, traduction, fabrication des fichiers, progression
  media.py          appels ffmpeg / ffprobe
  subtitles.py      formats SRT, VTT, texte
  stats.py          statistiques d'usage
  retention.py      purge automatique des fichiers
  device.py         choix CPU / GPU
  logs.py           journaux par service
  transcription/    modèles de transcription (greffons)
  translation/      traducteurs (greffons)
triton/
  Dockerfile        image du serveur d'inférence (tritonserver + modèles)
  model_repository/ un dossier par modèle Triton : config.pbtxt + 1/model.py
  backend/          code des modèles (backend Python de Triton)
observability/      images Prometheus (cibles) et Grafana (tableau de bord)
keycloak/           image Keycloak et realm importé au premier démarrage
db/                 image PostgreSQL du projet
web/
  user/             interface utilisateur
  admin/            console d'administration
  shared/           feuille de style et mise en forme communes
tests/              tests automatisés
scripts/            lancement local ou Docker (CPU / GPU), conversion du modèle de traduction,
                    test de charge, vérification du serveur Triton
test_pipeline_3.py  prototype d'origine, conservé pour référence
```
