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

    def test_scoped_config_falls_back_to_generic_database_and_schema(self):
        env = {
            **BASE_ENV,
            "SNOWFLAKE_DATABASE": "NFL_ANALYTICS",
            "SNOWFLAKE_SCHEMA": "audit",
        }

        with patch.dict(os.environ, env, clear=True):
            config = get_scoped_snowflake_config_from_env("AUDIT")

        self.assertEqual(config["database"], "NFL_ANALYTICS")
        self.assertEqual(config["schema"], "audit")


if __name__ == "__main__":
    unittest.main()
