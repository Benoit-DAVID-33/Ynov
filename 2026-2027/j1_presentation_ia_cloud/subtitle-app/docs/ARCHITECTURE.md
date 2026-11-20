# Architecture

## Vue d'ensemble

```mermaid
flowchart LR
    U[Utilisateur<br>navigateur] -->|HTTP :8000| API
    T[Service de traduction externe] -->|GET transcript| API
    A[Administrateur<br>navigateur] -->|HTTP :8001<br>mot de passe| ADM
    subgraph Serveur
        API[api<br>application utilisateur]
        ADM[admin<br>console d'administration]
        W[worker<br>Whisper + traduction + ffmpeg]
        DB[(Base<br>file + résultats + stats)]
        V[(Volume data<br>fichiers + journaux)]
        API --> DB
        API --> V
        W --> DB
        W --> V
        ADM -.->|sonde| API
        ADM -.-> DB
        ADM -.-> V
    end
```

Quatre services, décrits dans `docker-compose.yml` :

| Service | Rôle |
|---|---|
| `api` | Application utilisateur : reçoit les fichiers, crée les traitements, sert les résultats et l'interface web. Ne charge aucun modèle : il reste réactif pendant les calculs. |
| `worker` | Prend les traitements dans la file, transcrit, traduit, fabrique les fichiers avec ffmpeg. |
| `admin` | Console d'administration : état des services, usage, journaux. Ne dépend d'aucun autre service. |
| `db` | PostgreSQL : file de traitements, transcriptions, données d'usage. |

Déroulé d'un traitement : dépôt (`POST /api/uploads`) → lancement (`POST /api/jobs`, statut
`queued`) → le worker le prend (`processing`) → extraction audio 16 kHz mono → transcription
→ traduction si demandée → fabrication des fichiers selon le type demandé → `done` ou
`failed`. Le worker écrit l'étape et le pourcentage en base ; l'interface les lit toutes les
0,7 s et affiche la barre de progression.
## Choix et justifications

**Traitement asynchrone (API + worker séparés).** Une transcription dure de quelques secondes
à plusieurs minutes : la faire dans la requête HTTP bloquerait l'utilisateur, casserait sur un
timeout et empêcherait de servir 10 personnes. La file absorbe les pics et permet d'afficher
une position d'attente.

**File de traitements dans PostgreSQL plutôt qu'un broker (Redis, RabbitMQ).** Au volume visé
(10 utilisateurs), une table suffit, et cela fait un composant de moins à installer, surveiller
et sauvegarder. La prise d'un traitement est une mise à jour conditionnelle atomique
(`UPDATE ... WHERE status = 'queued'`), donc plusieurs workers peuvent coexister. Les
statistiques demandées par l'administrateur se lisent directement dans cette même table.

**Reprise après crash.** Le worker écrit un signal de vie toutes les 10 s pour chaque
traitement en cours. Un traitement sans signal depuis 60 s est remis en file (3 tentatives
maximum, puis échec explicite). Rien n'est gardé en mémoire : un redémarrage ne perd aucun
traitement.

**Modèles en greffons.** `Transcriber` et `SpeakerIdentifier` sont deux interfaces avec un
registre. Ajouter un modèle ou l'identification du speaker ne touche ni à l'API, ni à la file,
ni à l'interface. Le champ `speaker` existe déjà dans les segments, les sous-titres et l'API.

**Souveraineté.** Modèle exécuté localement, stockage sur un volume du serveur, aucune
dépendance à une API externe. Seul le téléchargement initial des poids sort du réseau ; il peut
être évité en préremplissant le volume `models`.

**Whisper exécuté avec faster-whisper (CTranslate2) plutôt que transformers.** Ce sont les
mêmes poids OpenAI que le prototype (`whisper-medium.en`), mais mesuré sur l'échantillon
fourni, le pipeline transformers du prototype rendait un premier sous-titre de 2 min 08 d'un
seul bloc (horodatages perdus à la fusion des fenêtres) et mettait 95 s sur CPU avec
`small.en`. faster-whisper rend 52 sous-titres de 6,4 s au plus en 13 s, sans dépendre de
PyTorch, sur CPU (int8) comme sur GPU (float16).

**Un seul moteur de base de données.** PostgreSQL, sous Docker comme en développement
(`docker compose up -d db` suffit à l'établi). Les deux déploiements ne diffèrent que par la
configuration. SQLite a été abandonné : le schéma comporte des comptes, des contraintes de
clé étrangère avec suppression en cascade, des verrous consultatifs pour les migrations
simultanées, et les tests doivent tourner sur le moteur de production.

**CPU ou GPU, choisi au lancement.** L'équipe développe sur deux machines, l'une sans GPU,
l'autre avec un GPU NVIDIA. Un seul réglage, `DEVICE`, posé par les scripts de lancement,
détermine tout ce qui dépend du matériel : précision de calcul (int8 ou float16), modèle par
défaut, taille des lots, et, sous Docker, l'image construite (les bibliothèques CUDA, près de
4 Go, ne sont installées que dans la version GPU) ainsi que l'accès du worker au GPU. Le moteur
d'inférence (CTranslate2) et le code sont identiques dans les deux cas. Un GPU demandé mais
inutilisable arrête le worker avec un message clair plutôt que de retomber sur le CPU en
silence.

**Une seule image Docker.** Application, console et worker partagent la même image et ne
diffèrent que par leur commande : une construction, un seul artefact à versionner et à
déployer. Elle tourne sous un utilisateur non privilégié. Le modèle de traduction y est
converti à la construction, dans une étape séparée, pour que PyTorch n'entre pas dans
l'image finale.

**Console d'administration séparée.** L'exigence est que l'administrateur garde la main quand
le site tombe. La console est donc un autre processus, sur un autre port, sans aucun lien
depuis l'application utilisateur (et inversement), avec son propre mot de passe. Elle se
connecte à la base à la demande : si la base est injoignable elle démarre quand même et
affiche l'état des services et les journaux, que chaque service écrit dans des fichiers du
volume partagé. Vérifié en arrêtant brutalement l'application : la console la signale « à
l'arrêt », ses journaux restent lisibles, puis elle repasse « en service » après la relance
automatique.

**Traduction locale en greffon.** Les cinq autres langues de l'ONU sont produites depuis
l'anglais par des modèles OPUS-MT (Helsinki-NLP) convertis pour CTranslate2 : même moteur que
Whisper, pas de PyTorch à l'exécution, 80 Mo par langue (235 Mo pour l'arabe). Les modèles
arabe et chinois couvrent plusieurs variantes : un jeton `>>ara<<` ou `>>cmn_Hans<<` en tête
de phrase choisit l'arabe standard et le mandarin simplifié. Les sous-titres étant souvent des
fragments de phrase, ils sont regroupés en phrases, traduits, puis redistribués sur les horodatages d'origine au prorata
des longueurs. L'interface `Translator` permet de brancher à la place le service de traduction
du client.
**Correction des sous-titres sans retranscrire.** Le texte corrigé par l'utilisateur est
enregistré à côté de la transcription d'origine, puis le même traitement repasse dans la file
pour refaire uniquement les fichiers. Mesuré : 3 s pour refaire une vidéo incrustée de
2 min 29, contre 16 s pour le traitement complet.

**Annulation coopérative.** Annuler passe le traitement à l'état « annulé » en base ; le
worker s'en aperçoit en écrivant sa progression et s'arrête (ffmpeg est tué, le dossier de
travail supprimé). L'arrêt est immédiat pendant l'incrustation, et attend la fin du lot en
cours pendant la transcription (une vingtaine de secondes au plus sur CPU).

**Mise en forme des sous-titres.** Deux lignes de 42 caractères au plus, équilibrées ; un
segment plus long est réparti sur plusieurs sous-titres au prorata du texte. En incrustation
grande taille la limite passe à 32 caractères, pour ne pas dépasser deux lignes à l'image.

**Transcription mise en cache.** Demander un second type de résultat pour le même fichier
réutilise la transcription : seul ffmpeg est relancé.

**Interface sans chaîne de build.** HTML/CSS/JS statiques servis par l'API : pas de Node à
installer ni de second service à déployer.

## Traitements simultanés et voie rapide

Besoin : si un utilisateur dépose une vidéo de 30 min et qu'un autre dépose une vidéo de
2 min, le second ne doit pas attendre 30 min. Deux mécanismes y répondent.

1. **Les traitements avancent de front.** Un worker mène `WORKER_CONCURRENCY` traitements à la
   fois (3 par défaut). Whisper traite l'audio par lots de quelques minutes ; les traitements
   en cours se partagent le modèle lot par lot au lieu de se suivre. Une vidéo courte n'attend
   donc au pire que la fin du lot en cours d'une vidéo longue.
2. **Une voie rapide est réservée aux fichiers courts.** `FAST_LANE_SLOTS` emplacements (1 par
   défaut) ne prennent que les médias de moins de `FAST_LANE_MAX_S` secondes (5 min). Même si
   tous les autres emplacements sont occupés par des fichiers longs, un fichier court démarre
   immédiatement. Les fichiers longs, eux, sont pris dans l'ordre d'arrivée.

Mesure sur le poste de développement (CPU seul, `whisper-small.en`) : deux vidéos de 29 min
47 s lancées ensemble, puis l'échantillon de 2 min 29 soumis 8 s plus tard avec traduction.

| Fichier | Demande | Résultat disponible après |
|---|---|---|
| Vidéo courte (2 min 29) | vidéo + sous-titres en français | **41 s** |
| Vidéo longue B (29 min 47) | sous-titres | 5 min 39 |
| Vidéo longue A (29 min 47) | vidéo incrustée en français | 6 min 54 |

Sans ces mécanismes, la vidéo courte aurait attendu la fin d'une vidéo longue, soit plus de
5 min. Seule sur la machine elle prend 15 s : le partage du processeur avec les deux longues
la ralentit, mais elle reste servie en bien moins que sa propre durée.

Limite : la voie rapide protège les fichiers courts, pas les fichiers longs entre eux. Avec
plus de fichiers longs que d'emplacements, les suivants attendent leur tour.

**Finesse de la barre de progression.** Pendant la transcription, le pourcentage avance à
chaque lot terminé (`BATCH_SIZE` fenêtres de 30 s, soit 4 min d'audio par défaut). Sur un
fichier de quelques minutes la barre fait donc peu de paliers ; elle est fluide sur les
fichiers longs et pendant l'incrustation vidéo. Réduire `BATCH_SIZE` l'affine au prix d'un
débit un peu plus faible.
## Limites et conservation des fichiers

**Limites par fichier.** 2 Go et 2 h par défaut. La durée est la vraie mesure du coût : le
calcul lui est proportionnel et l'audio est chargé entièrement en mémoire (environ 230 Mo par
heure et par traitement). À 2 h, un traitement représente de l'ordre de 11 min de calcul sur
le CPU de développement et 460 Mo de mémoire ; trois de front restent confortables sur 32 Go.
Un fichier dont la durée est illisible est refusé dès le dépôt plutôt que d'échouer plus tard.

**Plafond de la file.** Sans limite, le service accepterait plus de travail qu'il ne peut en
rendre dans des délais raisonnables. Un traitement est refusé quand la durée de média en
attente ou en cours (les traitements en cours ne comptent que pour ce qu'il leur reste), plus
la sienne, dépasse `MAX_PENDING_MEDIA_S` (4 h par défaut). Une file vide accepte toujours, pour
qu'un fichier seul ne soit jamais refusé. La limite est exprimée en durée de média et non en
nombre de traitements, parce que c'est la durée qui fait la charge. S'y ajoute un plafond de
4 traitements actifs par utilisateur. Le scénario de référence (10 utilisateurs, 2 min 29 chacun,
soit 25 min de média) reste très en dessous du plafond.

Une règle plus stricte, refuser dès que la promesse « plus rapide que la durée du média » ne
peut plus être tenue, a été écartée : elle refuserait à tort les fichiers courts que la voie
rapide sert pourtant en quelques dizaines de secondes.

**Envoi par morceaux avec reprise.** Le navigateur envoie le fichier par morceaux de 8 Mo dans
une session d'envoi. Le serveur n'ajoute un morceau que s'il commence exactement là où il en
est, sinon il répond avec sa position réelle : un morceau perdu ou envoyé deux fois ne peut pas
corrompre le fichier. L'état est sur disque et en base, donc il survit à un redémarrage.
Vérifié avec un fichier de 185 Mo : application tuée à mi-envoi, relancée automatiquement,
envoi terminé et fichier reçu identique à l'original (empreinte SHA-256). Un utilisateur n'a
qu'un envoi en cours à la fois, et un envoi abandonné est effacé après 24 h.

**Purge automatique.** Le worker passe toutes les 10 s et supprime les fichiers (dépôt et
résultats) de tout dépôt qui n'est plus le dernier de son propriétaire, ou qui a plus de
`RETENTION_DAYS` jours. Un fichier dont un traitement est en attente ou en cours n'est jamais
supprimé. Les lignes en base sont conservées : l'exigence « contenu des réponses » et les
compteurs de l'administrateur ne dépendent pas des fichiers.

« Le dernier fichier de chacun » repose sur le compte du dépôt. Une règle globale (ne garder
que le dernier fichier du serveur) aurait supprimé les résultats des autres utilisateurs à
chaque dépôt, ce qui est incompatible avec 10 utilisateurs en parallèle.

## Comptes et base de données

**Schéma.** `users` (nom en minuscules, unique ; mot de passe haché ; rôle `user` ou `admin` ;
`disabled_at`), `auth_sessions` (une ligne par connexion), `uploads` et `upload_sessions`
(rattachés à un compte par clé étrangère), `jobs` (rattachés à un dépôt), `workers`. Les
suppressions se propagent en cascade : compte, puis dépôts, puis traitements.

**Les médias ne sont pas dans la base.** Les fichiers (jusqu'à 2 Go) restent sur le disque :
mettre des vidéos dans PostgreSQL gonflerait la base, ralentirait sauvegardes et reprises
d'envoi, et empêcherait de servir un fichier en flux. La base fait le lien : propriétaire,
chemin, taille, durée, liste des fichiers produits. La taille est un `BIGINT` : un fichier de
plus de 2 Gio dépasse un entier de 32 bits.

**Mots de passe.** Hachés avec argon2id (paramètres par défaut d'`argon2-cffi`), jamais
stockés ni journalisés ; longueur bornée à 128 caractères pour qu'un mot de passe démesuré ne
serve pas à saturer le processeur. Un nom inconnu et un mauvais mot de passe prennent le même
temps et reçoivent la même réponse.

**Sessions.** Jeton aléatoire de 256 bits dans un cookie HttpOnly ; la base ne garde que son
empreinte SHA-256, donc une fuite de la base ne donne aucune session utilisable. Chaque
connexion peut être révoquée (déconnexion, changement de mot de passe, désactivation du
compte). Le worker purge les sessions expirées.

**Administrateur.** Un compte comme les autres, de rôle `admin`, avec son propre cookie
(`admin_session`) : une session d'utilisateur n'ouvre pas la console. Conséquence assumée : la
connexion à la console dépend de la base. Un administrateur déjà connecté garde les journaux
et l'état des services pendant une panne de la base, grâce à un cache des sessions déjà
validées ; c'est là qu'il en a le plus besoin.

**Migrations.** Alembic, appliquées au démarrage de chaque service sous un verrou consultatif
PostgreSQL (les trois services démarrent ensemble). Un test compare le schéma produit par les
migrations à celui des modèles. La migration `0001` remplace les tables d'avant les comptes :
leurs dépôts, liés à un cookie anonyme, n'avaient pas de propriétaire.

**Inscription ouverte.** Tout le monde peut créer un compte, donc le nombre de créations est
limité par adresse IP (`MAX_REGISTRATIONS_PER_HOUR`) et les échecs de connexion sont comptés
(5 par minute et par adresse). Ces compteurs sont en mémoire de chaque processus : ils freinent
la devinette de mots de passe sans remplacer un pare-feu ou un reverse proxy.

## Corrections apportées au prototype

| Prototype (`test_pipeline_3.py`) | Version industrialisée |
|---|---|
| Secondes des horodatages SRT sur un chiffre (`00:00:5,000`), fichier illisible par certains lecteurs | Format `HH:MM:SS,mmm` strict, testé |
| Numéros de sous-titres non consécutifs quand un segment est ignoré | Numérotation continue |
| Plantage si Whisper ne fournit pas l'horodatage de fin du dernier segment | Durée par défaut |
| Métadonnées de la piste de sous-titres écrites sur une piste inexistante (`s:s:1`) | Langue et titre sur la piste `s:s:0` |
| Langue de la piste écrite `en`, ignorée par le conteneur mp4 | Code ISO 639-2 (`eng`) |
| Sous-titres de plusieurs minutes d'un seul bloc (fusion des fenêtres) | Segments de quelques secondes (voir faster-whisper ci-dessus) |
| Fichier, type de sortie et GPU codés en dur | Paramètres d'API et de configuration |
| Audio extrait au format d'origine | 16 kHz mono, format natif de Whisper |

## Sécurité et limites connues

- La console d'administration est un service séparé, réservé aux comptes de rôle `admin`, avec
  blocage d'une minute après 5 échecs et sessions de 8 heures enregistrées en base. À publier
  en HTTPS uniquement.
- Les utilisateurs s'authentifient par un compte (inscription ouverte). Un fichier et ses
  résultats sont liés à ce compte : pour tout autre compte, toute lecture ou action répond 404,
  comme pour un identifiant inconnu ; sans connexion, 401. Le cookie de session est HttpOnly,
  SameSite Lax et marqué Secure en HTTPS (ou si `COOKIE_SECURE=true` derrière un proxy). Pas de
  récupération de mot de passe par courriel : l'administrateur le réinitialise
  (`python -m app.users passwd`). À exposer en HTTPS.
- Extensions limitées à `.mp4` / `.wav`, taille plafonnée (`MAX_UPLOAD_MB`), noms de fichiers
  jamais utilisés comme chemins.
- Supprimer un compte directement en base supprime ses lignes en cascade mais pas ses fichiers
  sur le disque ; la purge automatique ne les retrouve plus (elle part des lignes en base).
- La traduction part de l'anglais uniquement (vers les cinq autres langues de l'ONU) : un
  audio dans une autre langue ne peut être livré que dans sa langue d'origine.
- La correction porte sur le texte, pas sur les horaires des sous-titres.
- Traduction automatique généraliste : à relire avant diffusion (noms propres, expressions).
- Les sous-titres incrustés sont figés dans l'image : leur style se choisit avant le
  traitement. Le réglage en direct dans le lecteur ne concerne que la piste de sous-titres.
- Les migrations sont écrites à la main (Alembic) et relues : un test signale tout écart avec les
  modèles.

## Performances et dimensionnement

Exigence : résultat en moins de temps que la durée du média, jusqu'à 10 utilisateurs en
parallèle.

**Raisonnement.** Pire cas : les traitements passent l'un après l'autre. Si un traitement
coûte `r × durée` (r = rapport calcul / durée du média), le dernier de 10 traitements
identiques soumis en même temps attend `10 × r × durée`. L'exigence est donc tenue à coup
sûr tant que **r < 0,1** pour le traitement complet ; le parallélisme (3 traitements par
worker, plusieurs requêtes à la fois sur Triton) donne de la marge au-delà.

### Mesures sur CPU seul

Poste de développement : Ryzen 7 7700 (8 cœurs), 32 Go, **sans GPU utilisable**, lancement
local, échantillon fourni `input.mp4` (148,9 s), `scripts/benchmark.py`.

Transcription seule (8 threads, lots de 8) :

| Modèle | Temps | r |
|---|---|---|
| `whisper-small.en` | 13 s | 0,09 |
| `whisper-medium.en` | 40 s | 0,27 |

Application complète, `whisper-small.en`, attente dans la file comprise :

| Scénario | Résultat le plus lent | × durée | Exigence |
|---|---|---|---|
| 1 utilisateur, vidéo + sous-titres | 15,4 s | 0,10 | tenue |
| 1 utilisateur, vidéo incrustée | 19,2 s | 0,13 | tenue |
| 10 utilisateurs simultanés, sous-titres seuls | 130,4 s | 0,88 | tenue |
| 10 utilisateurs simultanés, vidéo incrustée (`superfast`, défaut) | 135,6 s | 0,91 | tenue |
| 10 utilisateurs simultanés, vidéo incrustée (`veryfast`, ancien défaut) | 156,5 s | 1,05 | manquée de 7,6 s |

Lecture : sur CPU seul, `small.en` est à la limite pour 10 utilisateurs (10 × 13 s de
transcription ≈ 130 s pour 149 s de média) et `medium.en` ne tient que jusqu'à 3 utilisateurs
simultanés environ. L'incrustation (`libx264`, 2 à 4 s ici selon le préréglage) tourne en parallèle de
l'inférence mais lui prend des cœurs. Les trois autres sorties ne ré-encodent rien.

### Sous Docker (CPU)

Même poste, pile Docker complète (Docker Desktop, moteur WSL 2, PostgreSQL), image `cpu`,
`whisper-small.en`, préréglage d'incrustation par défaut :

| Scénario | Résultat le plus lent | × durée | Exigence |
|---|---|---|---|
| 10 utilisateurs simultanés, sous-titres seuls | 102,8 s | 0,69 | tenue |
| 10 utilisateurs simultanés, vidéo incrustée | 118,0 s | 0,79 | tenue |

C'est plus rapide que le lancement direct sous Windows (130,4 s et 135,6 s) : les bibliothèques
de calcul sont mieux servies par Linux. L'exigence des 10 utilisateurs est donc tenue sur CPU
seul, avec de la marge, dans la configuration de déploiement.

Vérifié sur cette pile : construction de l'image, démarrage des quatre services, traitement
réel des quatre types de sortie avec traduction et correction, les tests automatisés rejoués
dans l'image sur PostgreSQL (194 au 20/11/2026, tous passés, image `gpu`), relance automatique de l'application après l'arrêt de son
processus, console d'administration utilisable base de données arrêtée.

### Modèles multilingues

Les modèles `.en` ne comprennent que l'anglais ; les modèles sans suffixe détectent la langue.
Transcription seule sur le poste de développement (CPU, 8 threads) :

| Modèle | Échantillon anglais (2 min 29) | Audio français (38 s) |
|---|---|---|
| `whisper-small.en` | 12,8 s, r = 0,09 | texte inutilisable |
| `whisper-small` | 15,2 s, r = 0,10 | 4,5 s, r = 0,12, langue détectée |
| `whisper-large-v3-turbo` | 29,5 s, r = 0,20 | 11,2 s, r = 0,30, langue détectée |

L'audio français de test est une voix de synthèse, donc plus facile qu'un enregistrement réel :
il valide la détection de langue et la chaîne complète, pas la qualité sur de vraies réunions.

À 10 utilisateurs simultanés, `whisper-small` est à la limite sur CPU : 148,4 s pour 148,9 s
de média en sous-titres seuls, et 166,7 s (objectif manqué) en vidéo incrustée. C'est pourquoi
le modèle par défaut reste `whisper-small.en` ; le multilingue se choisit dans l'interface, et
un GPU sur le serveur cible lèverait ce compromis.

### Incrustation des sous-titres : options mesurées

L'incrustation ré-encode toute la vidéo ; c'est elle qui faisait manquer l'objectif à
10 utilisateurs. Mesures sur le poste de développement, échantillon de 2 min 29 (640×360,
60 images/s) et le même agrandi en 1920×1080, un seul encodage à la fois :

| Encodeur | 360p : temps | 360p : taille | 1080p : temps | 1080p : taille |
|---|---|---|---|---|
| `libx264 veryfast` | 3,9 s | 14,3 Mo | 20,6 s | 58,9 Mo |
| `libx264 superfast` (défaut) | 2,4 s | 24,1 Mo | 16,3 s | 94,9 Mo |
| `libx264 ultrafast` | 1,4 s | 50,3 Mo | 11,3 s | 187,8 Mo |
| `h264_amf` (GPU AMD) | 7,5 s | 29,6 Mo | 14,2 s | 132,7 Mo |

Effet sur le scénario qui échouait (10 utilisateurs simultanés, vidéo incrustée, résultat le
plus lent, une mesure par réglage) :

| `BURN_PRESET` | Résultat le plus lent | × durée | Exigence |
|---|---|---|---|
| `veryfast` | 156,5 s | 1,05 | manquée |
| `superfast` (défaut) | 135,6 s | 0,91 | tenue |
| `ultrafast` | 132,8 s | 0,89 | tenue |

Lecture : un préréglage plus rapide libère des cœurs pour la transcription, d'où un gain bien
supérieur au temps d'encodage économisé. `superfast` suffit à tenir l'exigence pour un fichier
environ 1,7 fois plus lourd ; `ultrafast` n'apporte presque rien de plus et triple le poids.
L'encodeur matériel AMD n'est pas intéressant ici : plus lent en petite définition, et le
décodage comme le rendu des sous-titres restent sur le processeur.

Avec un GPU, la transcription ne prend plus les cœurs : l'encodage peut viser la taille du
fichier. Mesure sur une vidéo de 149 s en 640×360 (15,4 Mo en entrée), un seul encodage,
processeur de 20 cœurs :

| Réglage | Taille | Temps |
|---|---|---|
| `superfast`, CRF 23 (défaut CPU) | 26,3 Mo | 2,5 s |
| `veryfast`, CRF 23 | 15,3 Mo | 4,1 s |
| `medium`, CRF 23 | 18,0 Mo | 7,6 s |
| `medium`, CRF 26 (défaut GPU) | 13,8 Mo | 7,7 s |
| `slow`, CRF 26 | 13,7 Mo | 10,0 s |

`BURN_PRESET` et `BURN_CRF` vides suivent donc `DEVICE` : `superfast` / 23 sur CPU,
`medium` / 26 sur GPU (fichier presque deux fois plus léger, encodage toujours environ 19 fois
plus rapide que la durée de la vidéo).

### Avec GPU (Triton)

Poste portable : Intel Core Ultra 7 255HX, NVIDIA RTX 5070 Ti Laptop (12 Go), pile Docker
complète en version GPU (Docker Desktop, moteur WSL 2) : inférence sur Triton, worker sans
GPU, modèle par défaut `whisper-medium.en`, échantillon `input.mp4` (148,9 s),
`scripts/benchmark.py`. Mesure du 20/11/2026.

| Scénario | Résultat le plus rapide | Résultat le plus lent | × durée (le plus lent) | Exigence |
|---|---|---|---|---|
| 10 utilisateurs simultanés, vidéo incrustée | 19,6 s | 65,1 s | 0,44 | tenue |

Lecture : chaque traitement complet (transcription, incrustation `medium` / CRF 26) coûte
de 14 à 25 s de calcul. Triton traite plusieurs requêtes Whisper à la fois sur une seule copie
des poids (`max_concurrent_requests` = 4) et le worker mène 3 traitements en parallèle : les
résultats arrivent environ toutes les 5 s, et le dernier des 10 en moins de la moitié de la
durée du média. L'exigence est tenue avec `medium.en`, plus précis que le `small.en` imposé
sur CPU, et avec une marge d'environ 2,3 fois.

Le premier traitement après un démarrage de Triton est plus lent (initialisation CUDA) :
lancer un traitement de préchauffage avant une démonstration chronométrée. La page
d'administration affiche ensuite le rapport calcul / durée en continu sur l'usage réel.

Pour rejouer la mesure :
`python scripts/benchmark.py input.mp4 --users 10 --output-type video_embedded`.

Leviers si la charge augmente : `whisper-small.en` par défaut, augmenter `BATCH_SIZE`,
ajouter des vCPU pour l'incrustation, ou lancer un second worker sur une autre machine ou un
second GPU (`docker compose up -d --scale worker=2`).

**Infrastructure estimée**

| Élément | Dimensionnement |
|---|---|
| Machine | 1 instance GPU : 1 GPU 16–24 Go (T4 / L4), 8 vCPU, 32 Go de RAM |
| Disque | 200 Go SSD (fichiers déposés + résultats + modèles) |
| Réseau | 1 IP, HTTPS par reverse proxy |

**Coût.** Chez un hébergeur européen (souveraineté), une instance de cette classe se loue de
l'ordre de 0,75 €/h, soit environ 6 600 €/an allumée en continu, plus le stockage : sous le
plafond de 10 000 €/an. Arrêter l'instance hors heures ouvrées (≈ 50 h/semaine) ramène la
facture à environ 2 000 €/an. Tarif indicatif à confirmer sur la grille du fournisseur retenu
avant la soutenance.

## Serveur d'inférence (Triton) et observabilité

En version GPU, l'inférence est sortie du worker vers un serveur dédié, NVIDIA Triton
Inference Server (`triton/`, `docker-compose.gpu.yml`).

**Pourquoi un serveur d'inférence.** Dans le worker, chaque processus chargeait sa propre copie
des modèles et réclamait le GPU : ajouter un worker doublait la mémoire GPU, et l'inférence ne
pouvait pas évoluer à part du reste (file, ffmpeg, fichiers). Avec Triton, un seul processus
possède le GPU et les poids ; les workers deviennent légers (sans GPU) et se multiplient
librement. Triton apporte aussi ce qu'on attend en production : un contrat d'interface par
modèle (`config.pbtxt`), le chargement et déchargement des modèles à chaud, des sondes de
santé (`/v2/health/ready`) et des métriques Prometheus par modèle.

**Choix du backend.** Le backend Python de Triton, avec le même moteur CTranslate2 que
l'application (faster-whisper, OPUS-MT), plutôt qu'une conversion de Whisper en TensorRT :
mêmes poids et mêmes résultats, sans le coût d'une conversion propre à chaque GPU, pour des
performances déjà largement suffisantes (× 0,06 de la durée sur RTX 5070 Ti). La version
25.06 de Triton est la première série compilée avec CUDA 12.9 : elle prend en charge les GPU
Blackwell (RTX 50xx) tout en gardant les bibliothèques CUDA 12 / cuDNN 9 dont CTranslate2
a besoin.

**Contrats des modèles.**

| Modèle | Entrées | Sorties | Mode |
|---|---|---|---|
| `whisper_*` (5 variantes) | `AUDIO` INT16 [-1] (PCM 16 kHz mono) | `LANGUAGE`, puis par segment `START`, `END`, `TEXT` | decoupled (flux) |
| `translator` | `TEXT` BYTES [-1], `TARGET` BYTES [1] | `TRANSLATION` BYTES [-1] | requête / réponse |

L'audio est envoyé en entiers 16 bits plutôt qu'en flottants : deux fois moins de données
(230 Mo pour 2 h). Les cinq traducteurs partagent un seul modèle Triton, donc un seul
processus et un seul contexte CUDA (environ 2 Go de mémoire GPU économisés). Le mode
`decoupled` de Whisper garde la barre de progression et l'annulation, qu'un appel unique
aurait perdues.

**Mesures** (vidéo de 149 s, RTX 5070 Ti, `whisper_medium_en`) :

| | Modèle dans le worker | Triton |
|---|---|---|
| Transcription seule | – | 8,7 s (× 0,06) |
| Traitement complet (traduction fr + incrustation) | 36,6 s | 21,5 s |
| Chargement d'un autre Whisper à la demande | – | 15 s, une fois |

**Observabilité.** Chaque service publie ses métriques sur un port interne (9100) : requêtes
HTTP par route (et non par URL, pour borner le nombre de séries), traitements par résultat,
durée totale et par étape, et un état lu en base au moment de la collecte (file d'attente,
workers, comptes, stockage), juste quel que soit le worker qui a travaillé. Prometheus
collecte ces métriques et celles de Triton ; Grafana les présente dans un tableau de bord
provisionné. Pour Whisper, Triton ne mesure que la prise en charge des requêtes en flux : la
durée réelle de transcription vient de la mesure du worker (étape `transcription`).

**Limites connues.**

- Sous WSL 2 (Docker Desktop), Triton ne remonte pas l'utilisation du GPU (DCGM limité).
- Le chargement de modèles par l'API de Triton est ouvert à tout client du réseau interne : en
  production, restreindre ces protocoles (`--grpc-restricted-protocol`) au seul worker.
- L'image Triton reste lourde (18,6 Go) : voir ci-dessous.

**Taille de l'image Triton.** L'image officielle `tritonserver:25.06-py3` embarque tous les
backends (TensorRT, PyTorch, ONNX Runtime, OpenVINO, DALI...) : 31 Go sur le disque, alors
que seul le backend Python sert. `triton/Dockerfile` suit la méthode `compose.py` de NVIDIA
(dépôt `triton-inference-server/server`, branche `r25.06`) : partir de l'image minimale
`tritonserver:25.06-py3-min` et n'y copier, depuis l'image complète, que le cœur de Triton
et le backend Python. Deux écarts au fichier généré : les outils de compilation (clang, git)
ne sont pas installés, et de DCGM (métriques GPU, lié au cœur de Triton) seules la
bibliothèque et ses modules sont copiés (15 Mo) au lieu du paquet complet (plus de 2 Go de
proxies cuBLAS et de suite de diagnostic).

| Image | Sur le disque |
|---|---|
| Triton officielle complète + nos modèles | 32,7 Go |
| Triton réduite au backend Python + nos modèles | 18,6 Go (−43 %) |

Le reste vient de l'image minimale elle-même (16,5 Go, dont 7,7 Go de bibliothèques CUDA
et 1 Go d'outils de profilage). Aller plus loin demanderait de partir d'une image CUDA nue
(`nvidia/cuda:12.9.1-cudnn-runtime`, 3,2 Go compressés) en y recopiant à la main les
dépendances du cœur de Triton : environ 9 Go, mais un assemblage à revalider à chaque
version de Triton. vLLM n'est pas une alternative ici : image aussi lourde (10,5 Go
compressés, PyTorch), pensé pour les LLM génératifs, sans prise en charge des traducteurs
OPUS-MT (Marian) ni du flux de segments horodatés dont les sous-titres ont besoin.
