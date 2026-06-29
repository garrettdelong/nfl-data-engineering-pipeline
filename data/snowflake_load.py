import logging

from data.snowflake_client import (
    connect_snowflake,
    get_scoped_snowflake_config_from_env,
    qualified_table_name,
    sql_string,
    validate_identifier,
)
from data.pipeline_audit import update_file_load_result


logger = logging.getLogger(__name__)


def get_raw_snowflake_config_from_env():
    return get_scoped_snowflake_config_from_env("RAW", require_stage=True)


def source_year_sql(year):
    if year is None:
        return "NULL"

    return str(int(year))


def normalize_stage_name(stage_name):
    normalized = stage_name[1:] if stage_name.startswith("@") else stage_name
    validate_identifier(normalized, "stage")
    return normalized


def build_delete_sql(file_info, database=None, schema=None):
    raw_table = qualified_table_name(file_info["raw_table"], database, schema)
    return f"DELETE FROM {raw_table} WHERE source_file = {sql_string(file_info['s3_key'])}"


def build_copy_sql(file_info, stage_name, database=None, schema=None):
    raw_table = qualified_table_name(file_info["raw_table"], database, schema)
    normalized_stage = normalize_stage_name(stage_name)

    return f"""
COPY INTO {raw_table}
    (
        record,
        source_file,
        source_dataset,
        source_year,
        loaded_at
    )
FROM (
    SELECT
        $1,
        METADATA$FILENAME,
        {sql_string(file_info["dataset"])},
        {source_year_sql(file_info["year"])},
        CURRENT_TIMESTAMP()
    FROM @{normalized_stage}
)
FILES = ({sql_string(file_info["s3_key"])})
FILE_FORMAT = (TYPE = PARQUET)
FORCE = TRUE
ON_ERROR = ABORT_STATEMENT
""".strip()


def get_rows_loaded(copy_results, cursor_description):
    if not copy_results or not cursor_description:
        return None

    column_names = [
        getattr(column, "name", column[0]).lower()
        for column in cursor_description
    ]

    if "rows_loaded" not in column_names:
        return None

    rows_loaded_index = column_names.index("rows_loaded")
    return sum(
        int(row[rows_loaded_index] or 0)
        for row in copy_results
    )


def load_file(cursor, file_info, config):
    database = config.get("database")
    schema = config.get("schema")

    logger.info(
        "loading snowflake raw table dataset=%s year=%s s3_key=%s raw_table=%s",
        file_info["dataset"],
        file_info["year"] if file_info["year"] is not None else "single",
        file_info["s3_key"],
        file_info["raw_table"],
    )

    cursor.execute("BEGIN")
    try:
        cursor.execute(build_delete_sql(file_info, database, schema))
        cursor.execute(build_copy_sql(file_info, config["stage"], database, schema))
        cursor_description = cursor.description
        copy_results = cursor.fetchall()
        cursor.execute("COMMIT")
    except Exception:
        cursor.execute("ROLLBACK")
        raise

    logger.info(
        "loaded snowflake raw table dataset=%s year=%s s3_key=%s copy_results=%s",
        file_info["dataset"],
        file_info["year"] if file_info["year"] is not None else "single",
        file_info["s3_key"],
        copy_results,
    )
    return {
        "dataset": file_info["dataset"],
        "year": file_info["year"],
        "s3_key": file_info["s3_key"],
        "raw_table": file_info["raw_table"],
        "snowflake_load_status": "loaded",
        "rows_loaded": get_rows_loaded(copy_results, cursor_description),
        "error_message": None,
        "copy_results": copy_results,
    }


def update_load_audit_result(
    run_id,
    file_info,
    snowflake_load_status,
    rows_loaded=None,
    error_message=None,
    raise_on_failure=True,
):
    if not run_id:
        return

    try:
        update_file_load_result(
            run_id=run_id,
            s3_key=file_info["s3_key"],
            snowflake_load_status=snowflake_load_status,
            rows_loaded=rows_loaded,
            snowflake_table_name=file_info["raw_table"],
            error_message=error_message,
        )
    except Exception:
        logger.exception(
            "failed to update file load audit result run_id=%s s3_key=%s",
            run_id,
            file_info["s3_key"],
        )
        if raise_on_failure:
            raise


def load_uploaded_files(uploaded_files, config=None, run_id=None):
    if not uploaded_files:
        logger.info("no uploaded files to load into snowflake")
        return []

    snowflake_config = config or get_raw_snowflake_config_from_env()
    results = []

    try:
        connection = connect_snowflake(snowflake_config)
    except Exception:
        logger.exception("failed to connect to snowflake")
        raise

    try:
        with connection.cursor() as cursor:
            for file_info in uploaded_files:
                try:
                    load_result = load_file(cursor, file_info, snowflake_config)
                    results.append(load_result)

                    update_load_audit_result(
                        run_id=run_id,
                        file_info=file_info,
                        snowflake_load_status=load_result["snowflake_load_status"],
                        rows_loaded=load_result["rows_loaded"],
                        error_message=None,
                    )
                except Exception as exc:
                    update_load_audit_result(
                        run_id=run_id,
                        file_info=file_info,
                        snowflake_load_status="failed",
                        rows_loaded=None,
                        error_message=str(exc),
                        raise_on_failure=False,
                    )
                    raise
    except Exception:
        logger.exception("snowflake raw load failed")
        raise
    finally:
        connection.close()

    logger.info("snowflake raw load complete file_count=%s", len(uploaded_files))
    return results
