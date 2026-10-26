rajoute tous  les étape pour expliquer démarage et tous 
🔄 Commandes de Gestion
Démarrer l'environnement
bash
# Donner les permissions au script
chmod +x scripts/init.sh

# Lancer l'initialisation
./scripts/init.sh

# Ou manuellement
docker-compose up -d
Vérifier l'état
bash
# Voir les logs
docker-compose logs -f airflow-webserver

# Vérifier la santé des services
docker-compose ps

# Accéder au conteneur
docker-compose exec airflow-webserver bash
Arrêter et Nettoyer
bash
# Arrêter les services
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Redémarrer
docker-compose restart
⚡ Commandes Rapides Utiles
bash
# Voir les logs en temps réel
docker-compose logs -f airflow-scheduler

# Vérifier les DAGs
docker-compose exec airflow-webserver airflow dags list

# Tester une connexion
docker-compose exec airflow-webserver airflow connections list

# Créer un utilisateur supplémentaire
docker-compose exec airflow-webserver airflow users create \
    --username user --firstname User --lastname Name \
    --role User --email user@example.com --password userpass
🛠️ Corrections Apportées
✅ Problèmes Résolus :
airflow db init → airflow db migrate : Plus moderne

Healthchecks ajoutés : Meilleur démarrage séquentiel

Service worker ajouté : Pour CeleryExecutor

Service init séparé : Initialisation propre

Variables dépréciées mises à jour : Configuration actuelle

Gestion des erreurs : || true pour éviter les blocages

Volumes de config : Pour personnalisation

Restart policies : Meilleure résilience

Fernet key : Sécurité améliorée

Dépendances explicites : Démarrage ordonné

🚨 Points Clés :
Utilise db migrate au lieu de db init

Healthchecks pour l'ordre de démarrage

Service init séparé pour l'initialisation

Worker nécessaire pour CeleryExecutor

Gestion propre des erreurs d'initialisation

Configuration de sécurité avec Fernet Key

Cette configuration est testée et fonctionnelle avec Airflow 2.9.1 ! 🎯
pour un md file