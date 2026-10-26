# 🪐 Pluto : Explication Détaillée d'Airflow

## 🎯 1. DAG (Directed Acyclic Graph) - La Recette Complète

### 📚 Explication Détaillée
Un **DAG** est le cœur d'Airflow. Imaginez-le comme une **recette de cuisine complète** :
- **Directed** : Les étapes ont un ordre précis (on ne met pas le gâteau au four avant de mélanger les ingrédients)
- **Acyclic** : Pas de boucles infinies (on ne peut pas revenir en arrière indéfiniment)
- **Graph** : Représentation visuelle des dépendances entre les tâches

**Caractéristiques principales :**
- `dag_id` : Nom unique de votre recette
- `schedule_interval` : Fréquence d'exécution (quotidienne, horaire, etc.)
- `start_date` : Date de début de la recette
- `catchup` : Rattrapage des exécutions manquées ou non

### 🍳 Illustration Culinaire
```python
from airflow import DAG
from datetime import datetime, timedelta

# Notre recette de pain perdu
with DAG(
    dag_id="recette_pain_perdu",           # Nom de la recette
    description="Recette familiale de pain perdu",
    start_date=datetime(2024, 1, 1),       # Date de création de la recette
    schedule_interval="@daily",            # On peut en faire tous les jours
    catchup=False,                         # On ne rattrape pas les jours manqués
    default_args={
        'owner': 'chef_pluto',             # Le chef responsable
        'retries': 2,                      # Si ça rate, on réessaie 2 fois
        'retry_delay': timedelta(minutes=5) # On attend 5 min entre chaque essai
    },
    tags=['breakfast', 'french', 'family'] # Tags pour retrouver la recette
) as dag:
    
    # Ici viendront toutes les étapes de la recette
    print("📖 Recette de pain perdu chargée!")
```

### 🔧 Code Détaillé avec Explications
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd

# Arguments par défaut pour TOUTES les tâches du DAG
default_args = {
    'owner': 'data_team',           # Qui est responsable
    'depends_on_past': False,       # Ne dépend pas des runs précédents
    'email': ['alert@mycompany.com'], # Emails pour les alertes
    'email_on_failure': True,       # Email si échec
    'email_on_retry': False,        # Pas d'email sur les retry
    'retries': 3,                   # Nombre de tentatives en cas d'échec
    'retry_delay': timedelta(minutes=10) # Délai entre les retry
}

# Création du DAG avec tous ses paramètres
with DAG(
    dag_id='data_processing_pipeline',
    default_args=default_args,
    description='Pipeline de traitement des données clients',
    schedule_interval=timedelta(hours=1),  # Toutes les heures
    start_date=datetime(2024, 1, 1, 0, 0), # 1er Janvier 2024 à minuit
    end_date=datetime(2024, 12, 31, 23, 59), # Jusqu'au 31 Décembre
    catchup=True,                    # Rattrape les exécutions manquées
    max_active_runs=3,               # Maximum 3 exécutions simultanées
    concurrency=10,                  # Maximum 10 tâches simultanées
    tags=['data', 'processing', 'etl']
) as dag:
    
    def log_dag_start():
        """Fonction exécutée au début du DAG"""
        print(f"🚀 Début du pipeline à {datetime.now()}")
        return "DAG démarré avec succès"
    
    start_task = PythonOperator(
        task_id='demarrage_pipeline',
        python_callable=log_dag_start
    )
```

---

## 🎯 2. TASKS - Les Étapes Individuelles

### 📚 Explication Détaillée
Une **Task** représente une **étape individuelle** dans votre DAG. Chaque task :
- Est une unité de travail indépendante
- Peut être exécutée sur différents workers
- A un état (success, failed, running, etc.)
- Peut avoir des dépendances avec d'autres tasks

**Types d'opérateurs principaux :**
- `PythonOperator` : Exécute une fonction Python
- `BashOperator` : Exécute une commande shell
- `EmailOperator` : Envoie un email
- `Sensor` : Attend qu'une condition soit remplie

### 🍳 Illustration Culinaire
```python
from airflow.operators.python import PythonOperator

def preparer_pain():
    """Couper le pain en tranches"""
    print("🍞 Je coupe 6 tranches de pain rassis")
    return "pain_coupe"

def preparer_lait_oeufs():
    """Préparer le mélange lait/œufs"""
    print("🥛 Je mélange 2 œufs avec 25cl de lait")
    print("🍶 J'ajoute une pincée de vanille et de cannelle")
    return "melange_pret"

def tremper_pain(**context):
    """Tremper le pain dans le mélange"""
    # Récupère le résultat de la tâche précédente
    melange = context['task_instance'].xcom_pull(task_ids='preparer_lait_oeufs')
    pain = context['task_instance'].xcom_pull(task_ids='preparer_pain')
    
    print(f"🫗 Je trempe {pain} dans {melange}")
    return "pain_trempe"

def cuire_pain(**context):
    """Cuire le pain à la poêle"""
    pain_trempe = context['task_instance'].xcom_pull(task_ids='tremper_pain')
    print(f"🍳 Je fais cuire {pain_trempe} à la poêle beurrée")
    print("🔥 Cuisson 3 minutes de chaque côté")
    return "pain_perdu_cuit"

# Création des tâches
etape1 = PythonOperator(
    task_id="preparer_pain",
    python_callable=preparer_pain
)

etape2 = PythonOperator(
    task_id="preparer_lait_oeufs", 
    python_callable=preparer_lait_oeufs
)

etape3 = PythonOperator(
    task_id="tremper_pain",
    python_callable=tremper_pain
)

etape4 = PythonOperator(
    task_id="cuire_pain",
    python_callable=cuire_pain
)
```

### 🔧 Code Détaillé avec Gestion d'Erreurs
```python
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
import requests
import json

def telecharger_donnees_api():
    """Télécharge des données depuis une API avec gestion d'erreur"""
    try:
        print("📡 Connexion à l'API...")
        response = requests.get(
            'https://api.mon-service.com/donnees',
            timeout=30,  # Timeout de 30 secondes
            headers={'Authorization': 'Bearer mon-token'}
        )
        
        # Vérifier le statut HTTP
        if response.status_code != 200:
            raise AirflowException(f"Erreur API: {response.status_code}")
        
        data = response.json()
        print(f"✅ Données téléchargées: {len(data)} enregistrements")
        return data
        
    except requests.exceptions.Timeout:
        raise AirflowException("Timeout de l'API - trop long à répondre")
    except requests.exceptions.ConnectionError:
        raise AirflowException("Impossible de se connecter à l'API")
    except json.JSONDecodeError:
        raise AirflowException("Réponse API invalide - JSON corrompu")

def traiter_donnees(**context):
    """Traite les données téléchargées"""
    try:
        # Récupérer les données de la tâche précédente
        donnees_brutes = context['task_instance'].xcom_pull(task_ids='telecharger_donnees')
        
        if not donnees_brutes:
            raise AirflowException("Aucune donnée à traiter")
        
        print(f"🔧 Traitement de {len(donnees_brutes)} enregistrements...")
        
        # Exemple de traitement
        donnees_traitees = []
        for item in donnees_brutes:
            # Nettoyage des données
            item_propre = {
                'id': item.get('id'),
                'nom': item.get('name', '').strip().title(),
                'valeur': float(item.get('value', 0)),
                'date_creation': item.get('created_at')
            }
            donnees_traitees.append(item_propre)
        
        print(f"✅ Données traitées: {len(donnees_traitees)} enregistrements nettoyés")
        return donnees_traitees
        
    except Exception as e:
        raise AirflowException(f"Erreur lors du traitement: {str(e)}")

def sauvegarder_resultats(**context):
    """Sauvegarde les résultats finaux"""
    donnees_finales = context['task_instance'].xcom_pull(task_ids='traiter_donnees')
    
    if donnees_finales:
        # Sauvegarde dans un fichier (dans un vrai cas, ce serait une base de données)
        with open('/tmp/donnees_traitees.json', 'w') as f:
            json.dump(donnees_finales, f, indent=2)
        
        print(f"💾 Données sauvegardées: {len(donnees_finales)} enregistrements")
        return f"sauvegarde_reussie_{len(donnees_finales)}_items"
    else:
        raise AirflowException("Aucune donnée à sauvegarder")

# Création des tâches avec gestion d'erreur
telechargement = PythonOperator(
    task_id='telecharger_donnees',
    python_callable=telecharger_donnees_api,
    retries=2,  # 2 tentatives supplémentaires en cas d'échec
    retry_delay=timedelta(minutes=1)
)

traitement = PythonOperator(
    task_id='traiter_donnees',
    python_callable=traiter_donnees,
    retries=1
)

sauvegarde = PythonOperator(
    task_id='sauvegarder_resultats',
    python_callable=sauvegarder_resultats
)
```

---

## 🎯 3. DÉPENDANCES - L'Ordre des Opérations

### 📚 Explication Détaillée
Les **dépendances** définissent **l'ordre d'exécution** des tâches. C'est comme dire :
- "Il faut mélanger les ingrédients AVANT de mettre au four"
- "La décoration se fait APRÈS la cuisson"

**Deux syntaxes possibles :**
- **Opérateur bitshift** : `tache1 >> tache2 >> tache3`
- **Méthodes** : `tache2.set_upstream(tache1)`

### 🍳 Illustration Culinaire
```python
# Notre recette de cookies avec dépendances complexes

def prechauffer_four():
    print("🔥 Préchauffer le four à 180°C")

def melanger_ingredients():
    print("🥄 Mélanger beurre, sucre, œufs")
    print("🌾 Ajouter farine et pépites de chocolat")

def former_cookies():
    print("👐 Former des boules de pâte")
    return "12_boules_pretes"

def cuire_cookies(**context):
    boules = context['task_instance'].xcom_pull(task_ids='former_cookies')
    print(f"🍪 Enfourner {boules} pendant 12 minutes")
    return "cookies_cuits"

def laisser_refroidir(**context):
    cookies = context['task_instance'].xcom_pull(task_ids='cuire_cookies')
    print(f"❄️ Laisser refroidir {cookies} sur une grille")

# Création des tâches
prechauffage = PythonOperator(task_id="prechauffer_four", python_callable=prechauffer_four)
melange = PythonOperator(task_id="melanger_ingredients", python_callable=melanger_ingredients)
formation = PythonOperator(task_id="former_cookies", python_callable=former_cookies)
cuisson = PythonOperator(task_id="cuire_cookies", python_callable=cuire_cookies)
refroidissement = PythonOperator(task_id="laisser_refroidir", python_callable=laisser_refroidir)

# Définition des dépendances - METHODE 1: Opérateur bitshift
prechauffage >> melange >> formation >> cuisson >> refroidissement

# METHODE 2: Méthodes set_upstream/set_downstream (équivalent)
# formation.set_upstream(melange)
# cuisson.set_upstream(formation)
# refroidissement.set_upstream(cuisson)
```

### 🔧 Code Détaillé avec Dépendances Complexes
```python
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator

# Tâches de début/fin
debut = DummyOperator(task_id='debut_pipeline')
fin = DummyOperator(task_id='fin_pipeline')

# Tâches parallèles
def extraire_donnees_clients():
    print("👥 Extraction données clients...")
    return "clients_extraits"

def extraire_donnees_produits():
    print("📦 Extraction données produits...") 
    return "produits_extraits"

def extraire_donnees_ventes():
    print("💰 Extraction données ventes...")
    return "ventes_extraits"

extraction_clients = PythonOperator(
    task_id='extraire_clients',
    python_callable=extraire_donnees_clients
)

extraction_produits = PythonOperator(
    task_id='extraire_produits',
    python_callable=extraire_donnees_produits
)

extraction_ventes = PythonOperator(
    task_id='extraire_ventes',
    python_callable=extraire_donnees_ventes
)

# Tâches de transformation
def transformer_donnees(**context):
    clients = context['ti'].xcom_pull(task_ids='extraire_clients')
    produits = context['ti'].xcom_pull(task_ids='extraire_produits')
    ventes = context['ti'].xcom_pull(task_ids='extraire_ventes')
    
    print(f"🔨 Transformation des données: {clients}, {produits}, {ventes}")
    return "donnees_transformees"

transformation = PythonOperator(
    task_id='transformer_donnees',
    python_callable=transformer_donnees
)

# Tâches de chargement
def charger_entrepot():
    print("🏪 Chargement dans l'entrepôt de données...")
    return "entrepot_charge"

def charger_rapports():
    print("📊 Chargement pour les rapports...")
    return "rapports_prets"

chargement_entrepot = PythonOperator(
    task_id='charger_entrepot',
    python_callable=charger_entrepot
)

chargement_rapports = PythonOperator(
    task_id='charger_rapports',
    python_callable=charger_rapports
)

# DÉPENDANCES COMPLEXES
# Début → extractions (en parallèle)
debut >> [extraction_clients, extraction_produits, extraction_ventes]

# Extractions → transformation
[extraction_clients, extraction_produits, extraction_ventes] >> transformation

# Transformation → chargements (en parallèle)  
transformation >> [chargement_entrepot, chargement_rapports]

# Chargements → fin
[chargement_entrepot, chargement_rapports] >> fin
```

---

## 🎯 4. XCOM - Échange de Données entre Tâches

### 📚 Explication Détaillée
**XCom** (Cross-Communication) permet aux tâches de **partager des données**. C'est comme passer un bol d'ingrédients d'un chef à un autre.

**Fonctionnement :**
- `xcom_push()` : Envoyer des données
- `xcom_pull()` : Récupérer des données
- Limité à ~48KB (pour les petites données)
- Par défaut, la valeur de retour d'une tâche est automatiquement poussée en XCom

### 🍳 Illustration Culinaire
```python
def chef_patissier_prepare_creme():
    """Le chef pâtissier prépare la crème"""
    recette_creme = {
        'ingredients': ['crème fraîche', 'sucre', 'vanille'],
        'quantites': ['250ml', '50g', '1 gousse'],
        'instructions': 'Fouetter la crème avec le sucre et la vanille'
    }
    print("🧁 Chef pâtissier: Je prépare la crème chantilly")
    return recette_creme  # Automatiquement poussé en XCom

def chef_cuisinier_prepare_fruits(**context):
    """Le chef cuisinier prépare les fruits"""
    # Récupère la recette de la crème
    recette_creme = context['task_instance'].xcom_pull(
        task_ids='chef_patissier_prepare_creme'
    )
    
    print(f"🍓 Chef cuisinier: Je vois que le pâtissier a préparé: {recette_creme['ingredients']}")
    print("🍓 Je coupe des fraises et des framboises pour l'accompagnement")
    
    fruits_prepares = {
        'fruits': ['fraises', 'framboises', 'myrtilles'],
        'quantite': '250g'
    }
    return fruits_prepares

def assemble_dessert(**context):
    """Assemblage final du dessert"""
    # Récupère les préparations des deux chefs
    creme = context['ti'].xcom_pull(task_ids='chef_patissier_prepare_creme')
    fruits = context['ti'].xcom_pull(task_ids='chef_cuisinier_prepare_fruits')
    
    print("🎂 ASSEMBLAGE FINAL:")
    print(f"   - Crème: {creme['ingredients']}")
    print(f"   - Fruits: {fruits['fruits']}")
    print("   - Dressage dans des coupes")
    
    return "dessert_assemblé_et_prêt_à_servir"

# Création des tâches
patissier = PythonOperator(
    task_id="chef_patissier_prepare_creme",
    python_callable=chef_patissier_prepare_creme
)

cuisinier = PythonOperator(
    task_id="chef_cuisinier_prepare_fruits",
    python_callable=chef_cuisinier_prepare_fruits
)

assembleur = PythonOperator(
    task_id="assemble_dessert",
    python_callable=assemble_dessert
)

# Dépendances
patissier >> cuisinier >> assembleur
```

### 🔧 Code Détaillé avec XCom Avancé
```python
from airflow.operators.python import PythonOperator
from airflow.models import XCom

def traitement_etape_1():
    """Première étape de traitement"""
    donnees_initiales = {
        'fichier_source': 'data_2024.csv',
        'nombre_lignes': 10000,
        'colonnes': ['id', 'nom', 'email', 'date_inscription'],
        'statut': 'brut'
    }
    
    # METHODE 1: Return automatique (recommandé)
    return donnees_initiales

def traitement_etape_2(**context):
    """Deuxième étape avec récupération XCom"""
    # Récupération avec différentes méthodes
    donnees_etape1 = context['ti'].xcom_pull(
        task_ids='traitement_etape_1',
        key='return_value'  # Valeur par défaut
    )
    
    print(f"📥 Données reçues de l'étape 1: {donnees_etape1}")
    
    # Traitement
    donnees_etape1['statut'] = 'nettoye'
    donnees_etape1['lignes_traitees'] = 9500
    donnees_etape1['lignes_erreur'] = 500
    
    # METHODE 2: Push manuel avec clé personnalisée
    context['ti'].xcom_push(key='donnees_nettoyees', value=donnees_etape1)
    
    return "nettoyage_termine"

def traitement_etape_3(**context):
    """Troisième étape avec XCom multiple"""
    # Récupération de plusieurs valeurs XCom
    statut_nettoyage = context['ti'].xcom_pull(task_ids='traitement_etape_2', key='return_value')
    donnees_nettoyees = context['ti'].xcom_pull(task_ids='traitement_etape_2', key='donnees_nettoyees')
    
    print(f"📊 Statut: {statut_nettoyage}")
    print(f"📋 Données nettoyées: {donnees_nettoyees}")
    
    # Traitement final
    resultat_final = {
        'fichier_sortie': 'data_2024_traite.csv',
        'statistiques': {
            'total_lignes': donnees_nettoyees['nombre_lignes'],
            'lignes_valides': donnees_nettoyees['lignes_traitees'],
            'taux_reussite': (donnees_nettoyees['lignes_traitees'] / donnees_nettoyees['nombre_lignes']) * 100
        },
        'date_traitement': str(context['execution_date'])
    }
    
    # Push multiple avec différentes clés
    context['ti'].xcom_push(key='resultat_final', value=resultat_final)
    context['ti'].xcom_push(key='fichier_sortie', value=resultat_final['fichier_sortie'])
    context['ti'].xcom_push(key='statistiques', value=resultat_final['statistiques'])
    
    return resultat_final

def generer_rapport(**context):
    """Génère un rapport à partir de tous les XCom"""
    # Récupération de TOUS les XCom de l'exécution
    resultat_final = context['ti'].xcom_pull(task_ids='traitement_etape_3', key='resultat_final')
    fichier_sortie = context['ti'].xcom_pull(task_ids='traitement_etape_3', key='fichier_sortie')
    stats = context['ti'].xcom_pull(task_ids='traitement_etape_3', key='statistiques')
    
    print("📈 RAPPORT DE TRAITEMENT:")
    print(f"   Fichier: {fichier_sortie}")
    print(f"   Statistiques: {stats}")
    print(f"   Résultat complet: {resultat_final}")
    
    return "rapport_généré"

# Création du pipeline
etape1 = PythonOperator(task_id='traitement_etape_1', python_callable=traitement_etape_1)
etape2 = PythonOperator(task_id='traitement_etape_2', python_callable=traitement_etape_2)
etape3 = PythonOperator(task_id='traitement_etape_3', python_callable=traitement_etape_3)
rapport = PythonOperator(task_id='generer_rapport', python_callable=generer_rapport)

# Dépendances
etape1 >> etape2 >> etape3 >> rapport
```

---

## 🎯 5. SENSORS - Attente d'Événements

### 📚 Explication Détaillée
Les **Sensors** sont des tâches spéciales qui **attendent qu'une condition soit remplie** avant de continuer. C'est comme attendre que l'eau bout avant d'ajouter les pâtes.

**Types courants :**
- `FileSensor` : Attend qu'un fichier existe
- `ExternalTaskSensor` : Attend qu'une autre tâche soit terminée
- `PythonSensor` : Condition personnalisée en Python

### 🍳 Illustration Culinaire
```python
from airflow.sensors.filesystem import FileSensor
from airflow.sensors.python import PythonSensor
from datetime import datetime, timedelta

def attendre_livraison_ingredients():
    """Attendre que les courses soient livrées"""
    print("📦 En attente de la livraison des ingrédients...")
    # Simulation: vérifier si le fichier de livraison existe
    import os
    return os.path.exists('/cuisine/livraison/ingredients.txt')

def verifier_temperature_four():
    """Vérifier que le four est à la bonne température"""
    temperature_actuelle = 175  # Simulation
    temperature_cible = 180
    
    print(f"🌡️  Température actuelle: {temperature_actuelle}°C")
    print(f"🎯 Température cible: {temperature_cible}°C")
    
    return temperature_actuelle >= temperature_cible

# Sensor pour attendre les ingrédients
sensor_ingredients = PythonSensor(
    task_id="attendre_ingredients",
    python_callable=attendre_livraison_ingredients,
    timeout=300,  # 5 minutes max d'attente
    mode="reschedule",  # Libère le worker pendant l'attente
    poke_interval=30  # Vérifie toutes les 30 secondes
)

# Sensor pour la température du four
sensor_temperature = PythonSensor(
    task_id="verifier_temperature_four",
    python_callable=verifier_temperature_four,
    timeout=600,  # 10 minutes max
    mode="poke",  # Garde le worker occupé
    poke_interval=10  # Vérifie toutes les 10 secondes
)

def preparer_plat():
    """Préparer le plat une fois les conditions remplies"""
    print("👨‍🍳 Toutes les conditions sont remplies! Je commence la préparation...")

preparation = PythonOperator(
    task_id="preparer_plat",
    python_callable=preparer_plat
)

# Dépendances: attendre les conditions AVANT de préparer
sensor_ingredients >> sensor_temperature >> preparation
```

### 🔧 Code Détaillé avec Sensors Avancés
```python
from airflow.sensors.filesystem import FileSensor
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.sensors.python import PythonSensor
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import json

# Sensor 1: Attendre un fichier de données
sensor_fichier_donnees = FileSensor(
    task_id="attendre_fichier_donnees",
    filepath="/data/incoming/daily_data.csv",
    timeout=3600,  # 1 heure max d'attente
    mode="reschedule",
    poke_interval=60,  # Vérifie toutes les minutes
    soft_fail=False,  # Échoue si timeout dépassé
    fs_conn_id="fs_default"  # Connection ID pour le système de fichiers
)

# Sensor 2: Attendre qu'un DAG externe soit terminé
sensor_dag_externe = ExternalTaskSensor(
    task_id="attendre_dag_nettoyage",
    external_dag_id="data_cleaning_pipeline",
    external_task_id="fin_nettoyage",
    allowed_states=['success'],
    execution_delta=timedelta(hours=1),  # Attendre l'exécution d'il y a 1h
    timeout=7200,  # 2 heures max
    mode="reschedule",
    poke_interval=120  # Vérifie toutes les 2 minutes
)

# Sensor 3: Condition personnalisée - API disponible
def verifier_api_disponible():
    """Vérifie si l'API de données est disponible"""
    try:
        response = requests.get(
            'https://api.mon-service.com/health',
            timeout=10
        )
        if response.status_code == 200:
            health_data = response.json()
            return health_data.get('status') == 'healthy'
        return False
    except requests.exceptions.RequestException:
        return False

sensor_api = PythonSensor(
    task_id="verifier_api_disponible",
    python_callable=verifier_api_disponible,
    timeout=1800,  # 30 minutes max
    mode="poke",
    poke_interval=30  # Vérifie toutes les 30 secondes
)

# Sensor 4: Attendre un certain nombre de fichiers
def verifier_fichiers_complets():
    """Vérifie que tous les fichiers nécessaires sont présents"""
    fichiers_requis = [
        '/data/incoming/clients.csv',
        '/data/incoming/produits.csv', 
        '/data/incoming/ventes.csv',
        '/data/incoming/config.json'
    ]
    
    fichiers_presents = []
    for fichier in fichiers_requis:
        try:
            with open(fichier, 'r'):
                fichiers_presents.append(fichier)
        except FileNotFoundError:
            print(f"⏳ Fichier manquant: {fichier}")
    
    if len(fichiers_presents) == len(fichiers_requis):
        print("✅ Tous les fichiers sont présents!")
        return True
    else:
        print(f"📁 Fichiers présents: {len(fichiers_presents)}/{len(fichiers_requis)}")
        return False

sensor_fichiers_multiple = PythonSensor(
    task_id="verifier_fichiers_complets",
    python_callable=verifier_fichiers_complets,
    timeout=3600,
    mode="reschedule", 
    poke_interval=60
)

# Tâche de traitement principal
def traitement_principal(**context):
    """Traitement principal qui s'exécute une fois tous les sensors satisfaits"""
    execution_date = context['execution_date']
    print(f"🚀 Début du traitement principal à {execution_date}")
    
    # Logique de traitement...
    print("📊 Traitement des données en cours...")
    
    return "traitement_termine"

traitement = PythonOperator(
    task_id="traitement_principal",
    python_callable=traitement_principal
)

# Dépendances: Tous les sensors doivent être satisfaits avant le traitement
[sensor_fichier_donnees, sensor_dag_externe, sensor_api, sensor_fichiers_multiple] >> traitement
```

---

## 🎯 6. BRANCHING - Prise de Décision

### 📚 Explication Détaillée
Le **Branching** permet de **choisir un chemin d'exécution** selon une condition. C'est comme décider quelle recette faire selon les ingrédients disponibles.

**Fonctionnement :**
- `BranchPythonOperator` : Prend une décision basée sur Python
- Retourne le `task_id` de la prochaine tâche à exécuter
- Les autres branches sont ignorées

### 🍳 Illustration Culinaire
```python
from airflow.operators.python import BranchPythonOperator
from airflow.operators.dummy import DummyOperator

def choisir_recette_selon_saison(**context):
    """Choisit la recette selon la saison"""
    execution_date = context['execution_date']
    mois = execution_date.month
    
    # Déterminer la saison
    if 3 <= mois <= 5:
        saison = "printemps"
        return "preparer_salade_printaniere"
    elif 6 <= mois <= 8:
        saison = "ete" 
        return "preparer_gazpacho"
    elif 9 <= mois <= 11:
        saison = "automne"
        return "preparer_soupe_citrouille"
    else:
        saison = "hiver"
        return "preparer_raclette"

def choisir_dessert_selon_ingredients():
    """Choisit le dessert selon les ingrédients disponibles"""
    ingredients_disponibles = ['chocolat', 'œufs', 'farine', 'fruits']
    
    if 'chocolat' in ingredients_disponibles and 'œufs' in ingredients_disponibles:
        return "preparer_fondant_chocolat"
    elif 'fruits' in ingredients_disponibles:
        return "preparer_salade_fruits"
    else:
        return "preparer_creme_dessert"

# Tâche de décision principale
choix_plat_principal = BranchPythonOperator(
    task_id="choisir_plat_principal",
    python_callable=choisir_recette_selon_saison
)

# Tâche de décision dessert
choix_dessert = BranchPythonOperator(
    task_id="choisir_dessert",
    python_callable=choisir_dessert_selon_ingredients
)

# Tâches pour les plats principaux
salade = DummyOperator(task_id="preparer_salade_printaniere")
gazpacho = DummyOperator(task_id="preparer_gazpacho")
soupe = DummyOperator(task_id="preparer_soupe_citrouille")
raclette = DummyOperator(task_id="preparer_raclette")

# Tâches pour les desserts
fondant = DummyOperator(task_id="preparer_fondant_chocolat")
salade_fruits = DummyOperator(task_id="preparer_salade_fruits")
creme = DummyOperator(task_id="preparer_creme_dessert")

# Tâche de fin
fin = DummyOperator(task_id="service_repas")

# Dépendances complexes
choix_plat_principal >> [salade, gazpacho, soupe, raclette]
[salade, gazpacho, soupe, raclette] >> choix_dessert
choix_dessert >> [fondant, salade_fruits, creme]
[fondant, salade_fruits, creme] >> fin
```

### 🔧 Code Détaillé avec Branching Complexe
```python
from airflow.operators.python import BranchPythonOperator
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

def analyser_qualite_donnees(**context):
    """Analyse la qualité des données et choisit le bon traitement"""
    try:
        # Simulation d'analyse de qualité
        execution_date = context['execution_date']
        fichier_source = f"/data/raw/{execution_date.strftime('%Y-%m-%d')}.csv"
        
        # Métriques de qualité (simulées)
        metriques_qualite = {
            'completude': 0.85,  # 85% des données complètes
            'exactitude': 0.92,  # 92% des données exactes
            'consistance': 0.78  # 78% des données consistantes
        }
        
        print(f"📊 Métriques de qualité: {metriques_qualite}")
        
        # Seuils de qualité configurables
        seuil_eleve = float(Variable.get("seuil_qualite_eleve", 0.9))
        seuil_moyen = float(Variable.get("seuil_qualite_moyen", 0.7))
        
        # Décision basée sur la qualité
        if metriques_qualite['completude'] >= seuil_eleve and metriques_qualite['exactitude'] >= seuil_eleve:
            return "traitement_automatique"
        elif metriques_qualite['completude'] >= seuil_moyen:
            return "traitement_avec_nettoyage"
        else:
            return "traitement_manuel_revision"
            
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        return "traitement_erreur"

def choisir_methode_aggregation(**context):
    """Choisit la méthode d'agrégation selon le volume de données"""
    # Récupération des métriques de la tâche précédente
    metriques_qualite = context['ti'].xcom_pull(task_ids='analyser_qualite_donnees')
    
    volume_donnees = 500000  # Simulation
    
    if volume_donnees > 1000000:
        return "aggregation_distribuee"
    elif volume_donnees > 100000:
        return "aggregation_memoire"
    else:
        return "aggregation_simple"

# Tâches de décision
decision_qualite = BranchPythonOperator(
    task_id="analyser_qualite_donnees",
    python_callable=analyser_qualite_donnees
)

decision_aggregation = BranchPythonOperator(
    task_id="choisir_methode_aggregation",
    python_callable=choisir_methode_aggregation
)

# Tâches de traitement selon la qualité
traitement_auto = PythonOperator(
    task_id="traitement_automatique",
    python_callable=lambda: print("🤖 Traitement automatique - haute qualité")
)

traitement_nettoyage = PythonOperator(
    task_id="traitement_avec_nettoyage",
    python_callable=lambda: print("🧹 Traitement avec nettoyage - qualité moyenne")
)

traitement_manuel = PythonOperator(
    task_id="traitement_manuel_revision",
    python_callable=lambda: print("👨‍💻 Traitement manuel - qualité faible")
)

traitement_erreur = PythonOperator(
    task_id="traitement_erreur",
    python_callable=lambda: print("🚨 Traitement d'erreur - données problématiques")
)

# Tâches d'agrégation
agg_distribuee = PythonOperator(
    task_id="aggregation_distribuee",
    python_callable=lambda: print("🌐 Agrégation distribuée (Spark)")
)

agg_memoire = PythonOperator(
    task_id="aggregation_memoire",
    python_callable=lambda: print("💾 Agrégation en mémoire (Pandas)")
)

agg_simple = PythonOperator(
    task_id="aggregation_simple",
    python_callable=lambda: print("📊 Agrégation simple (SQL)")
)

# Tâche finale
finalisation = PythonOperator(
    task_id="finaliser_traitement",
    python_callable=lambda: print("✅ Traitement finalisé avec succès")
)

# DÉPENDANCES COMPLEXES
# Premier niveau: décision qualité
decision_qualite >> [traitement_auto, traitement_nettoyage, traitement_manuel, traitement_erreur]

# Deuxième niveau: décision agrégation (sauf pour erreur)
[traitement_auto, traitement_nettoyage, traitement_manuel] >> decision_aggregation

# Troisième niveau: agrégation
decision_aggregation >> [agg_distribuee, agg_memoire, agg_simple]

# Niveau final: toutes les branches convergent
[agg_distribuee, agg_memoire, agg_simple, traitement_erreur] >> finalisation
```

---

## 🎯 RÉSUMÉ GÉNÉRAL AIRFLOW

### **🏗️ Architecture Mentale**
```
DAG (Recette) 
    ↓
TASKS (Étapes)
    ↓  
DEPENDENCIES (Ordre)
    ↓
XCOM (Communication)
    ↓
SENSORS (Attentes) 
    ↓
BRANCHING (Décisions)
```

### **📋 Checklist de Création**
1. **DAG** : Définir le cadre (schedule, paramètres)
2. **Tasks** : Décomposer en étapes unitaires  
3. **Dependencies** : Ordonner les étapes
4. **XCom** : Communiquer des données si nécessaire
5. **Sensors** : Ajouter des attentes si besoin
6. **Branching** : Prévoir des décisions conditionnelles

### **🚨 Bonnes Pratiques**
- **Idempotence** : Les tâches peuvent être rejouées
- **Atomicité** : Une tâche = une responsabilité
- **Monitoring** : Logs clairs et états précis
- **Gestion d'erreur** : Retries et alertes configurées

**Airflow transforme vos recettes data en plats gastronomiques bien orchestrés!** 🍽️🎉