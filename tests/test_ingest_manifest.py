import unittest
from unittest.mock import Mock, patch


from data import ingest_s3


class IngestManifestTests(unittest.TestCase):
    def test_all_expands_to_each_dataset_for_year_range(self):
        files = ingest_s3.build_file_manifest("all", [2024, 2025])

        self.assertEqual(len(files), 10)
        self.assertEqual(
            {file_info["dataset"] for file_info in files},
            set(ingest_s3.DATASETS.keys()),
        )

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

    def test_head_200_with_no_previous_metadata_is_new(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(
            status_code=200,
            headers={
                "ETag": "abc",
                "Last-Modified": "Sun, 29 Jun 2025 12:00:00 GMT",
                "Content-Length": "123",
            },
        )

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        file_result = ingest_s3.merge_previous_metadata(metadata, None)

        self.assertEqual(file_result["file_state"], "new")
        self.assertEqual(file_result["remote_etag"], "abc")
        self.assertEqual(file_result["remote_content_length"], 123)

    def test_head_200_with_matching_previous_metadata_is_unchanged(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(
            status_code=200,
            headers={
                "ETag": "abc",
                "Last-Modified": "Sun, 29 Jun 2025 12:00:00 GMT",
                "Content-Length": "123",
            },
        )

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        previous_metadata = {
            "remote_etag": metadata["remote_etag"],
            "remote_last_modified": metadata["remote_last_modified"],
            "remote_content_length": metadata["remote_content_length"],
        }
        file_result = ingest_s3.merge_previous_metadata(metadata, previous_metadata)

        self.assertEqual(file_result["file_state"], "unchanged")

    def test_head_200_with_changed_previous_metadata_is_updated(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(
            status_code=200,
            headers={
                "ETag": "abc",
                "Last-Modified": "Sun, 29 Jun 2025 12:00:00 GMT",
                "Content-Length": "123",
            },
        )

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        previous_metadata = {
            "remote_etag": "old",
            "remote_last_modified": metadata["remote_last_modified"],
            "remote_content_length": metadata["remote_content_length"],
        }
        file_result = ingest_s3.merge_previous_metadata(metadata, previous_metadata)

        self.assertEqual(file_result["file_state"], "updated")

    def test_head_404_is_missing(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(status_code=404, headers={})

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        self.assertEqual(metadata["file_state"], "missing")

    def test_head_403_is_failed(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(status_code=403, headers={})

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        self.assertEqual(metadata["file_state"], "failed")

    def test_head_429_is_failed(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(status_code=429, headers={})

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        self.assertEqual(metadata["file_state"], "failed")

    def test_head_500_is_failed(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        response = Mock(status_code=500, headers={})

        with patch("data.ingest_s3.requests.head", return_value=response):
            metadata = ingest_s3.check_remote_metadata(file_info)

        self.assertEqual(metadata["file_state"], "failed")

    def test_head_request_exception_is_failed(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]

        with patch(
            "data.ingest_s3.requests.head",
            side_effect=ingest_s3.requests.RequestException("network error"),
        ):
            metadata = ingest_s3.check_remote_metadata(file_info)

        self.assertEqual(metadata["file_state"], "failed")

    def test_dry_run_does_not_call_s3_upload(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        s3_client = Mock()
        response = Mock(status_code=200, headers={})

        with patch("data.ingest_s3.requests.head", return_value=response):
            results = ingest_s3.ingest_files(
                s3_client=s3_client,
                files=[file_info],
                run_id="test_run",
                run_type="dry_run",
                table_arg="pbp",
                dry_run=True,
            )

        s3_client.upload_fileobj.assert_not_called()
        self.assertEqual(len(results["actions"]["would_upload_new"]), 1)

    def test_sync_unchanged_file_does_not_call_s3_upload(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        s3_client = Mock()
        response = Mock(
            status_code=200,
            headers={
                "ETag": "abc",
                "Content-Length": "123",
            },
        )
        previous_metadata = {
            ingest_s3.metadata_lookup_key(file_info): {
                "remote_etag": "abc",
                "remote_last_modified": None,
                "remote_content_length": 123,
            }
        }

        with patch("data.ingest_s3.requests.head", return_value=response):
            results = ingest_s3.ingest_files(
                s3_client=s3_client,
                files=[file_info],
                run_id="test_run",
                run_type="sync",
                table_arg="pbp",
                sync_enabled=True,
                previous_metadata_lookup=previous_metadata,
            )

        s3_client.upload_fileobj.assert_not_called()
        self.assertEqual(len(results["actions"]["skipped_unchanged"]), 1)

    def test_failed_files_raise_after_processing(self):
        args = ingest_s3.parse_args(
            [
                "--table",
                "pbp",
                "--start-year",
                "2025",
                "--end-year",
                "2025",
                "--sync",
                "--dry-run",
            ]
        )
        failed_metadata = ingest_s3.build_base_file_result(
            ingest_s3.build_file_manifest("pbp", [2025])[0]
        )
        failed_metadata.update(
            {
                "file_state": "failed",
                "checked_at": ingest_s3.utc_now(),
                "error_message": "remote metadata returned status_code=500",
            }
        )

        with patch("data.ingest_s3.check_remote_metadata", return_value=failed_metadata):
            with patch("data.ingest_s3.get_previous_metadata_lookup", return_value={}):
                with self.assertRaises(RuntimeError):
                    ingest_s3.main(args)

    def test_ingestion_metadata_row_matches_metadata_table_shape(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        file_result = ingest_s3.build_base_file_result(file_info)
        file_result.update(
            {
                "http_status_code": 200,
                "run_id": "test_run",
                "pipeline_name": "nfl_pipeline_v1",
                "run_type": "sync",
                "table_arg": "pbp",
                "remote_etag": "abc",
                "remote_content_length": 123,
                "file_state": "new",
                "ingestion_action": "uploaded",
                "checked_at": ingest_s3.utc_now(),
                "uploaded_at": ingest_s3.utc_now(),
            }
        )
        row = ingest_s3.build_ingestion_metadata_row(file_result)

        self.assertEqual(len(row), 25)
        self.assertEqual(row[0], "test_run")
        self.assertEqual(row[1], "nfl_pipeline_v1")
        self.assertEqual(row[10], 200)
        self.assertEqual(row[18], "uploaded")

    def test_ingestion_metadata_insert_sql_targets_expected_columns(self):
        sql = ingest_s3.build_ingestion_metadata_insert_sql(
            "NFL_ANALYTICS.audit.ingestion_file_manifest"
        )

        self.assertIn("INSERT INTO NFL_ANALYTICS.audit.ingestion_file_manifest", sql)
        self.assertIn("run_id", sql)
        self.assertIn("pipeline_name", sql)
        self.assertIn("http_status_code", sql)
        self.assertIn("duration_seconds", sql)

    def test_previous_metadata_lookup_uses_one_batch_query(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]

        with patch(
            "data.ingest_s3.lookup_previous_successful_metadata",
            return_value={},
        ) as lookup_previous:
            result = ingest_s3.get_previous_metadata_lookup(
                [file_info],
                enabled=True,
            )

        lookup_previous.assert_called_once_with([file_info])
        self.assertEqual(result, {})

    def test_main_skips_metadata_write_without_run_id(self):
        args = ingest_s3.parse_args(
            [
                "--table",
                "pbp",
                "--start-year",
                "2025",
                "--end-year",
                "2025",
            ]
        )
        upload_result = {
            "upload_status": "uploaded",
            "http_status_code": 200,
            "error_message": None,
            "started_at": ingest_s3.utc_now(),
            "finished_at": ingest_s3.utc_now(),
            "duration_seconds": 1,
        }

        with patch("data.ingest_s3.boto3.client", return_value=Mock()):
            with patch("data.ingest_s3.upload_file", return_value=upload_result):
                with patch(
                    "data.ingest_s3.write_ingestion_metadata_results"
                ) as write_metadata:
                    ingest_s3.main(args)

        write_metadata.assert_not_called()

    def test_ingestion_metadata_write_requires_run_id(self):
        file_info = ingest_s3.build_file_manifest("pbp", [2025])[0]
        file_result = ingest_s3.build_base_file_result(file_info)
        file_result["ingestion_action"] = "uploaded"
        batch_summary = {"run_id": None}

        with self.assertRaises(ValueError):
            ingest_s3.write_ingestion_metadata_results(
                batch_summary,
                [file_result],
            )

if __name__ == "__main__":
    unittest.main()
