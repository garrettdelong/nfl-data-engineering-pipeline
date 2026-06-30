import argparse
import json
import logging
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

from data.cli_args import (
    add_log_level_argument,
    add_manifest_output_argument,
    add_run_id_argument,
)
from data.logging_config import configure_logging
from data.pipeline_audit import record_file_events
from data.snowflake_client import (
    connect_snowflake,
    get_scoped_snowflake_config_from_env,
    qualified_table_name,
)
from data.snowflake_load import load_uploaded_files


BUCKET_NAME = "nfl-pipeline-raw"
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"
REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_START_YEAR = 2002
METADATA_TABLE_NAME = "ingestion_file_manifest"
PIPELINE_NAME = "nfl_pipeline_v1"

FILE_STATES = [
    "new",
    "updated",
    "unchanged",
    "missing",
    "failed",
]

INGESTION_ACTIONS = [
    "uploaded",
    "skipped_unchanged",
    "skipped_missing",
    "failed",
    "would_upload_new",
    "would_upload_updated",
    "would_skip_unchanged",
    "would_skip_missing",
    "would_fail",
]

DATASETS = {
    "pbp": {
        "file_stem": "play_by_play",
        "release": "pbp",
        "s3_prefix": "pbp",
        "raw_table": "RAW_PLAY_BY_PLAY",
        "single_file": False,
    },
    "schedules": {
        "file_stem": "games",
        "release": "schedules",
        "s3_prefix": "schedules",
        "raw_table": "RAW_GAMES",
        "single_file": True,
    },
    "teams": {
        "file_stem": "teams_colors_logos",
        "release": "teams",
        "s3_prefix": "teams",
        "raw_table": "RAW_TEAMS_COLORS_LOGOS",
        "single_file": True,
    },
    "stats_player": {
        "file_stem": "stats_player_week",
        "release": "stats_player",
        "s3_prefix": "stats_players",
        "raw_table": "RAW_STATS_PLAYER_WEEK",
        "single_file": False,
    },
    "weekly_rosters": {
        "file_stem": "roster_weekly",
        "release": "weekly_rosters",
        "s3_prefix": "weekly_rosters",
        "raw_table": "RAW_ROSTER_WEEKLY",
        "single_file": False,
        "start_year": 2002,
    },
    "stats_team": {
        "file_stem": "stats_team_week",
        "release": "stats_team",
        "s3_prefix": "stats_teams",
        "raw_table": "RAW_STATS_TEAM_WEEK",
        "single_file": False,
    },
}

TABLE_CHOICES = list(DATASETS.keys()) + ["all"]

logger = logging.getLogger(__name__)


def file_year_label(file_info):
    return file_info["year"] if file_info["year"] is not None else "single"


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def timestamp_string(value):
    if value is None:
        return None

    return value.isoformat(timespec="seconds")


def parse_http_datetime(value):
    if not value:
        return None

    try:
        parsed_value = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        logger.warning("could not parse http datetime value=%s", value)
        return None

    if parsed_value.tzinfo:
        return parsed_value.replace(tzinfo=None)

    return parsed_value


def parse_content_length(value):
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        logger.warning("could not parse content length value=%s", value)
        return None


def build_base_file_result(file_info):
    return {
        "run_id": None,
        "pipeline_name": None,
        "run_type": None,
        "table_arg": None,
        "dataset": file_info["dataset"],
        "file_stem": file_info["file_stem"],
        "source_year": file_info["year"],
        "source_url": file_info["url"],
        "s3_bucket": BUCKET_NAME,
        "s3_key": file_info["s3_key"],
        "http_status_code": None,
        "remote_etag": None,
        "remote_last_modified": None,
        "remote_content_length": None,
        "previous_remote_etag": None,
        "previous_remote_last_modified": None,
        "previous_remote_content_length": None,
        "file_state": None,
        "ingestion_action": None,
        "checked_at": None,
        "uploaded_at": None,
        "started_at": None,
        "finished_at": None,
        "duration_seconds": None,
        "error_message": None,
    }


def add_run_context(file_result, run_id, run_type, table_arg):
    file_result.update(
        {
            "run_id": run_id,
            "pipeline_name": PIPELINE_NAME,
            "run_type": run_type,
            "table_arg": table_arg,
        }
    )
    return file_result


def build_file_info(dataset, dataset_config, file_name, year):
    return {
        "dataset": dataset,
        "file_stem": dataset_config["file_stem"],
        "year": year,
        "release": dataset_config["release"],
        "s3_prefix": dataset_config["s3_prefix"],
        "raw_table": dataset_config["raw_table"],
        "url": f"{BASE_URL}/{dataset_config['release']}/{file_name}",
        "s3_key": f"{dataset_config['s3_prefix']}/{file_name}",
    }


def build_year_file(dataset, dataset_config, year):
    file_name = f"{dataset_config['file_stem']}_{year}.parquet"
    return build_file_info(dataset, dataset_config, file_name, year)


def build_single_file(dataset, dataset_config):
    file_name = f"{dataset_config['file_stem']}.parquet"
    return build_file_info(dataset, dataset_config, file_name, None)


def get_selected_datasets(table_arg):
    if table_arg == "all":
        return DATASETS.items()

    return [(table_arg, DATASETS[table_arg])]


def build_file_manifest(table_arg, years):
    files = []

    for dataset, dataset_config in get_selected_datasets(table_arg):
        if dataset_config["single_file"]:
            files.append(build_single_file(dataset, dataset_config))
            continue

        dataset_start_year = dataset_config.get("start_year")
        dataset_years = [
            year
            for year in years
            if dataset_start_year is None or year >= dataset_start_year
        ]

        for year in dataset_years:
            files.append(build_year_file(dataset, dataset_config, year))

    return files


def check_remote_metadata(file_info):
    checked_at = utc_now()

    logger.info(
        "checking remote metadata dataset=%s year=%s url=%s",
        file_info["dataset"],
        file_year_label(file_info),
        file_info["url"],
    )

    try:
        response = requests.head(
            file_info["url"],
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.exception(
            "remote metadata check failed dataset=%s year=%s url=%s",
            file_info["dataset"],
            file_year_label(file_info),
            file_info["url"],
        )
        metadata = build_base_file_result(file_info)
        metadata.update(
            {
                "file_state": "failed",
                "http_status_code": None,
                "checked_at": checked_at,
                "error_message": str(exc),
            }
        )
        return metadata

    metadata = build_base_file_result(file_info)
    metadata["checked_at"] = checked_at
    metadata["http_status_code"] = response.status_code

    if response.status_code == 404:
        logger.warning(
            "remote file missing dataset=%s year=%s url=%s",
            file_info["dataset"],
            file_year_label(file_info),
            file_info["url"],
        )
        metadata.update(
            {
                "file_state": "missing",
                "error_message": "remote file returned status_code=404",
            }
        )
        return metadata

    if response.status_code != 200:
        logger.warning(
            "remote metadata check returned non-200 dataset=%s year=%s status_code=%s",
            file_info["dataset"],
            file_year_label(file_info),
            response.status_code,
        )
        metadata.update(
            {
                "file_state": "failed",
                "error_message": f"remote metadata returned status_code={response.status_code}",
            }
        )
        return metadata

    metadata.update(
        {
            "remote_etag": response.headers.get("ETag"),
            "remote_last_modified": parse_http_datetime(
                response.headers.get("Last-Modified")
            ),
            "remote_content_length": parse_content_length(
                response.headers.get("Content-Length")
            ),
        }
    )

    return metadata


def metadata_values_match(current_metadata, previous_metadata):
    comparable_fields = [
        "remote_etag",
        "remote_last_modified",
        "remote_content_length",
    ]

    return all(
        current_metadata.get(field) == previous_metadata.get(field)
        for field in comparable_fields
    )


def classify_file_state(current_metadata, previous_metadata):
    if current_metadata["file_state"] in ["missing", "failed"]:
        return current_metadata["file_state"]

    if previous_metadata is None:
        return "new"

    if metadata_values_match(current_metadata, previous_metadata):
        return "unchanged"

    return "updated"


def merge_previous_metadata(current_metadata, previous_metadata):
    if previous_metadata:
        current_metadata.update(
            {
                "previous_remote_etag": previous_metadata.get("remote_etag"),
                "previous_remote_last_modified": previous_metadata.get(
                    "remote_last_modified"
                ),
                "previous_remote_content_length": previous_metadata.get(
                    "remote_content_length"
                ),
            }
        )

    current_metadata["file_state"] = classify_file_state(
        current_metadata,
        previous_metadata,
    )
    return current_metadata


def get_metadata_table_name(config):
    table_name = qualified_table_name(
        METADATA_TABLE_NAME,
        database=config.get("database"),
        schema=config.get("schema"),
    )
    return table_name


def normalize_source_year(value):
    if value is None:
        return None

    return int(value)


def lookup_previous_successful_metadata(files, config=None):
    if not files:
        return {}

    snowflake_config = config or get_scoped_snowflake_config_from_env(
        "INGESTION_METADATA"
    )
    table_name = get_metadata_table_name(snowflake_config)
    connection = connect_snowflake(snowflake_config)

    query = f"""
SELECT
    dataset,
    source_year,
    s3_key,
    remote_etag,
    remote_last_modified,
    remote_content_length
FROM (
    SELECT
        dataset,
        source_year,
        s3_key,
        remote_etag,
        remote_last_modified,
        remote_content_length,
        ROW_NUMBER() OVER (
            PARTITION BY dataset, source_year, s3_key
            ORDER BY uploaded_at DESC, created_at DESC
        ) AS row_number
    FROM {table_name}
    WHERE ingestion_action = 'uploaded'
)
WHERE row_number = 1
""".strip()

    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
    finally:
        connection.close()

    expected_keys = {metadata_lookup_key(file_info) for file_info in files}
    lookup = {}

    for row in rows:
        key = (
            row[0],
            normalize_source_year(row[1]),
            row[2],
        )

        if key not in expected_keys:
            continue

        lookup[key] = {
            "remote_etag": row[3],
            "remote_last_modified": row[4],
            "remote_content_length": row[5],
        }

    return lookup


def get_previous_metadata_lookup(files, enabled):
    if not enabled:
        return {}

    return lookup_previous_successful_metadata(files)


def metadata_lookup_key(file_info):
    return (
        file_info["dataset"],
        file_info["year"],
        file_info["s3_key"],
    )


def should_upload_file(file_result, sync_enabled, replace_enabled):
    if file_result["file_state"] in ["missing", "failed"]:
        return False

    if replace_enabled:
        return True

    if not sync_enabled:
        return True

    return file_result["file_state"] in ["new", "updated"]


def dry_run_action_for_state(file_state):
    return {
        "new": "would_upload_new",
        "updated": "would_upload_updated",
        "unchanged": "would_skip_unchanged",
        "missing": "would_skip_missing",
        "failed": "would_fail",
    }[file_state]


def skipped_action_for_state(file_state):
    return {
        "unchanged": "skipped_unchanged",
        "missing": "skipped_missing",
        "failed": "failed",
    }[file_state]


def upload_file(s3_client, file_info):
    year_label = file_year_label(file_info)
    started_at = utc_now()

    logger.info(
        "uploading file dataset=%s year=%s source=%s target=s3://%s/%s",
        file_info["dataset"],
        year_label,
        file_info["url"],
        BUCKET_NAME,
        file_info["s3_key"],
    )

    try:
        with requests.get(
            file_info["url"],
            stream=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                finished_at = utc_now()
                if response.status_code == 404:
                    logger.warning(
                        "remote file missing dataset=%s year=%s status_code=%s",
                        file_info["dataset"],
                        year_label,
                        response.status_code,
                    )
                    upload_status = "missing"
                else:
                    logger.warning(
                        "remote file unavailable dataset=%s year=%s status_code=%s",
                        file_info["dataset"],
                        year_label,
                        response.status_code,
                    )
                    upload_status = "failed"

                return {
                    "upload_status": upload_status,
                    "http_status_code": response.status_code,
                    "error_message": f"remote file returned status_code={response.status_code}",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                }

            s3_client.upload_fileobj(
                response.raw,
                BUCKET_NAME,
                file_info["s3_key"],
            )

        logger.info(
            "uploaded file dataset=%s year=%s s3_key=%s",
            file_info["dataset"],
            year_label,
            file_info["s3_key"],
        )
        finished_at = utc_now()
        return {
            "upload_status": "uploaded",
            "http_status_code": 200,
            "error_message": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }

    except requests.RequestException as exc:
        finished_at = utc_now()
        logger.exception(
            "download failed dataset=%s year=%s url=%s",
            file_info["dataset"],
            year_label,
            file_info["url"],
        )
        return {
            "upload_status": "failed",
            "http_status_code": None,
            "error_message": str(exc),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }

    except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
        finished_at = utc_now()
        logger.exception(
            "s3 upload failed dataset=%s year=%s s3_key=%s",
            file_info["dataset"],
            year_label,
            file_info["s3_key"],
        )
        return {
            "upload_status": "failed",
            "http_status_code": None,
            "error_message": str(exc),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }


def build_manifest_record(file_info, file_result):
    return {
        "dataset": file_info["dataset"],
        "file_stem": file_info["file_stem"],
        "source_year": file_info["year"],
        "source_url": file_info["url"],
        "s3_bucket": BUCKET_NAME,
        "s3_key": file_info["s3_key"],
        "upload_status": file_result["ingestion_action"],
        "snowflake_load_status": (
            "not_attempted"
            if file_result["ingestion_action"] == "uploaded"
            else "skipped"
        ),
        "snowflake_table_name": file_info["raw_table"],
        "remote_etag": file_result["remote_etag"],
        "remote_last_modified": timestamp_string(file_result["remote_last_modified"]),
        "remote_content_length": file_result["remote_content_length"],
        "previous_remote_etag": file_result["previous_remote_etag"],
        "previous_remote_last_modified": timestamp_string(
            file_result["previous_remote_last_modified"]
        ),
        "previous_remote_content_length": file_result[
            "previous_remote_content_length"
        ],
        "http_status_code": file_result["http_status_code"],
        "file_state": file_result["file_state"],
        "started_at": timestamp_string(file_result["started_at"]),
        "finished_at": timestamp_string(file_result["finished_at"]),
        "duration_seconds": file_result["duration_seconds"],
        "error_message": file_result["error_message"],
        "snowflake_load_eligible": file_result["ingestion_action"] == "uploaded",
    }


def log_failed_file_details(files):
    for file_info in files:
        logger.error(
            "ingestion failed dataset=%s year=%s s3_key=%s url=%s",
            file_info["dataset"],
            file_year_label(file_info),
            file_info["s3_key"],
            file_info["url"],
        )


def ingest_files(
    s3_client,
    files,
    run_id,
    run_type,
    table_arg,
    sync_enabled=False,
    dry_run=False,
    replace_enabled=False,
    previous_metadata_lookup=None,
):
    previous_metadata_lookup = previous_metadata_lookup or {}
    results = {
        "states": {state: [] for state in FILE_STATES},
        "actions": {action: [] for action in INGESTION_ACTIONS},
        "uploaded": [],
        "missing": [],
        "failed": [],
        "manifest_records": [],
        "file_results": [],
    }

    for file_info in files:
        if sync_enabled or dry_run:
            file_result = check_remote_metadata(file_info)
            previous_metadata = previous_metadata_lookup.get(
                metadata_lookup_key(file_info)
            )
            file_result = merge_previous_metadata(file_result, previous_metadata)
        else:
            file_result = build_base_file_result(file_info)
            file_result["file_state"] = "new"

        file_result = add_run_context(
            file_result,
            run_id=run_id,
            run_type=run_type,
            table_arg=table_arg,
        )

        should_upload = should_upload_file(
            file_result,
            sync_enabled=sync_enabled,
            replace_enabled=replace_enabled,
        )

        if dry_run:
            action = dry_run_action_for_state(file_result["file_state"])
            file_result["ingestion_action"] = action
            logger.info(
                "dry run action=%s dataset=%s year=%s s3_key=%s",
                action,
                file_info["dataset"],
                file_year_label(file_info),
                file_info["s3_key"],
            )
        elif should_upload:
            upload_result = upload_file(s3_client, file_info)
            upload_action = upload_result["upload_status"]
            if upload_action == "missing":
                upload_action = "skipped_missing"
            file_result.update(
                {
                    "ingestion_action": upload_action,
                    "http_status_code": upload_result["http_status_code"],
                    "started_at": upload_result["started_at"],
                    "finished_at": upload_result["finished_at"],
                    "duration_seconds": upload_result["duration_seconds"],
                    "uploaded_at": (
                        upload_result["finished_at"]
                        if upload_result["upload_status"] == "uploaded"
                        else None
                    ),
                    "error_message": upload_result["error_message"],
                }
            )
            if upload_result["upload_status"] == "missing":
                file_result["file_state"] = "missing"
            if upload_result["upload_status"] == "failed":
                file_result["file_state"] = "failed"
        else:
            action = skipped_action_for_state(file_result["file_state"])
            file_result["ingestion_action"] = action
            logger.info(
                "skipping file action=%s dataset=%s year=%s s3_key=%s",
                action,
                file_info["dataset"],
                file_year_label(file_info),
                file_info["s3_key"],
            )

        action = file_result["ingestion_action"]
        results["states"][file_result["file_state"]].append(file_info)
        results["actions"][action].append(file_info)
        results["file_results"].append(file_result)
        results["manifest_records"].append(build_manifest_record(file_info, file_result))

        if action == "uploaded":
            results["uploaded"].append(file_info)
        if action in ["skipped_missing", "would_skip_missing"] or file_result[
            "file_state"
        ] == "missing":
            results["missing"].append(file_info)
        if action in ["failed", "would_fail"] or file_result["file_state"] == "failed":
            results["failed"].append(file_info)

    log_ingestion_summary(results)
    log_failed_file_details(results["failed"])

    return results


def build_batch_summary(
    run_id,
    run_type,
    table_arg,
    start_year,
    end_year,
    results,
):
    state_counts = {
        state: len(results["states"][state])
        for state in FILE_STATES
    }
    uploaded_count = len(results["actions"]["uploaded"])
    planned_upload_count = (
        len(results["actions"]["would_upload_new"])
        + len(results["actions"]["would_upload_updated"])
    )
    changed_file_count = state_counts["new"] + state_counts["updated"]

    if state_counts["failed"] > 0:
        batch_status = "failed"
    elif state_counts["missing"] > 0:
        batch_status = "success_with_missing"
    elif uploaded_count > 0:
        batch_status = "success_with_uploads"
    elif changed_file_count > 0:
        batch_status = "success_with_changes"
    else:
        batch_status = "success_no_changes"

    return {
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "run_type": run_type,
        "table_arg": table_arg,
        "start_year": start_year,
        "end_year": end_year,
        "file_count": len(results["file_results"]),
        "new_count": state_counts["new"],
        "updated_count": state_counts["updated"],
        "unchanged_count": state_counts["unchanged"],
        "missing_count": state_counts["missing"],
        "failed_count": state_counts["failed"],
        "uploaded_count": uploaded_count,
        "planned_upload_count": planned_upload_count,
        "changed_file_count": changed_file_count,
        "batch_status": batch_status,
    }


def log_ingestion_summary(results):
    uploaded_count = len(results["actions"]["uploaded"])
    planned_upload_count = (
        len(results["actions"]["would_upload_new"])
        + len(results["actions"]["would_upload_updated"])
    )
    changed_file_count = len(results["states"]["new"]) + len(
        results["states"]["updated"]
    )

    logger.info(
        "ingestion summary uploaded=%s planned_uploads=%s updated=%s unchanged=%s missing=%s failed=%s changed_files=%s",
        uploaded_count,
        planned_upload_count,
        len(results["states"]["updated"]),
        len(results["states"]["unchanged"]),
        len(results["states"]["missing"]),
        len(results["states"]["failed"]),
        changed_file_count,
    )


def build_ingestion_metadata_row(file_result):
    return (
        file_result["run_id"],
        file_result["pipeline_name"],
        file_result["run_type"],
        file_result["table_arg"],
        file_result["dataset"],
        file_result["file_stem"],
        file_result["source_year"],
        file_result["source_url"],
        file_result["s3_bucket"],
        file_result["s3_key"],
        file_result["http_status_code"],
        file_result["remote_etag"],
        file_result["remote_last_modified"],
        file_result["remote_content_length"],
        file_result["previous_remote_etag"],
        file_result["previous_remote_last_modified"],
        file_result["previous_remote_content_length"],
        file_result["file_state"],
        file_result["ingestion_action"],
        file_result["checked_at"],
        file_result["uploaded_at"],
        file_result["started_at"],
        file_result["finished_at"],
        file_result["duration_seconds"],
        file_result["error_message"],
    )


def build_ingestion_metadata_insert_sql(table_name):
    return f"""
INSERT INTO {table_name} (
    run_id,
    pipeline_name,
    run_type,
    table_arg,
    dataset,
    file_stem,
    source_year,
    source_url,
    s3_bucket,
    s3_key,
    http_status_code,
    remote_etag,
    remote_last_modified,
    remote_content_length,
    previous_remote_etag,
    previous_remote_last_modified,
    previous_remote_content_length,
    file_state,
    ingestion_action,
    checked_at,
    uploaded_at,
    started_at,
    finished_at,
    duration_seconds,
    error_message
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)
""".strip()


def write_ingestion_metadata_results(batch_summary, file_results, config=None):
    if not file_results:
        logger.info(
            "no ingestion metadata rows to write run_id=%s",
            batch_summary["run_id"],
        )
        return

    if not batch_summary.get("run_id") or any(
        not file_result.get("run_id")
        for file_result in file_results
    ):
        raise ValueError("run_id is required to write ingestion metadata")

    snowflake_config = config or get_scoped_snowflake_config_from_env(
        "INGESTION_METADATA"
    )
    table_name = get_metadata_table_name(snowflake_config)
    rows = [
        build_ingestion_metadata_row(file_result)
        for file_result in file_results
    ]
    connection = connect_snowflake(snowflake_config)

    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            cursor.executemany(build_ingestion_metadata_insert_sql(table_name), rows)
            cursor.execute("COMMIT")
    except Exception:
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        logger.exception(
            "snowflake ingestion metadata write failed run_id=%s",
            batch_summary["run_id"],
        )
        raise
    finally:
        connection.close()

    logger.info(
        "wrote snowflake ingestion metadata run_id=%s file_count=%s",
        batch_summary["run_id"],
        len(file_results),
    )


def write_manifest(manifest_records, manifest_path):
    if not manifest_path:
        return

    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest_records, manifest_file, indent=2)

    logger.info(
        "wrote ingestion manifest path=%s file_count=%s",
        path,
        len(manifest_records),
    )


def build_years(start_year, end_year):
    if start_year > end_year:
        raise ValueError("--start-year cannot be greater than --end-year")

    return list(range(start_year, end_year + 1))


def default_season_end_year(current_date):
    if current_date.month < 9:
        return current_date.year - 1

    return current_date.year


def parse_args(argv=None):
    current_date = datetime.now()
    default_end_year = default_season_end_year(current_date)

    parser = argparse.ArgumentParser(description="Ingest nflverse parquet files to S3")
    add_log_level_argument(parser)
    add_run_id_argument(parser)
    parser.add_argument(
        "--table",
        type=str,
        required=True,
        choices=TABLE_CHOICES,
        help="Which dataset to ingest",
    )
    parser.add_argument(
        "--load-snowflake",
        action="store_true",
        help="Load successfully uploaded files into Snowflake raw tables",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Check remote metadata and upload only new or changed files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview ingestion actions without uploading or writing metadata",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Upload files even when sync metadata indicates they are unchanged",
    )
    parser.add_argument(
        "--write-audit-events",
        action="store_true",
        help="Write ingestion file events to Snowflake audit tables",
    )
    add_manifest_output_argument(parser)
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        help="First season year to ingest for year-partitioned datasets",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=default_end_year,
        help="Last season year to ingest for year-partitioned datasets. Defaults to the prior year before September.",
    )

    return parser.parse_args(argv)


def main(args=None):
    if args is None:
        args = parse_args()

    years = build_years(args.start_year, args.end_year)
    files = build_file_manifest(args.table, years)
    run_id = args.run_id or str(uuid.uuid4())
    run_type = "dry_run" if args.dry_run else "sync" if args.sync else "full"

    logger.info(
        "starting ingestion run_id=%s table=%s file_count=%s bucket=%s start_year=%s end_year=%s sync=%s dry_run=%s replace=%s",
        run_id,
        args.table,
        len(files),
        BUCKET_NAME,
        args.start_year,
        args.end_year,
        args.sync,
        args.dry_run,
        args.replace,
    )

    previous_metadata_lookup = get_previous_metadata_lookup(
        files,
        enabled=args.sync,
    )
    s3_client = None if args.dry_run else boto3.client("s3")
    results = ingest_files(
        s3_client=s3_client,
        files=files,
        run_id=run_id,
        run_type=run_type,
        table_arg=args.table,
        sync_enabled=args.sync,
        dry_run=args.dry_run,
        replace_enabled=args.replace,
        previous_metadata_lookup=previous_metadata_lookup,
    )
    batch_summary = build_batch_summary(
        run_id=run_id,
        run_type=run_type,
        table_arg=args.table,
        start_year=args.start_year,
        end_year=args.end_year,
        results=results,
    )
    logger.info("ingestion batch summary=%s", batch_summary)
    write_manifest(results["manifest_records"], args.manifest_output_path)

    if args.write_audit_events and not args.dry_run:
        if not args.run_id:
            raise ValueError("--run-id is required when --write-audit-events is used")

        record_file_events(args.run_id, results["manifest_records"])

    if args.run_id and not args.dry_run:
        write_ingestion_metadata_results(batch_summary, results["file_results"])
    elif not args.dry_run:
        logger.info(
            "skipping snowflake ingestion metadata write because --run-id was not provided"
        )

    if results["failed"]:
        raise RuntimeError(f"Ingestion failed for {len(results['failed'])} file(s)")

    if args.load_snowflake and not args.dry_run:
        load_uploaded_files(results["uploaded"])


if __name__ == "__main__":
    parsed_args = parse_args()
    configure_logging(parsed_args.log_level)
    main(parsed_args)
