import logging

try:
    from snowflake_client import (
        connect_snowflake,
        get_snowflake_config_from_env,
        qualified_table_name,
        sql_string,
        validate_identifier,
    )
except ModuleNotFoundError:
    from data.snowflake_client import (
        connect_snowflake,
        get_snowflake_config_from_env,
        qualified_table_name,
        sql_string,
        validate_identifier,
    )


logger = logging.getLogger(__name__)


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
    return copy_results


def load_uploaded_files(uploaded_files, config=None):
    if not uploaded_files:
        logger.info("no uploaded files to load into snowflake")
        return []

    snowflake_config = config or get_snowflake_config_from_env(require_stage=True)
    results = []

    try:
        connection = connect_snowflake(snowflake_config)
    except Exception:
        logger.exception("failed to connect to snowflake")
        raise

    try:
        with connection.cursor() as cursor:
            for file_info in uploaded_files:
                results.append(load_file(cursor, file_info, snowflake_config))
    except Exception:
        logger.exception("snowflake raw load failed")
        raise
    finally:
        connection.close()

    logger.info("snowflake raw load complete file_count=%s", len(uploaded_files))
    return results
