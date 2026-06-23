import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

import ingest_s3


class IngestManifestTests(unittest.TestCase):
    def test_all_expands_to_each_dataset_for_year_range(self):
        files = ingest_s3.build_file_manifest("all", [2024, 2025])

        self.assertEqual(len(files), 12)
        self.assertEqual(
            {file_info["dataset"] for file_info in files},
            set(ingest_s3.DATASETS.keys()),
        )

    def test_stats_player_uses_physical_s3_prefix(self):
        files = ingest_s3.build_file_manifest("stats_player", [2024])

        self.assertEqual(files[0]["s3_key"], "stats_players/stats_player_week_2024.parquet")
        self.assertEqual(files[0]["release"], "stats_player")
        self.assertEqual(files[0]["raw_table"], "RAW_STATS_PLAYER_WEEK")

    def test_stats_team_uses_physical_s3_prefix(self):
        files = ingest_s3.build_file_manifest("stats_team", [2024])

        self.assertEqual(files[0]["s3_key"], "stats_teams/stats_team_week_2024.parquet")
        self.assertEqual(files[0]["release"], "stats_team")
        self.assertEqual(files[0]["raw_table"], "RAW_STATS_TEAM_WEEK")

    def test_single_file_dataset_has_no_year(self):
        files = ingest_s3.build_file_manifest("teams", [2024])

        self.assertEqual(len(files), 1)
        self.assertIsNone(files[0]["year"])
        self.assertEqual(files[0]["s3_key"], "teams/teams_colors_logos.parquet")


if __name__ == "__main__":
    unittest.main()
