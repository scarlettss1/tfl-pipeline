"""
tfl_pipeline_dag.py

Airflow DAG definition for the TfL pipeline: runs fetch_status.py, then
transform_status.py, every 15 minutes.

This file is a copy, kept here for visibility and version control. The
actual file Airflow reads from is at ~/airflow-tfl/dags/tfl_pipeline_dag.py
on the local machine running Airflow. If this DAG is edited, both copies
need to be updated.

To actually run this DAG, Airflow needs to be set up separately (see
README for instructions), this file alone does not run anything.
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    dag_id="tfl_pipeline",
    description="Fetches TfL Tube status and transforms it into clean_line_status",
    start_date=datetime(2026, 9, 15),
    schedule=timedelta(minutes=15),
    catchup=False,
) as dag:

    fetch_task = BashOperator(
        task_id="fetch_status",
        bash_command="cd /opt/airflow/tfl-pipeline && python3 fetch_status.py",
    )

    transform_task = BashOperator(
        task_id="transform_status",
        bash_command="cd /opt/airflow/tfl-pipeline && python3 transform_status.py",
    )

    fetch_task >> transform_task