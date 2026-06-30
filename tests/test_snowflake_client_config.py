import os
import unittest
from unittest.mock import patch

from data.snowflake_client import get_scoped_snowflake_config_from_env


BASE_ENV = {
    "SNOWFLAKE_ACCOUNT": "test_account",
    "SNOWFLAKE_USER": "test_user",
    "SNOWFLAKE_PRIVATE_KEY_PATH": "test_key.p8",
}


class SnowflakeClientConfigTests(unittest.TestCase):
    def test_scoped_config_uses_scoped_database_schema_and_stage(self):
        env = {
            **BASE_ENV,
            "SNOWFLAKE_RAW_DATABASE": "NFL_RAW",
            "SNOWFLAKE_RAW_SCHEMA": "PLAY_BY_PLAY",
            "SNOWFLAKE_RAW_STAGE": "NFL_RAW.PLAY_BY_PLAY.stg_nfl_raw",
            "SNOWFLAKE_DATABASE": "NFL_ANALYTICS",
            "SNOWFLAKE_SCHEMA": "dbt_gdelong",
        }

        with patch.dict(os.environ, env, clear=True):
            config = get_scoped_snowflake_config_from_env(
                "RAW",
                require_stage=True,
            )

        self.assertEqual(config["database"], "NFL_RAW")
        self.assertEqual(config["schema"], "PLAY_BY_PLAY")
        self.assertEqual(config["stage"], "NFL_RAW.PLAY_BY_PLAY.stg_nfl_raw")

    def test_scoped_config_requires_scoped_database_and_schema(self):
        env = {
            **BASE_ENV,
            "SNOWFLAKE_DATABASE": "NFL_ANALYTICS",
            "SNOWFLAKE_SCHEMA": "audit",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as context:
                get_scoped_snowflake_config_from_env("AUDIT")

        self.assertIn("SNOWFLAKE_AUDIT_DATABASE", str(context.exception))
        self.assertIn("SNOWFLAKE_AUDIT_SCHEMA", str(context.exception))

    def test_scoped_config_ignores_generic_database_schema(self):
        env = {
            **BASE_ENV,
            "SNOWFLAKE_DATABASE": "NFL_RAW",
            "SNOWFLAKE_SCHEMA": "PLAY_BY_PLAY",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                get_scoped_snowflake_config_from_env("INGESTION_METADATA")

    def test_scoped_config_uses_scoped_database_schema(self):
        env = {
            **BASE_ENV,
            "SNOWFLAKE_DATABASE": "NFL_RAW",
            "SNOWFLAKE_SCHEMA": "PLAY_BY_PLAY",
            "SNOWFLAKE_INGESTION_METADATA_DATABASE": "NFL_ANALYTICS",
            "SNOWFLAKE_INGESTION_METADATA_SCHEMA": "audit",
        }

        with patch.dict(os.environ, env, clear=True):
            config = get_scoped_snowflake_config_from_env(
                "INGESTION_METADATA",
            )

        self.assertEqual(config["database"], "NFL_ANALYTICS")
        self.assertEqual(config["schema"], "audit")


if __name__ == "__main__":
    unittest.main()
