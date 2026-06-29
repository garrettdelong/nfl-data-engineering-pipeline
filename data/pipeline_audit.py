import argparse
import logging
from datetime import datetime, timezone

from data.cli_args import (
    add_environment_name_argument,
    add_log_level_argument,
    add_run_id_argument,
)
from data.logging_config import configure_logging
from data.snowflake_client import (
    connect_snowflake,
    get_scoped_snowflake_config_from_env,
    qualified_table_name,
)


logger = logging.getLogger(__name__)

PIPELINE_RUN_TABLE = "pipeline_run"
PIPELINE_TASK_RUN_TABLE = "pipeline_task_run"
PIPELINE_FILE_EVENT_TABLE = "pipeline_file_event"


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_timestamp(value):
    if value is None or isinstance(value, datetime):
        return value

    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def seconds_between(started_at, finished_at):
    if not started_at or not finished_at:
        return None

    return (finished_at - started_at).total_seconds()


def get_audit_snowflake_config_from_env():
    return get_scoped_snowflake_config_from_env("AUDIT")


def audit_table_name(table_name, config):
    return qualified_table_name(
        table_name,
        database=config.get("database"),
        schema=config.get("schema"),
    )


def execute_audit_write(sql, params=None, config=None):
    snowflake_config = config or get_audit_snowflake_config_from_env()
    connection = connect_snowflake(snowflake_config)

    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            cursor.execute(sql, params)
            cursor.execute("COMMIT")
    except Exception:
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        logger.exception("snowflake audit write failed")
        raise
    finally:
        connection.close()


def execute_many_audit_writes(statements, config=None):
    if not statements:
        return

    snowflake_config = config or get_audit_snowflake_config_from_env()
    connection = connect_snowflake(snowflake_config)

    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            for sql, params in statements:
                cursor.execute(sql, params)
            cursor.execute("COMMIT")
    except Exception:
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        logger.exception("snowflake audit write failed")
        raise
    finally:
        connection.close()


def start_pipeline_run(
    run_id,
    pipeline_name,
    dag_id=None,
    airflow_run_id=None,
    triggered_by=None,
    environment_name=None,
    git_commit_sha=None,
    started_at=None,
    config=None,
):
    started_at = parse_timestamp(started_at) or utc_now()
    snowflake_config = config or get_audit_snowflake_config_from_env()
    table_name = audit_table_name(PIPELINE_RUN_TABLE, snowflake_config)

    sql = f"""
MERGE INTO {table_name} AS target
USING (
    SELECT
        %s AS run_id,
        %s AS pipeline_name,
        %s AS dag_id,
        %s AS airflow_run_id,
        %s AS started_at,
        %s AS triggered_by,
        %s AS environment_name,
        %s AS git_commit_sha
) AS source
ON target.run_id = source.run_id
WHEN MATCHED THEN UPDATE SET
    run_status = 'running',
    started_at = source.started_at,
    finished_at = NULL,
    duration_seconds = NULL,
    error_message = NULL,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    run_id,
    pipeline_name,
    dag_id,
    airflow_run_id,
    run_status,
    started_at,
    triggered_by,
    environment_name,
    git_commit_sha,
    created_at,
    updated_at
)
VALUES (
    source.run_id,
    source.pipeline_name,
    source.dag_id,
    source.airflow_run_id,
    'running',
    source.started_at,
    source.triggered_by,
    source.environment_name,
    source.git_commit_sha,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
)
""".strip()

    execute_audit_write(
        sql,
        (
            run_id,
            pipeline_name,
            dag_id,
            airflow_run_id,
            started_at,
            triggered_by,
            environment_name,
            git_commit_sha,
        ),
        config=snowflake_config,
    )
    logger.info("started pipeline audit run_id=%s", run_id)


def finish_pipeline_run(
    run_id,
    run_status,
    error_message=None,
    finished_at=None,
    config=None,
):
    finished_at = parse_timestamp(finished_at) or utc_now()
    snowflake_config = config or get_audit_snowflake_config_from_env()
    table_name = audit_table_name(PIPELINE_RUN_TABLE, snowflake_config)

    sql = f"""
UPDATE {table_name}
SET
    run_status = %s,
    finished_at = %s,
    duration_seconds = DATEDIFF('second', started_at, %s),
    error_message = %s,
    updated_at = CURRENT_TIMESTAMP()
WHERE run_id = %s
""".strip()

    execute_audit_write(
        sql,
        (
            run_status,
            finished_at,
            finished_at,
            error_message,
            run_id,
        ),
        config=snowflake_config,
    )
    logger.info("finished pipeline audit run_id=%s status=%s", run_id, run_status)


def start_task_run(
    run_id,
    task_name,
    attempt_number,
    started_at=None,
    log_reference=None,
    config=None,
):
    started_at = parse_timestamp(started_at) or utc_now()
    snowflake_config = config or get_audit_snowflake_config_from_env()
    table_name = audit_table_name(PIPELINE_TASK_RUN_TABLE, snowflake_config)

    sql = f"""
MERGE INTO {table_name} AS target
USING (
    SELECT
        %s AS run_id,
        %s AS task_name,
        %s AS attempt_number,
        %s AS started_at,
        %s AS log_reference
) AS source
ON target.run_id = source.run_id
    AND target.task_name = source.task_name
    AND target.attempt_number = source.attempt_number
WHEN MATCHED THEN UPDATE SET
    task_status = 'running',
    started_at = source.started_at,
    finished_at = NULL,
    duration_seconds = NULL,
    error_message = NULL,
    log_reference = source.log_reference,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    run_id,
    task_name,
    task_status,
    attempt_number,
    started_at,
    log_reference,
    created_at,
    updated_at
)
VALUES (
    source.run_id,
    source.task_name,
    'running',
    source.attempt_number,
    source.started_at,
    source.log_reference,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
)
""".strip()

    execute_audit_write(
        sql,
        (
            run_id,
            task_name,
            attempt_number,
            started_at,
            log_reference,
        ),
        config=snowflake_config,
    )


def finish_task_run(
    run_id,
    task_name,
    attempt_number,
    task_status,
    error_message=None,
    finished_at=None,
    input_record_count=None,
    output_record_count=None,
    config=None,
):
    finished_at = parse_timestamp(finished_at) or utc_now()
    snowflake_config = config or get_audit_snowflake_config_from_env()
    table_name = audit_table_name(PIPELINE_TASK_RUN_TABLE, snowflake_config)

    sql = f"""
UPDATE {table_name}
SET
    task_status = %s,
    finished_at = %s,
    duration_seconds = DATEDIFF('second', started_at, %s),
    input_record_count = COALESCE(%s, input_record_count),
    output_record_count = COALESCE(%s, output_record_count),
    error_message = %s,
    updated_at = CURRENT_TIMESTAMP()
WHERE run_id = %s
    AND task_name = %s
    AND attempt_number = %s
""".strip()

    execute_audit_write(
        sql,
        (
            task_status,
            finished_at,
            finished_at,
            input_record_count,
            output_record_count,
            error_message,
            run_id,
            task_name,
            attempt_number,
        ),
        config=snowflake_config,
    )


def build_file_event_statement(record, run_id, config):
    table_name = audit_table_name(PIPELINE_FILE_EVENT_TABLE, config)
    started_at = parse_timestamp(record.get("started_at"))
    finished_at = parse_timestamp(record.get("finished_at"))

    sql = f"""
MERGE INTO {table_name} AS target
USING (
    SELECT
        %s AS run_id,
        %s AS dataset_name,
        %s AS source_year,
        %s AS source_url,
        %s AS s3_bucket,
        %s AS s3_key,
        %s AS upload_status,
        %s AS snowflake_load_status,
        %s AS snowflake_table_name,
        %s AS started_at,
        %s AS finished_at,
        %s AS duration_seconds,
        %s AS error_message
) AS source
ON target.run_id = source.run_id
    AND target.s3_key = source.s3_key
WHEN MATCHED THEN UPDATE SET
    dataset_name = source.dataset_name,
    source_year = source.source_year,
    source_url = source.source_url,
    s3_bucket = source.s3_bucket,
    upload_status = source.upload_status,
    snowflake_load_status = source.snowflake_load_status,
    snowflake_table_name = source.snowflake_table_name,
    started_at = source.started_at,
    finished_at = source.finished_at,
    duration_seconds = source.duration_seconds,
    error_message = source.error_message
WHEN NOT MATCHED THEN INSERT (
    run_id,
    dataset_name,
    source_year,
    source_url,
    s3_bucket,
    s3_key,
    upload_status,
    snowflake_load_status,
    snowflake_table_name,
    started_at,
    finished_at,
    duration_seconds,
    error_message,
    created_at
)
VALUES (
    source.run_id,
    source.dataset_name,
    source.source_year,
    source.source_url,
    source.s3_bucket,
    source.s3_key,
    source.upload_status,
    source.snowflake_load_status,
    source.snowflake_table_name,
    source.started_at,
    source.finished_at,
    source.duration_seconds,
    source.error_message,
    CURRENT_TIMESTAMP()
)
""".strip()

    params = (
        run_id,
        record.get("dataset"),
        record.get("source_year"),
        record.get("source_url"),
        record.get("s3_bucket"),
        record.get("s3_key"),
        record.get("upload_status"),
        record.get("snowflake_load_status", "not_attempted"),
        record.get("snowflake_table_name"),
        started_at,
        finished_at,
        record.get("duration_seconds"),
        record.get("error_message"),
    )

    return sql, params


def record_file_events(run_id, manifest_records, config=None):
    if not manifest_records:
        logger.info("no file audit events to record run_id=%s", run_id)
        return

    snowflake_config = config or get_audit_snowflake_config_from_env()
    statements = [
        build_file_event_statement(record, run_id, snowflake_config)
        for record in manifest_records
    ]

    execute_many_audit_writes(statements, config=snowflake_config)
    logger.info(
        "recorded file audit events run_id=%s file_count=%s",
        run_id,
        len(manifest_records),
    )


def update_file_load_result(
    run_id,
    s3_key,
    snowflake_load_status,
    rows_loaded=None,
    error_message=None,
    snowflake_table_name=None,
    finished_at=None,
    config=None,
):
    finished_at = parse_timestamp(finished_at) or utc_now()
    snowflake_config = config or get_audit_snowflake_config_from_env()
    table_name = audit_table_name(PIPELINE_FILE_EVENT_TABLE, snowflake_config)

    sql = f"""
UPDATE {table_name}
SET
    snowflake_load_status = %s,
    snowflake_table_name = COALESCE(%s, snowflake_table_name),
    rows_loaded = COALESCE(%s, rows_loaded),
    finished_at = %s,
    duration_seconds = DATEDIFF('second', started_at, %s),
    error_message = %s
WHERE run_id = %s
    AND s3_key = %s
""".strip()

    execute_audit_write(
        sql,
        (
            snowflake_load_status,
            snowflake_table_name,
            rows_loaded,
            finished_at,
            finished_at,
            error_message,
            run_id,
            s3_key,
        ),
        config=snowflake_config,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Write pipeline audit metadata")
    add_log_level_argument(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_pipeline = subparsers.add_parser("start-pipeline")
    add_run_id_argument(start_pipeline, required=True)
    start_pipeline.add_argument("--pipeline-name", required=True)
    start_pipeline.add_argument("--dag-id")
    start_pipeline.add_argument("--airflow-run-id")
    start_pipeline.add_argument("--triggered-by")
    add_environment_name_argument(start_pipeline)
    start_pipeline.add_argument("--git-commit-sha")

    finish_pipeline = subparsers.add_parser("finish-pipeline")
    add_run_id_argument(finish_pipeline, required=True)
    finish_pipeline.add_argument("--run-status", required=True)
    finish_pipeline.add_argument("--error-message")

    return parser.parse_args(argv)


def main(args=None):
    if args is None:
        args = parse_args()

    if args.command == "start-pipeline":
        start_pipeline_run(
            run_id=args.run_id,
            pipeline_name=args.pipeline_name,
            dag_id=args.dag_id,
            airflow_run_id=args.airflow_run_id,
            triggered_by=args.triggered_by,
            environment_name=args.environment_name,
            git_commit_sha=args.git_commit_sha,
        )
        return

    if args.command == "finish-pipeline":
        finish_pipeline_run(
            run_id=args.run_id,
            run_status=args.run_status,
            error_message=args.error_message,
        )
        return

    raise ValueError(f"Unsupported audit command: {args.command}")


if __name__ == "__main__":
    parsed_args = parse_args()
    configure_logging(parsed_args.log_level)
    main(parsed_args)
