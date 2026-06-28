import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

from snowflake_load import load_uploaded_files


BUCKET_NAME = "nfl-pipeline-raw"
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"
REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_START_YEAR = 2002

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


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s - %(message)s",
    )


def file_year_label(file_info):
    return file_info["year"] if file_info["year"] is not None else "single"


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


def upload_file(s3_client, file_info):
    year_label = file_year_label(file_info)

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
                logger.warning(
                    "remote file unavailable dataset=%s year=%s status_code=%s",
                    file_info["dataset"],
                    year_label,
                    response.status_code,
                )
                return "failed", f"remote file returned status_code={response.status_code}"

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
        return "uploaded", None

    except requests.RequestException as exc:
        logger.exception(
            "download failed dataset=%s year=%s url=%s",
            file_info["dataset"],
            year_label,
            file_info["url"],
        )
        return "failed", str(exc)

    except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
        logger.exception(
            "s3 upload failed dataset=%s year=%s s3_key=%s",
            file_info["dataset"],
            year_label,
            file_info["s3_key"],
        )
        return "failed", str(exc)


def build_manifest_record(file_info, upload_status, error_message):
    return {
        "dataset": file_info["dataset"],
        "source_year": file_info["year"],
        "source_url": file_info["url"],
        "s3_bucket": BUCKET_NAME,
        "s3_key": file_info["s3_key"],
        "upload_status": upload_status,
        "error_message": error_message,
        "snowflake_load_eligible": upload_status == "uploaded",
    }


def log_result_details(result_name, files):
    log_func = logger.error if result_name == "failed" else logger.warning

    for file_info in files:
        log_func(
            "ingestion result=%s dataset=%s year=%s s3_key=%s url=%s",
            result_name,
            file_info["dataset"],
            file_year_label(file_info),
            file_info["s3_key"],
            file_info["url"],
        )


def ingest_files(s3_client, files):
    results = {
        "uploaded": [],
        "failed": [],
        "manifest_records": [],
    }

    for file_info in files:
        result, error_message = upload_file(s3_client, file_info)
        results[result].append(file_info)
        results["manifest_records"].append(
            build_manifest_record(file_info, result, error_message)
        )

    logger.info(
        "ingestion complete uploaded=%s failed=%s",
        len(results["uploaded"]),
        len(results["failed"]),
    )

    log_result_details("failed", results["failed"])

    return results


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


def parse_args():
    current_date = datetime.now()
    default_end_year = default_season_end_year(current_date)

    parser = argparse.ArgumentParser(description="Ingest nflverse parquet files to S3")
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
        "--manifest-output-path",
        type=str,
        help="Path where ingestion manifest JSON should be written",
    )
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

    return parser.parse_args()


def main():
    configure_logging()
    args = parse_args()

    years = build_years(args.start_year, args.end_year)
    files = build_file_manifest(args.table, years)

    logger.info(
        "starting ingestion table=%s file_count=%s bucket=%s start_year=%s end_year=%s",
        args.table,
        len(files),
        BUCKET_NAME,
        args.start_year,
        args.end_year,
    )

    s3_client = boto3.client("s3")
    results = ingest_files(s3_client, files)
    write_manifest(results["manifest_records"], args.manifest_output_path)

    if results["failed"]:
        raise RuntimeError(f"Ingestion failed for {len(results['failed'])} file(s)")

    if args.load_snowflake:
        load_uploaded_files(results["uploaded"])


if __name__ == "__main__":
    main()
