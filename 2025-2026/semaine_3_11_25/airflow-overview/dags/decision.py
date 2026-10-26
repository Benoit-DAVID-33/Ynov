from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.python import BranchPythonOperator
from airflow.operators.dummy import DummyOperator # Utilisé pour joindre les chemins
from datetime import datetime
from pendulum import timezone

# Définir le fuseau horaire de référence (important pour la logique horaire)
# Nous utiliserons 'Europe/Paris' ou un fuseau horaire pertinent pour les heures de bureau.
TIMEZONE = "Europe/Paris" 

# --- Tâches de Base ---

def log_start_branch(branch_name):
    """Log la branche qui est exécutée."""
    print(f"--- Démarrage de la branche : {branch_name} ---")

def log_end_branch(branch_name):
    """Log la fin de la branche qui est exécutée."""
    print(f"--- Fin de la branche : {branch_name} ---")

# --- Logique de Branchement ---

def choose_path(**kwargs):
    """
    Détermine si l'heure actuelle est dans les heures de bureau (9h - 18h).
    Retourne l'ID de la tâche à exécuter ensuite.
    """
    # Récupérer l'heure d'exécution du DAG (execution_date) et la localiser
    # ou simplement utiliser l'heure actuelle du Worker (moins fiable si les Workers
    # ne sont pas synchronisés, mais plus simple ici).
    # Utilisons l'heure actuelle localisée pour la démonstration.
    
    current_time = datetime.now(timezone(TIMEZONE))
    
    # Définition des heures de bureau (9h à 18h)
    start_hour = 9
    end_hour = 18
    
    current_hour = current_time.hour
    
    if start_hour <= current_hour < end_hour:
        # Exécute la branche des heures de bureau
        print(f"Heure actuelle ({current_time.strftime('%H:%M %Z')}) : Dans les heures de bureau. Branche 'office_hours' sélectionnée.")
        return 'office_hours_start'
    else:
        # Exécute la branche des heures creuses
        print(f"Heure actuelle ({current_time.strftime('%H:%M %Z')}) : En dehors des heures de bureau. Branche 'off_hours' sélectionnée.")
        return 'off_hours_start'

# --- Tâches de la Branche "Office Hours" (Priorité/Urgent) ---

def process_urgent_data():
    """Simule le traitement de données urgentes pendant les heures de bureau."""
    print("💼 Tâche 1 (Office Hours) : Traitement des données urgentes...")
    
def send_alert_notification():
    """Simule l'envoi d'une alerte immédiate."""
    print("🚨 Tâche 2 (Office Hours) : Notification immédiate envoyée à l'équipe de jour.")

# --- Tâches de la Branche "Off Hours" (Maintenance/Batch) ---

def run_db_cleanup():
    """Simule une tâche de maintenance, comme le nettoyage de base de données."""
    print("🌙 Tâche 1 (Off Hours) : Lancement du nettoyage de la base de données...")

def backup_large_dataset():
    """Simule une tâche de lot non critique comme la sauvegarde."""
    print("💾 Tâche 2 (Off Hours) : Sauvegarde d'un grand ensemble de données vers le stockage froid.")

# 🗓️ Définition du DAG
with DAG(
    dag_id='conditional_decision_pipeline',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['challenge', 'branching', 'condition']
) as dag:
    
    # 1. Point de départ
    start_task = PythonOperator(
        task_id='pipeline_start',
        python_callable=log_start_branch,
        op_kwargs={'branch_name': 'Global Pipeline Start'}
    )
    
    # 2. Opérateur de Branchement
    branch_decision = BranchPythonOperator(
        task_id='time_based_decision',
        python_callable=choose_path,
        # Si une branche est sautée, on veut s'assurer qu'elle arrive quand même au point final (join).
        # Le BranchPythonOperator gère cela en faisant pointer les tâches non choisies vers le 'join'.
    )
    
    # 3. Définition des Tâches de Branchement (avec des points d'entrée nommés)
    
    # --- Branche Office Hours ---
    office_start = DummyOperator(task_id='office_hours_start')
    
    t_office_1 = PythonOperator(
        task_id='process_urgent_data',
        python_callable=process_urgent_data
    )
    
    t_office_2 = PythonOperator(
        task_id='send_alert_notification',
        python_callable=send_alert_notification
    )
    
    # --- Branche Off Hours ---
    off_start = DummyOperator(task_id='off_hours_start')
    
    t_off_1 = PythonOperator(
        task_id='run_db_cleanup',
        python_callable=run_db_cleanup
    )
    
    t_off_2 = PythonOperator(
        task_id='backup_large_dataset',
        python_callable=backup_large_dataset
    )
    
    # 4. Tâche de Jonction
    # Le 'trigger_rule' est crucial ici pour s'assurer que le DAG continue 
    # même si une branche est sautée (skipped).
    join_branches = DummyOperator(
        task_id='join_branches',
        trigger_rule='none_failed_min_one_success', # S'exécute si au moins une branche a réussi et aucune n'a échoué.
        doc_md="Point de jonction après la décision conditionnelle."
    )

    # 5. Point de fin
    end_task = PythonOperator(
        task_id='pipeline_end',
        python_callable=log_end_branch,
        op_kwargs={'branch_name': 'Global Pipeline End'}
    )
    
    # Définition des Dépendances
    
    # 1. Démarrage -> Décision
    start_task >> branch_decision
    
    # 2. Décision -> Branches
    # Le BranchPythonOperator envoie vers l'une des tâches de démarrage de branche
    branch_decision >> [office_start, off_start]
    
    # 3. Déroulement des Branches
    # Office Hours
    office_start >> t_office_1 >> t_office_2 >> join_branches
    
    # Off Hours
    off_start >> t_off_1 >> t_off_2 >> join_branches
    
    # 4. Jonction -> Fin
    join_branches >> end_task