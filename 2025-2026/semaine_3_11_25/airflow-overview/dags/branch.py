from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from datetime import datetime

def choose_branch(**kwargs):
    """Décide quelle branche exécuter"""
    execution_date = kwargs['execution_date']
    day_of_week = execution_date.weekday()

    if day_of_week < 5:
        return 'weekday_task'
    else:
        return 'weekend_task'

def weekday_action():
    print("C'est un jour de semaine. Traitement spécifique lancé.")

def weekend_action():
    print("C'est le week-end. Routine allégée exécutée.")

with DAG(
    dag_id='branching_with_actions',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:

    branching = BranchPythonOperator(
        task_id='branching',
        python_callable=choose_branch
    )

    weekday_task = PythonOperator(
        task_id='weekday_task',
        python_callable=weekday_action
    )

    weekend_task = PythonOperator(
        task_id='weekend_task',
        python_callable=weekend_action
    )

    branching >> [weekday_task, weekend_task]