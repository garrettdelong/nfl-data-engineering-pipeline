from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

DBT_IMAGE = "nfl-dbt:1.11.0"
PROJECT_DIR = "/opt/project/data/nfl_data"
PROFILES_DIR = "/opt/airflow/.dbt"
HOST_PROJECT = r"C:\coding projects\nfl-data-engineering-pipeline"
HOST_DBT = r"C:\Users\littl\.dbt"
HOST_SNOWFLAKE = r"C:\Users\littl\.snowflake"


with DAG(
    dag_id="nfl_pipeline_v1",
    start_date=datetime(2026, 2, 26),
    schedule="0 6 * * *",   # daily 6am
    catchup=False,
    tags=["nfl", "pipeline"],
) as dag:

    ingest_all = BashOperator(
        task_id="ingest_all",
        bash_command="python /opt/project/data/ingest_s3.py --table all",
    )

    common_mounts = [
        Mount(source=HOST_PROJECT, target="/opt/project", type="bind", read_only=False),
        Mount(source=HOST_DBT, target="/opt/airflow/.dbt", type="bind", read_only=True),
        Mount(source=HOST_SNOWFLAKE, target="/opt/airflow/.snowflake", type="bind", read_only=True),
    ]

    dbt_deps = DockerOperator(
        task_id="dbt_deps",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=f"deps --project-dir {PROJECT_DIR} --profiles-dir {PROFILES_DIR}",
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment={
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "{{ var.value.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE }}"
        },
    )

    dbt_run = DockerOperator(
        task_id="dbt_run",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=f"run --project-dir {PROJECT_DIR} --profiles-dir {PROFILES_DIR} --target airflow",
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment={
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "{{ var.value.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE }}"
        },
    )

    dbt_test = DockerOperator(
        task_id="dbt_test",
        image=DBT_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        command=f"test --project-dir {PROJECT_DIR} --profiles-dir {PROFILES_DIR} --target airflow",
        mounts=common_mounts,
        mount_tmp_dir=False,
        tty=True,
        do_xcom_push=False,
        environment={
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "{{ var.value.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE }}"
        },
    )

    ingest_all >> dbt_deps >> dbt_run >> dbt_test
