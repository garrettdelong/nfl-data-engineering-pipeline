import os
import re
from dataclasses import dataclass


required_env_vars = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PRIVATE_KEY_PATH",
]

optional_env_vars = [
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_STAGE",
]

identifier_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)*$")


@dataclass(frozen=True)
class SnowflakeWriteResult:
    success: bool
    chunk_count: int
    row_count: int
    output: list


def validate_identifier(identifier, label):
    if not identifier_pattern.match(identifier):
        raise ValueError(f"Invalid Snowflake {label}: {identifier}")


def sql_string(value):
    if value is None:
        return "NULL"

    return "'" + str(value).replace("'", "''") + "'"


def qualified_table_name(table_name, database=None, schema=None):
    validate_identifier(table_name, "table")

    if "." in table_name:
        return table_name

    if database and schema:
        validate_identifier(database, "database")
        validate_identifier(schema, "schema")
        return f"{database}.{schema}.{table_name}"

    if schema:
        validate_identifier(schema, "schema")
        return f"{schema}.{table_name}"

    return table_name


def get_snowflake_config_from_env(require_stage=False):
    required = list(required_env_vars)
    if require_stage:
        required.append("SNOWFLAKE_STAGE")

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required Snowflake environment variables: " + ", ".join(missing)
        )

    config = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "private_key_path": os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        "private_key_passphrase": os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", ""),
    }

    for env_var in optional_env_vars:
        if os.getenv(env_var):
            config[env_var.lower().replace("snowflake_", "")] = os.environ[env_var]

    return config


def connect_snowflake(config):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    passphrase = config.get("private_key_passphrase") or None
    if passphrase:
        passphrase = passphrase.encode()

    with open(config["private_key_path"], "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=passphrase,
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


def read_table_to_dataframe(
    connection,
    table_name,
    columns,
    database=None,
    schema=None,
):
    qualified_name = qualified_table_name(table_name, database, schema)

    for column in columns:
        validate_identifier(column, "column")

    query = f"""
SELECT
    {", ".join(columns)}
FROM {qualified_name}
""".strip()

    with connection.cursor() as cursor:
        cursor.execute(query)
        dataframe = cursor.fetch_pandas_all()

    dataframe.columns = [column.lower() for column in dataframe.columns]
    return dataframe


def write_dataframe_to_table(
    connection,
    dataframe,
    table_name,
    database=None,
    schema=None,
):
    from snowflake.connector.pandas_tools import write_pandas

    if dataframe.empty:
        return SnowflakeWriteResult(
            success=True,
            chunk_count=0,
            row_count=0,
            output=[],
        )

    qualified_name = qualified_table_name(table_name, database, schema)
    table_parts = qualified_name.split(".")

    if len(table_parts) == 3:
        database_name, schema_name, unqualified_table_name = table_parts
    elif len(table_parts) == 2:
        database_name = database
        schema_name, unqualified_table_name = table_parts
    else:
        database_name = database
        schema_name = schema
        unqualified_table_name = table_parts[0]

    success, chunk_count, row_count, output = write_pandas(
        conn=connection,
        df=dataframe,
        table_name=unqualified_table_name,
        database=database_name,
        schema=schema_name,
        quote_identifiers=False,
    )

    return SnowflakeWriteResult(
        success=success,
        chunk_count=chunk_count,
        row_count=row_count,
        output=output,
    )
