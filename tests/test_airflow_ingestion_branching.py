import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "airflow"
    / "dags"
    / "airflow_ingestion_branching.py"
)
spec = importlib.util.spec_from_file_location(
    "airflow_ingestion_branching",
    MODULE_PATH,
)
airflow_ingestion_branching = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = airflow_ingestion_branching
spec.loader.exec_module(airflow_ingestion_branching)


class AirflowIngestionBranchingTests(unittest.TestCase):
    def load_snowflake_raw_mock(self, manifest_records):
        module = Mock()
        module.read_manifest.return_value = manifest_records
        module.get_snowflake_eligible_files.side_effect = lambda records: [
            record
            for record in records
            if record.get("snowflake_load_eligible")
        ]
        return module

    def test_choose_downstream_path_continues_when_manifest_has_eligible_files(self):
        manifest_records = [
            {
                "dataset": "teams",
                "source_year": None,
                "s3_key": "teams/teams_colors_logos.parquet",
                "snowflake_load_eligible": False,
            },
            {
                "dataset": "schedules",
                "source_year": None,
                "s3_key": "schedules/games.parquet",
                "snowflake_load_eligible": True,
            },
        ]

        with patch.dict(
            "sys.modules",
            {"data.load_snowflake_raw": self.load_snowflake_raw_mock(manifest_records)},
        ):
            selected_task = airflow_ingestion_branching.choose_downstream_path(
                manifest_path="manifest.json",
                variable_getter=lambda name, default_var=None: "false",
            )

        self.assertEqual(selected_task, "load_snowflake_raw")

    def test_choose_downstream_path_skips_when_manifest_has_no_eligible_files(self):
        manifest_records = [
            {
                "dataset": "teams",
                "source_year": None,
                "s3_key": "teams/teams_colors_logos.parquet",
                "snowflake_load_eligible": False,
            },
            {
                "dataset": "schedules",
                "source_year": None,
                "s3_key": "schedules/games.parquet",
                "snowflake_load_eligible": False,
            },
        ]

        with patch.dict(
            "sys.modules",
            {"data.load_snowflake_raw": self.load_snowflake_raw_mock(manifest_records)},
        ):
            selected_task = airflow_ingestion_branching.choose_downstream_path(
                manifest_path="manifest.json",
                variable_getter=lambda name, default_var=None: "false",
            )

        self.assertEqual(selected_task, "end")

    def test_choose_downstream_path_can_be_forced_by_dag_run_conf(self):
        dag_run = SimpleNamespace(conf={"force_downstream": "true"})

        selected_task = airflow_ingestion_branching.choose_downstream_path(
            manifest_path="manifest.json",
            variable_getter=lambda name, default_var=None: "false",
            dag_run=dag_run,
        )

        self.assertEqual(selected_task, "load_snowflake_raw")

    def test_choose_downstream_path_can_be_forced_by_variable(self):
        selected_task = airflow_ingestion_branching.choose_downstream_path(
            manifest_path="manifest.json",
            variable_getter=lambda name, default_var=None: "true",
        )

        self.assertEqual(selected_task, "load_snowflake_raw")


if __name__ == "__main__":
    unittest.main()
