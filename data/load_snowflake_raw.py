import argparse
import json
import logging
from pathlib import Path

from ingest_s3 import DATASETS
from snowflake_load import load_uploaded_files


logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s - %(message)s",
    )


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load Snowflake raw tables from an ingestion manifest",
    )
    parser.add_argument(
        "--manifest-path",
        required=True,
        help="Path to ingestion manifest JSON created by ingest_s3.py",
    )

    return parser.parse_args()


def main():
    configure_logging()
    args = parse_args()

    manifest_records = read_manifest(args.manifest_path)
    eligible_files = get_snowflake_eligible_files(manifest_records)
    load_uploaded_files(eligible_files)


if __name__ == "__main__":
    main()
