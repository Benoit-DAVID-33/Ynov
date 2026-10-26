from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import numpy as np
import json
import os
from time import sleep

# ⚠️ Chemins de fichiers pour l'artefact final (JSON)
# Le fichier final est écrit localement, mais la tâche de lecture (compute_stats)
# n'a plus besoin d'accéder à un fichier intermédiaire, ce qui résout le problème principal.
JSON_PATH = '/tmp/stats_summary.json' 
# Le CSV n'est plus créé physiquement pour garantir la robustesse du transfert.

# 🧬 1. Générer les données aléatoires et les transférer via XCom
# Au lieu d'écrire un CSV sur un disque local non partagé, nous retournons un DataFrame 
# sous forme de dictionnaire qui sera stocké dans XCom.
def generate_data_xcom():
    # Génération d'un DataFrame avec 100 lignes de données aléatoires
    df = pd.DataFrame({
        'value': np.random.randint(0, 1000, size=100)
    })
    # Pour s'assurer que Pandas utilise un format XCom-compatible, nous retournons un dictionnaire.
    # Airflow sérialisera ceci automatiquement.
    return df.to_dict(orient='list') 

# 📊 2. Lire les données depuis XCom et calculer les statistiques
def compute_stats_from_xcom(ti):
    # Récupération des données générées par la tâche 'generate_data_xcom'
    data_dict = ti.xcom_pull(task_ids='generate_data_xcom')
    
    # Reconstruction du DataFrame à partir des données XCom
    df = pd.DataFrame(data_dict)

    # Calcul des statistiques
    # CORRECTION IMPORTANTE : Nous convertissons explicitement les types NumPy 
    # (int64, float64) en types Python natifs (int, float) pour la sérialisation JSON.
    stats = {
        'mean': df['value'].mean().item(), # .item() convertit les types NumPy en natif
        'min': df['value'].min().item(),
        'max': df['value'].max().item(),
        'total_rows': len(df)
    }
    # Les statistiques sont automatiquement stockées dans XCom pour les tâches suivantes
    return stats 

# 📝 3. Écrire les résultats des statistiques dans un fichier JSON local
def write_json_xcom(ti):
    # Récupération des statistiques calculées par la tâche 'compute_stats_from_xcom'
    stats = ti.xcom_pull(task_ids='compute_stats_from_xcom')
    
    # Écriture du fichier JSON (artefact final). Cela fonctionne maintenant car les types sont natifs.
    with open(JSON_PATH, 'w') as f:
        json.dump(stats, f, indent=4)
    print(f"✅ Fichier JSON écrit à : {JSON_PATH}")

# 📧 4. Simuler l’envoi d’un résumé par email
def send_summary_xcom(ti):
    # Récupération des statistiques pour le résumé
    stats = ti.xcom_pull(task_ids='compute_stats_from_xcom')
    
    # Les valeurs sont désormais des types float/int Python natifs
    summary = (
        f"📧 Résumé des statistiques : "
        f"Moyenne={stats['mean']:.2f}, "
        f"Min={stats['min']}, "
        f"Max={stats['max']}, "
        f"Échantillon={stats['total_rows']} lignes."
    )
    print(summary)
    # Simulation d'envoi par email
    sleep(1) # Simulation d'une opération réseau

# 🧹 5. Nettoyer les fichiers temporaires
def cleanup_json():
    # Nettoyage seulement du fichier JSON, car le CSV n'a jamais été créé physiquement.
    if os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
        print(f"🗑️ Fichier nettoyé : {JSON_PATH}")
    else:
        print(f"🗑️ Le fichier {JSON_PATH} n'existe pas, pas de nettoyage nécessaire.")

# 🗓️ Définition du DAG
with DAG(
    dag_id='data_pipeline_xcom_safe',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['challenge', 'xcom-safe']
) as dag:

    # 1. Génération des données (et transmission par XCom)
    t1_generate = PythonOperator(
        task_id='generate_data_xcom', 
        python_callable=generate_data_xcom,
        doc_md="Génère 100 données aléatoires et les transmet via XCom."
    )
    
    # 2. Calcul des statistiques (récupération des données depuis XCom)
    t2_compute = PythonOperator(
        task_id='compute_stats_from_xcom', 
        python_callable=compute_stats_from_xcom,
        doc_md="Lit les données depuis XCom et calcule la moyenne, min, max."
    )
    
    # 3. Écriture du JSON (récupération des stats depuis XCom)
    t3_write_json = PythonOperator(
        task_id='write_json', 
        python_callable=write_json_xcom,
        doc_md="Écrit les statistiques finales dans un fichier JSON."
    )
    
    # 4. Envoi du résumé (récupération des stats depuis XCom)
    t4_send_summary = PythonOperator(
        task_id='send_summary', 
        python_callable=send_summary_xcom,
        doc_md="Simule l'envoi d'un email de résumé."
    )
    
    # 5. Nettoyage des fichiers temporaires (JSON uniquement)
    t5_cleanup = PythonOperator(
        task_id='cleanup_files', 
        python_callable=cleanup_json,
        trigger_rule='all_done', # Assure que le nettoyage s'exécute même si t3 ou t4 échoue
        doc_md="Nettoie le fichier JSON final."
    )

    # Définition des dépendances
    # t1 -> t2
    # t2 -> t3 (écriture)
    # t2 -> t4 (email)
    # t3 et t4 doivent terminer avant t5 (nettoyage)
    
    t1_generate >> t2_compute
    t2_compute >> [t3_write_json, t4_send_summary]
    [t3_write_json, t4_send_summary] >> t5_cleanup