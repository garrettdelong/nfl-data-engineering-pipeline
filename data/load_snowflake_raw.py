import argparse
import json
import logging
from pathlib import Path

from data.cli_args import (
    add_log_level_argument,
    add_manifest_input_argument,
    add_run_id_argument,
)
from data.ingest_s3 import DATASETS
from data.logging_config import configure_logging
from data.snowflake_load import load_uploaded_files


logger = logging.getLogger(__name__)


def read_manifest(manifest_path):
    path = Path(manifest_path)

    with path.open("r", encoding="utf-8") as manifest_file:
        manifest_records = json.load(manifest_file)

    logger.info(
        "read ingestion manifest path=%s file_count=%s",
        path,
        len(manifest_records),
    )

    return manifest_records


def build_snowflake_file_info(manifest_record):
    dataset = manifest_record["dataset"]
    dataset_config = DATASETS[dataset]

    return {
        "dataset": dataset,
        "year": manifest_record["source_year"],
        "s3_key": manifest_record["s3_key"],
        "raw_table": dataset_config["raw_table"],
    }


def get_snowflake_eligible_files(manifest_records):
    eligible_records = [
        record
        for record in manifest_records
        if record.get("snowflake_load_eligible")
    ]

    logger.info(
        "filtered snowflake eligible files eligible=%s total=%s",
        len(eligible_records),
        len(manifest_records),
    )

    return [
        build_snowflake_file_info(record)
        for record in eligible_records
    ]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Load Snowflake raw tables from an ingestion manifest",
    )
    add_log_level_argument(parser)
    add_run_id_argument(parser)
    add_manifest_input_argument(parser)

    return parser.parse_args(argv)


def main(args=None):
    if args is None:
        args = parse_args()

    manifest_records = read_manifest(args.manifest_path)
    eligible_files = get_snowflake_eligible_files(manifest_records)
    load_uploaded_files(eligible_files, run_id=args.run_id)


if __name__ == "__main__":
    parsed_args = parse_args()
    configure_logging(parsed_args.log_level)
    main(parsed_args)
