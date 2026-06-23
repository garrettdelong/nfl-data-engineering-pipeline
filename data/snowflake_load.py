import logging
import os
import re


logger = logging.getLogger(__name__)

required_env_vars = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PRIVATE_KEY_PATH",
    "SNOWFLAKE_STAGE",
]

optional_env_vars = [
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]

identifier_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)*$")


def validate_identifier(identifier, label):
    if not identifier_pattern.match(identifier):
        raise ValueError(f"Invalid Snowflake {label}: {identifier}")


def sql_string(value):
    if value is None:
        return "NULL"

    return "'" + str(value).replace("'", "''") + "'"


def source_year_sql(year):
    if year is None:
        return "NULL"

    return str(int(year))


def normalize_stage_name(stage_name):
    normalized = stage_name[1:] if stage_name.startswith("@") else stage_name
    validate_identifier(normalized, "stage")
    return normalized


def qualified_table_name(raw_table, database=None, schema=None):
    validate_identifier(raw_table, "raw table")

    if database and schema:
        validate_identifier(database, "database")
        validate_identifier(schema, "schema")
        return f"{database}.{schema}.{raw_table}"

    if schema:
        validate_identifier(schema, "schema")
        return f"{schema}.{raw_table}"

    return raw_table


def get_snowflake_config_from_env():
    missing = [name for name in required_env_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required Snowflake environment variables: " + ", ".join(missing)
        )

    config = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "private_key_path": os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        "private_key_passphrase": os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", ""),
        "stage": os.environ["SNOWFLAKE_STAGE"],
    }

    for env_var in optional_env_vars:
        if os.getenv(env_var):
            config[env_var.lower().replace("snowflake_", "")] = os.environ[env_var]

    return config

def connect_snowflake(config):
    import snowflake.connector
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    passphrase = config.get("private_key_passphrase") or None
    if passphrase:
        passphrase = passphrase.encode()

    with open(config["private_key_path"], "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=passphrase,
            backend=default_backend(),
        )

    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    connection_args = {
        "account": config["account"],
        "user": config["user"],
        "private_key": private_key_der,
    }

    for key in ["role", "warehouse", "database", "schema"]:
        if config.get(key):
            connection_args[key] = config[key]

    return snowflake.connector.connect(**connection_args)


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

    snowflake_config = config or get_snowflake_config_from_env()
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
