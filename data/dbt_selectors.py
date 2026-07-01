import argparse
import logging

from data.cli_args import add_log_level_argument, add_run_id_argument, parse_truthy
from data.logging_config import configure_logging
from data.snowflake_client import (
    connect_snowflake,
    get_scoped_snowflake_config_from_env,
    qualified_table_name,
)


logger = logging.getLogger(__name__)

INGESTION_METADATA_TABLE = "ingestion_file_manifest"

DATASET_DBT_SELECTORS = {
    "pbp": "stg_play_by_play+",
    "schedules": "stg_games+",
    "teams": "stg_teams_colors_logos+",
    "weekly_rosters": "stg_roster_weekly+",
    "stats_player": "stg_stats_player_week+",
    "stats_team": "stg_stats_team_week+",
}


def get_metadata_table_name(config):
    return qualified_table_name(
        INGESTION_METADATA_TABLE,
        database=config.get("database"),
        schema=config.get("schema"),
    )


def get_uploaded_datasets(run_id, config=None):
    snowflake_config = config or get_scoped_snowflake_config_from_env(
        "INGESTION_METADATA"
    )
    table_name = get_metadata_table_name(snowflake_config)
    connection = connect_snowflake(snowflake_config)

    query = f"""
SELECT DISTINCT
    dataset
FROM {table_name}
WHERE run_id = %s
    AND ingestion_action = 'uploaded'
ORDER BY dataset
""".strip()

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (run_id,))
            rows = cursor.fetchall()
    finally:
        connection.close()

    return [row[0] for row in rows]


def build_dbt_selectors(uploaded_datasets, dataset_selector_map=None):
    dataset_selector_map = dataset_selector_map or DATASET_DBT_SELECTORS
    selectors = []
    seen_selectors = set()

    for dataset in uploaded_datasets:
        selector = dataset_selector_map.get(dataset)
        if not selector:
            logger.warning("no dbt selector configured for uploaded dataset=%s", dataset)
            continue

        if selector in seen_selectors:
            continue

        selectors.append(selector)
        seen_selectors.add(selector)

    return selectors


def build_dbt_selector_args(selectors):
    if not selectors:
        return ""

    return "--select " + " ".join(selectors)


def get_dbt_selector_args(run_id, force_downstream=False, config=None):
    uploaded_datasets = get_uploaded_datasets(run_id, config=config)
    selectors = build_dbt_selectors(uploaded_datasets)

    logger.info(
        "uploaded datasets for dbt selection run_id=%s datasets=%s",
        run_id,
        uploaded_datasets,
    )
    logger.info("dbt selectors=%s force_downstream=%s", selectors, force_downstream)

    if not uploaded_datasets and force_downstream:
        logger.info("no uploaded datasets found; using default dbt build because force is enabled")
        return ""

    return build_dbt_selector_args(selectors)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build dbt selector arguments from ingestion metadata",
    )
    add_log_level_argument(parser)
    add_run_id_argument(parser, required=True)
    parser.add_argument(
        "--force-downstream",
        default="false",
        help="Run default dbt build when no uploaded datasets exist",
    )

    return parser.parse_args(argv)


def main(args=None):
    if args is None:
        args = parse_args()

    selector_args = get_dbt_selector_args(
        run_id=args.run_id,
        force_downstream=parse_truthy(args.force_downstream),
    )
    print(selector_args)


if __name__ == "__main__":
    parsed_args = parse_args()
    configure_logging(parsed_args.log_level)
    main(parsed_args)
