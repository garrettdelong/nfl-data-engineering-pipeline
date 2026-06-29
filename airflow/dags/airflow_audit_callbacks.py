import logging
import os
import subprocess

from airflow.models import Variable


logger = logging.getLogger(__name__)

AUDIT_SUBPROCESS_TIMEOUT_SECONDS = 120


def pipeline_run_id(context):
    return f"{context['dag'].dag_id}__{context['run_id']}"


def audit_log_reference(context):
    task_instance = context["task_instance"]
    return (
        f"dag_id={context['dag'].dag_id} "
        f"run_id={context['run_id']} "
        f"task_id={task_instance.task_id} "
        f"try_number={task_instance.try_number}"
    )


def build_audit_subprocess_env():
    env = os.environ.copy()
    variable_names = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_ROLE",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE",
        "SNOWFLAKE_AUDIT_DATABASE",
        "SNOWFLAKE_AUDIT_SCHEMA",
    ]

    for variable_name in variable_names:
        value = Variable.get(variable_name, default_var=None)
        if value:
            env[variable_name] = value

    env.setdefault("SNOWFLAKE_AUDIT_DATABASE", "NFL_ANALYTICS")
    env.setdefault("SNOWFLAKE_AUDIT_SCHEMA", "audit")
    env["SNOWFLAKE_PRIVATE_KEY_PATH"] = "/opt/airflow/.snowflake/rsa_key.p8"

    return env


def run_audit_command(command):
    try:
        subprocess.run(
            command,
            cwd="/opt/project",
            env=build_audit_subprocess_env(),
            check=True,
            timeout=AUDIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("airflow audit callback failed command=%s", command)


def audit_task_start(context):
    task_instance = context["task_instance"]
    run_audit_command(
        [
            "python",
            "-m",
            "data.pipeline_audit",
            "start-task",
            "--run-id",
            pipeline_run_id(context),
            "--task-name",
            task_instance.task_id,
            "--attempt-number",
            str(task_instance.try_number),
            "--log-reference",
            audit_log_reference(context),
        ]
    )


def audit_task_success(context):
    task_instance = context["task_instance"]
    run_audit_command(
        [
            "python",
            "-m",
            "data.pipeline_audit",
            "finish-task",
            "--run-id",
            pipeline_run_id(context),
            "--task-name",
            task_instance.task_id,
            "--attempt-number",
            str(task_instance.try_number),
            "--task-status",
            "succeeded",
        ]
    )


def audit_task_failure(context):
    task_instance = context["task_instance"]
    exception = context.get("exception")
    command = [
        "python",
        "-m",
        "data.pipeline_audit",
        "finish-task",
        "--run-id",
        pipeline_run_id(context),
        "--task-name",
        task_instance.task_id,
        "--attempt-number",
        str(task_instance.try_number),
        "--task-status",
        "failed",
    ]

    if exception:
        command.extend(["--error-message", str(exception)[:1000]])

    run_audit_command(command)


def audit_pipeline_success(context):
    run_audit_command(
        [
            "python",
            "-m",
            "data.pipeline_audit",
            "finish-pipeline",
            "--run-id",
            pipeline_run_id(context),
            "--run-status",
            "succeeded",
        ]
    )


def audit_pipeline_failure(context):
    exception = context.get("exception")
    command = [
        "python",
        "-m",
        "data.pipeline_audit",
        "finish-pipeline",
        "--run-id",
        pipeline_run_id(context),
        "--run-status",
        "failed",
    ]

    if exception:
        command.extend(["--error-message", str(exception)[:1000]])

    run_audit_command(command)
