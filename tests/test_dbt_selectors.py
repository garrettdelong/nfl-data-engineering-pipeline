import unittest
from unittest.mock import Mock, patch

from data import dbt_selectors


class DbtSelectorsTests(unittest.TestCase):
    def test_build_dbt_selectors_maps_uploaded_datasets(self):
        selectors = dbt_selectors.build_dbt_selectors(
            ["pbp", "schedules", "teams", "weekly_rosters", "stats_player", "stats_team"]
        )

        self.assertEqual(
            selectors,
            [
                "stg_play_by_play+",
                "stg_games+",
                "stg_teams_colors_logos+",
                "stg_roster_weekly+",
                "stg_stats_player_week+",
                "stg_stats_team_week+",
            ],
        )

    def test_build_dbt_selectors_deduplicates_selectors(self):
        selectors = dbt_selectors.build_dbt_selectors(
            ["pbp", "pbp"],
        )

        self.assertEqual(selectors, ["stg_play_by_play+"])

    def test_build_dbt_selector_args_returns_select_clause(self):
        selector_args = dbt_selectors.build_dbt_selector_args(
            ["stg_play_by_play+", "stg_games+"]
        )

        self.assertEqual(selector_args, "--select stg_play_by_play+ stg_games+")

    def test_get_dbt_selector_args_returns_default_command_when_forced_without_uploads(self):
        with patch("data.dbt_selectors.get_uploaded_datasets", return_value=[]):
            selector_args = dbt_selectors.get_dbt_selector_args(
                run_id="test_run",
                force_downstream=True,
            )

        self.assertEqual(selector_args, "")

    def test_get_uploaded_datasets_filters_to_uploaded_rows_for_run_id(self):
        cursor = Mock()
        cursor.fetchall.return_value = [("pbp",), ("teams",)]
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=None)

        connection = Mock()
        connection.cursor.return_value = cursor

        config = {"database": "NFL_ANALYTICS", "schema": "audit"}

        with patch("data.dbt_selectors.connect_snowflake", return_value=connection):
            uploaded_datasets = dbt_selectors.get_uploaded_datasets(
                run_id="test_run",
                config=config,
            )

        executed_sql = cursor.execute.call_args.args[0]
        executed_params = cursor.execute.call_args.args[1]

        self.assertIn("FROM NFL_ANALYTICS.audit.ingestion_file_manifest", executed_sql)
        self.assertIn("run_id = %s", executed_sql)
        self.assertIn("ingestion_action = 'uploaded'", executed_sql)
        self.assertEqual(executed_params, ("test_run",))
        self.assertEqual(uploaded_datasets, ["pbp", "teams"])
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
