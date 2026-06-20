import argparse
import logging
from datetime import datetime

import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

BUCKET_NAME = "nfl-pipeline-raw"
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"
REQUEST_TIMEOUT_SECONDS = 60

DATASETS = {
    "pbp": "play_by_play",
    "schedules": "games",
    "teams": "teams_colors_logos",
    "player_stats": "player_stats",
    "weekly_rosters": "roster_weekly",
    "stats_player": "stats_player_week",
    "stats_team": "stats_team_week",
}

TABLE_CHOICES = list(DATASETS.keys()) + ["all"]
SINGLE_FILE_DATASETS = {"schedules", "teams"}

logger = logging.getLogger(__name__)

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s - %(message)s"
    )

def file_year_label(file_info):
    return file_info["year"] if file_info["year"] is not None else "single"

def build_year_file (dataset, file_stem, year):
    file_name = f"{file_stem}_{year}.parquet"

    return {
        "dataset": dataset,
        "file_stem": file_stem,
        "year": year,
        "url": f"{BASE_URL}/{dataset}/{file_name}",
        "s3_key": f"{dataset}/{file_name}",
    }

def build_single_file(dataset, file_stem):
    file_name = f"{file_stem}.parquet"

    return {
        "dataset": dataset,
        "file_stem": file_stem,
        "year": None,
        "url": f"{BASE_URL}/{dataset}/{file_name}",
        "s3_key": f"{dataset}/{file_name}",
    }

def get_selected_datasets(table_arg):
    if table_arg == "all":
        return DATASETS.items()
    
    return [(table_arg, DATASETS[table_arg])]

def build_file_manifest(table_arg, years):
    files = []

    for dataset, file_stem in get_selected_datasets(table_arg):
        if dataset in SINGLE_FILE_DATASETS:
            files.append(build_single_file(dataset, file_stem))
            continue

        for year in years:
            files.append(build_year_file(dataset, file_stem, year))

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
            if response.status_code == 404:
                logger.warning(
                    "remote file not found dataset=%s year=%s status_code=%s",
                    file_info["dataset"],
                    year_label,
                    response.status_code,
                )
                return "missing"

            if response.status_code != 200:
                logger.warning(
                    "remote file unavailable dataset=%s year=%s status_code=%s",
                    file_info["dataset"],
                    year_label,
                    response.status_code,
                )
                return "failed"
            
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
        return "uploaded"
    
    except requests.RequestException:
        logger.exception(
            "download failed dataset=%s year=%s url=%s",
            file_info["dataset"],
            year_label,
            file_info["url"],
        )
        return "failed"
    
    except (BotoCoreError, ClientError, S3UploadFailedError):
        logger.exception(
            "s3 upload failed dataset=%s year=%s s3_key=%s",
            file_info["dataset"],
            year_label,
            file_info["s3_key"],
        )  
        return "failed"
    
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
        "missing": [],
        "failed": [],
    }

    for file_info in files:
        result = upload_file(s3_client, file_info)
        results[result].append(file_info)

    logger.info(
        "ingestion complete uploaded=%s missing=%s failed=%s",
        len(results["uploaded"]),
        len(results["missing"]),
        len(results["failed"]),
    )

    log_result_details("missing", results["missing"])
    log_result_details("failed", results["failed"])

    if results["failed"]:
        raise RuntimeError(f"Ingestion failed for {len(results['failed'])} file(s)")
    
    return results

def parse_args():
    parser = argparse.ArgumentParser(description="Ingest nflverse parquet files to S3")
    parser.add_argument(
        "--table",
        type=str,
        required=True,
        choices=TABLE_CHOICES,
        help="Which dataset to ingest",
    )

    return parser.parse_args()

def main():
    configure_logging()
    args = parse_args()

    current_year = datetime.now().year
    years = list(range(2000, current_year + 1))
    files = build_file_manifest(args.table, years)

    logger.info(
        "starting ingestion table=%s file_count=%s bucket=%s",
        args.table,
        len(files),
        BUCKET_NAME,
    )

    s3_client = boto3.client("s3")
    ingest_files(s3_client, files)

if __name__ == "__main__":
    main()
