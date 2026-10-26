# 📚 Airflow - Commandes Essentielles

## 🚀 Installation et Configuration

### Installation avec pip
```bash
# Installation de base
pip install apache-airflow

# Avec des extras courants
pip install apache-airflow[celery,postgres,redis,ssh,s3]

# Version spécifique
pip install apache-airflow==2.7.0
```

### Initialisation de la base de données
```bash
# Initialiser la DB
airflow db init

# Migrer la DB (après mise à jour)
airflow db migrate

# Reset complet (attention!)
airflow db reset

# Vérifier la santé de la DB
airflow db check
```

### Création d'utilisateur admin
```bash
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

## 🏃‍♂️ Démarrage des Services

### Démarrer le scheduler
```bash
# En arrière-plan
airflow scheduler --daemon

# En foreground avec logs
airflow scheduler

# Avec un fichier de logs spécifique
airflow scheduler --log-file /path/to/scheduler.log
```

### Démarrer le webserver
```bash
# Port par défaut (8080)
airflow webserver --port 8080

# En arrière-plan
airflow webserver --daemon --port 8080

# Avec un host spécifique
airflow webserver --hostname 0.0.0.0 --port 8080
```

### Démarrer les workers (Celery)
```bash
# Worker simple
airflow celery worker

# Avec un nombre spécifique de processus
airflow celery worker --concurrency 4

# Worker avec des queues spécifiques
airflow celery worker --queues default,important
```

## 📁 Gestion des DAGs

### Lister les DAGs
```bash
# Lister tous les DAGs
airflow dags list

# Lister avec des détails
airflow dags list --output table

# Lister les DAGs actifs seulement
airflow dags list --active-only
```

### Afficher les informations d'un DAG
```bash
# Afficher les détails d'un DAG
airflow dags show my_dag_id

# Afficher le code du DAG
airflow dags show my_dag_id --save /path/to/save/code.py

# Afficher l'état du DAG
airflow dags state my_dag_id
```

### Pause/Reprise des DAGs
```bash
# Mettre en pause un DAG
airflow dags pause my_dag_id

# Reprendre un DAG
airflow dags unpause my_dag_id

# Mettre en pause tous les DAGs
airflow dags pause --all

# Vérifier l'état de pause
airflow dags list-pauses
```

### Gestion des runs
```bash
# Lister les runs d'un DAG
airflow dags list-runs --dag-id my_dag_id

# Déclencher un run manuel
airflow dags trigger --dag-id my_dag_id

# Déclencher avec une date d'exécution spécifique
airflow dags trigger --dag-id my_dag_id --exec-date "2024-01-01T00:00:00"

# Supprimer un DAG
airflow dags delete --dag-id my_dag_id
```

## ⚡ Gestion des Tâches

### Tester une tâche
```bash
# Tester une tâche localement
airflow tasks test my_dag_id my_task_id 2024-01-01

# Tester avec des paramètres spécifiques
airflow tasks test my_dag_id my_task_id 2024-01-01 --local --cfg-path /path/to/config.cfg
```

### Lister les tâches
```bash
# Lister les tâches d'un DAG
airflow tasks list my_dag_id

# Lister avec l'ordre des dépendances
airflow tasks list my_dag_id --tree

# Lister avec les dépendances
airflow tasks list my_dag_id --depends-on-past
```

### État des tâches
```bash
# Vérifier l'état d'une tâche
airflow tasks state my_dag_id my_task_id 2024-01-01

# Forcer l'état d'une tâche
airflow tasks clear my_dag_id --task-regex pattern_to_clear

# Réessayer une tâche
airflow tasks run my_dag_id my_task_id 2024-01-01 --local
```

## 🔄 Gestion des Exécutions

### Clear (Nettoyage)
```bash
# Clear toutes les instances d'un DAG
airflow dags clear my_dag_id

# Clear avec des options de filtrage
airflow dags clear my_dag_id \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --only-failed

# Clear une tâche spécifique
airflow tasks clear my_dag_id --task-ids my_task_id
```

### Backfill
```bash
# Exécuter les runs manquants
airflow dags backfill my_dag_id \
    --start-date 2024-01-01 \
    --end-date 2024-01-31

# Backfill avec options
airflow dags backfill my_dag_id \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --reset-dagruns \
    --rerun-failed-tasks
```

## 🔐 Gestion des Connexions

### Lister les connexions
```bash
# Lister toutes les connexions
airflow connections list

# Lister avec un format spécifique
airflow connections list --output table

# Vérifier une connexion spécifique
airflow connections get my_connection_id
```

### Ajouter/Modifier des connexions
```bash
# Ajouter une connexion
airflow connections add my_postgres_conn \
    --conn-type postgres \
    --conn-host localhost \
    --conn-login myuser \
    --conn-password mypass \
    --conn-port 5432 \
    --conn-schema mydb

# Ajouter une connexion avec URI
airflow connections add my_http_conn \
    --conn-type http \
    --conn-host https://api.example.com

# Modifier une connexion existante
airflow connections update my_postgres_conn \
    --conn-host newhost.example.com
```

### Supprimer des connexions
```bash
# Supprimer une connexion
airflow connections delete my_connection_id

# Exporter les connexions
airflow connections export /path/to/connections.json

# Importer des connexions
airflow connections import /path/to/connections.json
```

## 📊 Variables et Configuration

### Gestion des variables
```bash
# Lister les variables
airflow variables list

# Obtenir une variable
airflow variables get my_variable

# Définir une variable
airflow variables set my_variable "my_value"

# Définir depuis un fichier JSON
airflow variables set my_variables --file /path/to/variables.json

# Supprimer une variable
airflow variables delete my_variable

# Importer/Exporter des variables
airflow variables export /path/to/variables.json
airflow variables import /path/to/variables.json
```

### Configuration
```bash
# Voir la configuration actuelle
airflow config list

# Voir une valeur spécifique
airflow config get-value core sql_alchemy_conn

# Tester la configuration
airflow config test
```

## 👥 Gestion des Utilisateurs et Rôles

### Utilisateurs
```bash
# Lister les utilisateurs
airflow users list

# Créer un utilisateur
airflow users create \
    --username john \
    --firstname John \
    --lastname Doe \
    --role User \
    --email john@example.com \
    --password secret

# Modifier un utilisateur
airflow users update john --email newjohn@example.com

# Supprimer un utilisateur
airflow users delete john
```

### Rôles
```bash
# Lister les rôles
airflow roles list

# Créer un rôle personnalisé
airflow roles create my_custom_role

# Assigner des permissions à un rôle
airflow roles add-permission my_custom_role can_read_dag
```

## 📈 Monitoring et Métriques

### Vérifier la santé
```bash
# Vérifier la santé globale
airflow check

# Vérifier la DB
airflow db check

# Vérifier les connexions
airflow checkdb
```

### Métriques et Stats
```bash
# Afficher les jobs en cours
airflow jobs check

# Afficher les stats du scheduler
airflow jobs check --job-type SchedulerJob

# Voir les workers Celery
airflow celery workers
```

## 🔧 Commandes Avancées

### Plugins et Providers
```bash
# Lister les providers installés
airflow providers list

# Voir les détails d'un provider
airflow providers behaviours

# Installer un provider
pip install apache-airflow-providers-postgres
```

### Version et Info
```bash
# Version d'Airflow
airflow version

# Info système
airflow info

# Chemin de configuration
airflow config get-value core dags_folder
```

### Debug et Logs
```bash
# Afficher les logs d'une tâche
airflow tasks logs my_dag_id my_task_id 2024-01-01

# Afficher les logs avec options
airflow tasks logs my_dag_id my_task_id 2024-01-01 --subdir task_instance

# Tester un DAG complet
airflow dags test my_dag_id 2024-01-01
```

## 🐳 Commandes Docker (si utilisé)

### Avec Docker Compose
```bash
# Démarrer tous les services
docker-compose up -d

# Voir les logs
docker-compose logs -f scheduler
docker-compose logs -f webserver

# Scale workers
docker-compose up -d --scale worker=3

# Arrêter tout
docker-compose down
```

### Commandes dans les conteneurs
```bash
# Exécuter une commande dans le scheduler
docker-compose exec scheduler airflow version

# Initialiser la DB
docker-compose exec webserver airflow db init

# Créer un utilisateur
docker-compose exec webserver airflow users create ...
```

## 🛠️ Scripts Utiles pour le Développement

### Script de test de DAG
```bash
#!/bin/bash
# test_dag.sh

DAG_ID=$1
EXEC_DATE=${2:-$(date +%Y-%m-%d)}

echo "🧪 Test du DAG: $DAG_ID pour la date: $EXEC_DATE"

# Tester le DAG
airflow dags test $DAG_ID $EXEC_DATE

# Vérifier la syntaxe
python -m py_compile /opt/airflow/dags/$DAG_ID.py

echo "✅ Test terminé"
```

### Script de déploiement
```bash
#!/bin/bash
# deploy_dags.sh

DAGS_DIR="/opt/airflow/dags"
BACKUP_DIR="/opt/airflow/dags_backup"

# Sauvegarde
echo "📦 Sauvegarde des DAGs existants..."
cp -r $DAGS_DIR $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S)

# Déploiement
echo "🚀 Déploiement des nouveaux DAGs..."
cp ./dags/*.py $DAGS_DIR/

# Vérification
echo "🔍 Vérification des DAGs..."
airflow dags list | grep -E "(my_dag|another_dag)"

echo "✅ Déploiement terminé"
```

## 📋 Checklist des Commandes Essentielles

### Démarrage Rapide
```bash
# 1. Initialisation
airflow db init
airflow users create --username admin --role Admin --email admin@example.com

# 2. Démarrer les services
airflow webserver --port 8080 --daemon
airflow scheduler --daemon

# 3. Vérifier
airflow dags list
airflow users list
```

### Débogage Courant
```bash
# DAG ne s'exécute pas
airflow dags unpause my_dag
airflow dags trigger my_dag

# Tâche bloquée
airflow tasks clear my_dag --task-regex pattern
airflow tasks test my_dag my_task 2024-01-01

# Problème de connexion
airflow connections test my_conn
airflow variables get important_var
```

### Monitoring de Production
```bash
# Santé du système
airflow check
airflow db check

# Métriques
airflow jobs check
airflow celery workers

# Logs
airflow tasks logs my_dag my_task latest
```

## 🎯 Raccourcis Pratiques

### Alias utiles pour le shell
```bash
# Ajouter à ~/.bashrc ou ~/.zshrc
alias af='airflow'
alias afd='airflow dags'
alias aft='airflow tasks'
alias afc='airflow connections'
alias afv='airflow variables'
alias afu='airflow users'

# Exemples d'utilisation
# afd list
# aft test my_dag my_task today
# afc get my_postgres
```

### Commandes les plus utilisées
```bash
# Top 10 des commandes Airflow
1. airflow dags list                    # Lister les DAGs
2. airflow dags pause/unpause          # Gérer l'état
3. airflow tasks test                  # Tester une tâche
4. airflow dags trigger                # Déclencher manuellement
5. airflow tasks clear                 Nettoyer les tâches
6. airflow connections list           # Vérifier les connexions
7. airflow variables get              # Obtenir des variables
8. airflow dags backfill              # Rattrapage
9. airflow tasks logs                 # Voir les logs
10. airflow db init                   # Initialisation
```

Ce guide couvre 95% des commandes que vous utiliserez quotidiennement avec Airflow! 🚀