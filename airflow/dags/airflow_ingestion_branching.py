import logging

from data.cli_args import parse_truthy


logger = logging.getLogger(__name__)

FORCE_DOWNSTREAM_VARIABLE = "NFL_PIPELINE_FORCE_DOWNSTREAM"
CONTINUE_TASK_ID = "load_snowflake_raw"
SKIP_TASK_ID = "end"


def get_force_downstream(context, variable_getter=None):
    dag_run = context.get("dag_run")
    dag_run_conf = dag_run.conf or {} if dag_run else {}

    if "force_downstream" in dag_run_conf:
        return parse_truthy(dag_run_conf["force_downstream"])

    if variable_getter is None:
        from airflow.models import Variable

        variable_getter = Variable.get

    return parse_truthy(
        variable_getter(FORCE_DOWNSTREAM_VARIABLE, default_var="false")
    )


def choose_downstream_path(
    manifest_path,
    continue_task_id=CONTINUE_TASK_ID,
    skip_task_id=SKIP_TASK_ID,
    variable_getter=None,
    **context,
):
    if get_force_downstream(context, variable_getter=variable_getter):
        logger.info("forcing downstream pipeline path")
        return continue_task_id

    from data.load_snowflake_raw import (
        get_snowflake_eligible_files,
        read_manifest,
    )

    manifest_records = read_manifest(manifest_path)
    eligible_files = get_snowflake_eligible_files(manifest_records)

    logger.info(
        "evaluated ingestion manifest eligible_files=%s total_files=%s",
        len(eligible_files),
        len(manifest_records),
    )

    if eligible_files:
        return continue_task_id

    return skip_task_id
