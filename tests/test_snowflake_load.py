import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

import snowflake_load


class SnowflakeLoadSqlTests(unittest.TestCase):
    def setUp(self):
        self.file_info = {
            "dataset": "stats_player",
            "year": 2024,
            "s3_key": "stats_players/stats_player_week_2024.parquet",
            "raw_table": "RAW_STATS_PLAYER_WEEKLY",
        }

    def test_delete_sql_targets_source_file(self):
        sql = snowflake_load.build_delete_sql(
            self.file_info,
            database="NFL_RAW",
            schema="PLAY_BY_PLAY",
        )

        self.assertEqual(
            sql,
            "DELETE FROM NFL_RAW.PLAY_BY_PLAY.RAW_STATS_PLAYER_WEEKLY "
            "WHERE source_file = 'stats_players/stats_player_week_2024.parquet'",
        )

    def test_copy_sql_contains_idempotent_file_load_parts(self):
        sql = snowflake_load.build_copy_sql(
            self.file_info,
            stage_name="NFL_RAW_STAGE",
            database="NFL_RAW",
            schema="PLAY_BY_PLAY",
        )

        self.assertIn("COPY INTO NFL_RAW.PLAY_BY_PLAY.RAW_STATS_PLAYER_WEEKLY", sql)
        self.assertIn("METADATA$FILENAME", sql)
        self.assertIn("'stats_player'", sql)
        self.assertIn("2024", sql)
        self.assertIn("FROM @NFL_RAW_STAGE", sql)
        self.assertIn("FILES = ('stats_players/stats_player_week_2024.parquet')", sql)
        self.assertIn("FORCE = TRUE", sql)
        self.assertIn("ON_ERROR = ABORT_STATEMENT", sql)

    def test_copy_sql_uses_null_source_year_for_single_file(self):
        file_info = {
            "dataset": "teams",
            "year": None,
            "s3_key": "teams/teams_colors_logos.parquet",
            "raw_table": "RAW_TEAMS",
        }

        sql = snowflake_load.build_copy_sql(file_info, stage_name="@NFL_RAW_STAGE")

        self.assertIn("NULL", sql)
        self.assertIn("FILES = ('teams/teams_colors_logos.parquet')", sql)


if __name__ == "__main__":
    unittest.main()
