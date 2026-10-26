from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import numpy as np
import json
import os

# 📁 Chemins de fichiers
CSV_PATH = '/tmp/random_data.csv'
JSON_PATH = '/tmp/stats_summary.json'

# 🧬 1. Générer un CSV avec 100 lignes de données aléatoires
def generate_csv():
    df = pd.DataFrame({
        'value': np.random.randint(0, 1000, size=100)
    })
    df.to_csv(CSV_PATH, index=False)

# 📊 2. Lire le CSV et calculer les statistiques
def compute_stats():
    df = pd.read_csv(CSV_PATH)
    stats = {
        'mean': df['value'].mean(),
        'min': df['value'].min(),
        'max': df['value'].max()
    }
    # Stocker les stats dans XCom pour la tâche suivante
    return stats

# 📝 3. Écrire les résultats dans un fichier JSON
def write_json(ti):
    stats = ti.xcom_pull(task_ids='compute_stats')
    with open(JSON_PATH, 'w') as f:
        json.dump(stats, f)

# 📧 4. Simuler l’envoi d’un résumé par email
def send_summary(ti):
    stats = ti.xcom_pull(task_ids='compute_stats')
    print(f"Résumé des statistiques : Moyenne={stats['mean']:.2f}, Min={stats['min']}, Max={stats['max']}")

# 🧹 5. Nettoyer les fichiers temporaires
def cleanup_files():
    for path in [CSV_PATH, JSON_PATH]:
        if os.path.exists(path):
            os.remove(path)

# 🗓️ Définition du DAG
with DAG(
    dag_id='data_pipeline_challenge',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:

    t1 = PythonOperator(task_id='generate_csv', python_callable=generate_csv)
    t2 = PythonOperator(task_id='compute_stats', python_callable=compute_stats)
    t3 = PythonOperator(task_id='write_json', python_callable=write_json)
    t4 = PythonOperator(task_id='send_summary', python_callable=send_summary)
    t5 = PythonOperator(task_id='cleanup_files', python_callable=cleanup_files)

    t1 >> t2 >> t3 >> t4 >> t5