from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

from airflow_audit_callbacks import (
    audit_pipeline_failure,
    audit_pipeline_success,
    audit_task_failure,
    audit_task_start,
    audit_task_success,
)


DBT_IMAGE = "nfl-dbt:1.11.0"
DBT_PROJECT_DIR = "/opt/project/data/nfl_data"
PROFILES_DIR = "/opt/airflow/.dbt"
INGEST_MANIFEST_PATH = "/opt/project/logs/airflow_ingestion_manifest.json"
PIPELINE_RUN_ID = "{{ dag.dag_id }}__{{ run_id }}"
PIPELINE_ENVIRONMENT_NAME = "{{ var.value.get('PIPELINE_ENVIRONMENT_NAME', 'local') }}"

HOST_PROJECT = r"C:\coding projects\nfl-data-engineering-pipeline"
HOST_DBT = r"C:\Users\littl\.dbt"
HOST_SNOWFLAKE = r"C:\Users\littl\.snowflake"

SNOWFLAKE_COMMON_ENV = {
    "SNOWFLAKE_ACCOUNT": "{{ var.value.SNOWFLAKE_ACCOUNT }}",
    "SNOWFLAKE_USER": "{{ var.value.SNOWFLAKE_USER }}",
    "SNOWFLAKE_ROLE": "{{ var.value.SNOWFLAKE_ROLE }}",
    "SNOWFLAKE_WAREHOUSE": "{{ var.value.SNOWFLAKE_WAREHOUSE }}",
    "SNOWFLAKE_PRIVATE_KEY_PATH": "/opt/airflow/.snowflake/rsa_key.p8",
    "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "{{ var.value.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE }}",
}

SNOWFLAKE_AUDIT_ENV = {
    **SNOWFLAKE_COMMON_ENV,
    "SNOWFLAKE_AUDIT_DATABASE": "{{ var.value.get('SNOWFLAKE_AUDIT_DATABASE', 'NFL_ANALYTICS') }}",
    "SNOWFLAKE_AUDIT_SCHEMA": "{{ var.value.get('SNOWFLAKE_AUDIT_SCHEMA', 'audit') }}",
    "SNOWFLAKE_INGESTION_METADATA_DATABASE": "{{ var.value.get('SNOWFLAKE_INGESTION_METADATA_DATABASE', 'NFL_ANALYTICS') }}",
    "SNOWFLAKE_INGESTION_METADATA_SCHEMA": "{{ var.value.get('SNOWFLAKE_INGESTION_METADATA_SCHEMA', 'audit') }}",
}

SNOWFLAKE_RAW_LOAD_ENV = {
    **SNOWFLAKE_COMMON_ENV,
    "SNOWFLAKE_AUDIT_DATABASE": "{{ var.value.get('SNOWFLAKE_AUDIT_DATABASE', 'NFL_ANALYTICS') }}",
    "SNOWFLAKE_AUDIT_SCHEMA": "{{ var.value.get('SNOWFLAKE_AUDIT_SCHEMA', 'audit') }}",
    "SNOWFLAKE_RAW_DATABASE": "{{ var.value.SNOWFLAKE_RAW_DATABASE }}",
    "SNOWFLAKE_RAW_SCHEMA": "{{ var.value.SNOWFLAKE_RAW_SCHEMA }}",
    "SNOWFLAKE_RAW_STAGE": "{{ var.value.SNOWFLAKE_RAW_STAGE }}",
}

DBT_ENV = {
    **SNOWFLAKE_COMMON_ENV,
    "DBT_SNOWFLAKE_DATABASE": "{{ var.value.DBT_SNOWFLAKE_DATABASE }}",
    "DBT_SNOWFLAKE_SCHEMA": "{{ var.value.DBT_SNOWFLAKE_SCHEMA }}",
    "SNOWFLAKE_DATABASE": "{{ var.value.DBT_SNOWFLAKE_DATABASE }}",
    "SNOWFLAKE_SCHEMA": "{{ var.value.DBT_SNOWFLAKE_SCHEMA }}",
}

ML_ENV = {
    **SNOWFLAKE_COMMON_ENV,
    "SNOWFLAKE_ML_FEATURE_DATABASE": "{{ var.value.SNOWFLAKE_ML_FEATURE_DATABASE }}",
    "SNOWFLAKE_ML_FEATURE_SCHEMA": "{{ var.value.SNOWFLAKE_ML_FEATURE_SCHEMA }}",
    "SNOWFLAKE_ML_RESULTS_DATABASE": "{{ var.value.SNOWFLAKE_ML_RESULTS_DATABASE }}",
    "SNOWFLAKE_ML_RESULTS_SCHEMA": "{{ var.value.SNOWFLAKE_ML_RESULTS_SCHEMA }}",
}


with DAG(
    dag_id="nfl_pipeline_v1",
    start_date=datetime(2026, 2, 26),
    schedule="0 6 * * *",
    catchup=False,
    tags=["nfl", "pipeline"],
    on_success_callback=audit_pipeline_success,
    on_failure_callback=audit_pipeline_failure,
    default_args={
        "on_execute_callback": audit_task_start,
        "on_success_callback": audit_task_success,
        "on_failure_callback": audit_task_failure,
    },
) as dag:
    common_mounts = [
        Mount(
            source=HOST_PROJECT,
            target="/opt/project",
            type="bind",
            read_only=False,
        ),
        Mount(
            source=HOST_DBT,
            target="/opt/airflow/.dbt",
            type="bind",
            read_only=True,
        ),
        Mount(
            source=HOST_SNOWFLAKE,
            target="/opt/airflow/.snowflake",
            type="bind",
            read_only=True,
        ),
    ]

    start_pipeline_audit = BashOperator(
        task_id="start_pipeline_audit",
        bash_command=(
            "cd /opt/project && "
            "python -m data.pipeline_audit "
            "start-pipeline "
            f"--run-id \"{PIPELINE_RUN_ID}\" "
            "--pipeline-name nfl_pipeline_v1 "
            "--dag-id nfl_pipeline_v1 "
            f"--airflow-run-id \"{{{{ run_id }}}}\" "
            "--triggered-by airflow "
            f"--environment-name \"{PIPELINE_ENVIRONMENT_NAME}\""
        ),
        env=SNOWFLAKE_AUDIT_ENV,
        append_env=True,
    )

    ingest_all = BashOperator(
        task_id="ingest_all",
        bash_command=(
            "cd /opt/project && "
            "python -m data.ingest_s3 "
            "--table all "
            "--sync "
            f"--run-id \"{PIPELINE_RUN_ID}\" "
            "--write-audit-events "
            f"--manifest-output-path {INGEST_MANIFEST_PATH}"
        ),
        env=SNOWFLAKE_AUDIT_ENV,
        append_env=True,
    )

    load_snowflake_raw = BashOperator(
        task_id="load_snowflake_raw",
        bash_command=(
            "cd /opt/project && "
            "python -m data.load_snowflake_raw "
            f"--run-id \"{PIPELINE_RUN_ID}\" "
            f"--manifest-path {INGEST_MANIFEST_PATH}"
        ),
        env=SNOWFLAKE_RAW_LOAD_ENV,
        append_env=True,
    )

    dbt_deps = DockerOperator(
        task_id="dbt_deps",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=f"deps --project-dir {DBT_PROJECT_DIR} --profiles-dir {PROFILES_DIR}",
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment=DBT_ENV,
    )

    dbt_run = DockerOperator(
        task_id="dbt_run",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=(
            f"run --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {PROFILES_DIR} "
            "--target airflow"
        ),
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment=DBT_ENV,
    )

    dbt_test = DockerOperator(
        task_id="dbt_test",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=(
            f"test --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {PROFILES_DIR} "
            "--target airflow"
        ),
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment=DBT_ENV,
    )

    train_play_success_model = BashOperator(
        task_id="train_play_success_model",
        bash_command=(
            "cd /opt/project && "
            "python -m ml.play_success_prediction.train_model"
        ),
        env=ML_ENV,
        append_env=True,
    )

    validate_ml_outputs = BashOperator(
        task_id="validate_ml_outputs",
        bash_command=(
            "cd /opt/project && "
            "python -c \""
            "from data.snowflake_client import get_snowflake_config_from_env, connect_snowflake; "
            "config = get_snowflake_config_from_env(); "
            "connection = connect_snowflake(config); "
            "cursor = connection.cursor(); "
            "cursor.execute('SELECT COUNT(1) FROM nfl_analytics.ml_results.ml_play_success_model_metrics'); "
            "metrics_count = cursor.fetchone()[0]; "
            "cursor.execute('SELECT COUNT(1) FROM nfl_analytics.ml_results.ml_play_success_predictions'); "
            "predictions_count = cursor.fetchone()[0]; "
            "cursor.close(); "
            "connection.close(); "
            "print({'metrics_count': metrics_count, 'predictions_count': predictions_count}); "
            "raise SystemExit(0 if metrics_count > 0 and predictions_count > 0 else 1)"
            "\""
        ),
        env=ML_ENV,
        append_env=True,
    )

    end = EmptyOperator(task_id="end")

    (
        start_pipeline_audit
        >> ingest_all
        >> load_snowflake_raw
        >> dbt_deps
        >> dbt_run
        >> dbt_test
        >> train_play_success_model
        >> validate_ml_outputs
        >> end
    )
