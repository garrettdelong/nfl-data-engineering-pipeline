# NFL Data Engineering Pipeline

Production-style NFL analytics pipeline built with Python, AWS S3, Snowflake,
dbt, Airflow, Docker, and Terraform. The project ingests public nflverse
Parquet data, loads it into a raw warehouse layer, and transforms it into
analytics-ready dimensions, facts, and machine learning features.

## Architecture

```text
nflverse Parquet releases
        |
        v
Python ingestion
        |
        v
AWS S3 raw storage
        |
        v
Snowflake raw tables and flattened views
        |
        v
dbt staging models
        |
        v
dbt dimensions, facts, and ML features
        |
        v
Python ML training and Snowflake ML result tables
```

Airflow orchestrates ingestion, Snowflake raw loading, dbt, audit logging, and
ML training locally through Docker.

## Technology

- Python for ingestion and Snowflake loading
- AWS S3 for raw Parquet storage
- Snowflake for raw and analytics warehouse layers
- dbt for transformations, tests, and documentation
- Airflow and Docker for local orchestration
- Terraform for AWS infrastructure
- Python and scikit-learn for baseline machine learning

## Ingestion

The main ingestion entry point is `data.ingest_s3`. It expands a dataset/year
selection into an expected file manifest, checks nflverse release metadata,
and streams eligible Parquet files into:

```text
s3://nfl-pipeline-raw/
```

Supported dataset arguments:

- `pbp`
- `schedules`
- `teams`
- `stats_player`
- `weekly_rosters`
- `stats_team`
- `all`

Example commands:

```powershell
python -m data.ingest_s3 --table teams
python -m data.ingest_s3 --table pbp --start-year 2024 --end-year 2024
python -m data.ingest_s3 --table teams --sync --dry-run
python -m data.ingest_s3 --table all --sync --run-id local_sync_all_001 --manifest-output-path logs/ingestion_manifest.json
```

Sync mode uses HTTP `HEAD` metadata from the remote source and compares it to
the latest successful metadata in Snowflake. Files are classified as:

- `new`
- `updated`
- `unchanged`
- `missing`
- `failed`

Real ingestion actions are:

- `uploaded`
- `skipped_unchanged`
- `skipped_missing`
- `failed`

Dry-run actions are:

- `would_upload_new`
- `would_upload_updated`
- `would_skip_unchanged`
- `would_skip_missing`
- `would_fail`

`--dry-run` does not upload files, write Snowflake metadata, or trigger
downstream loads. Failed files produce a non-zero task result after the script
logs a complete summary.

When `--run-id` is supplied on a non-dry run, ingestion writes one row per
expected source file to:

```text
nfl_analytics.audit.ingestion_file_manifest
```

This table stores file state, ingestion action, remote metadata, previous
metadata, timing, and error details. It does not store Snowflake raw-load
status.

Ingestion summaries separate source changes from upload activity:

- `changed_file_count` counts files whose remote metadata is `new` or
  `updated`.
- `uploaded_count` counts files actually uploaded during the run, including
  forced uploads from `--replace`.
- `planned_upload_count` counts files a dry-run would upload.

The sync metadata table requires scoped Snowflake environment variables:

```text
SNOWFLAKE_INGESTION_METADATA_DATABASE
SNOWFLAKE_INGESTION_METADATA_SCHEMA
```

The shared scoped Snowflake config helper does not fall back to generic
`SNOWFLAKE_DATABASE` or `SNOWFLAKE_SCHEMA`.

## Snowflake Loading

`data/load_snowflake_raw.py` reads the ingestion manifest and loads only files
marked as Snowflake-load eligible. `data/snowflake_load.py` contains the shared
load implementation and uses key-pair authentication.

Loads are idempotent at the source-file level:

1. Delete existing raw rows for the S3 object key.
2. Copy that specific Parquet file from the Snowflake stage.
3. Use `FORCE = TRUE` and `ON_ERROR = ABORT_STATEMENT`.
4. Commit the delete and copy together or roll back on failure.

Snowflake credentials, private keys, and dbt profiles are stored outside the
repository and supplied through environment variables.

Raw loading requires scoped Snowflake variables:

```text
SNOWFLAKE_RAW_DATABASE
SNOWFLAKE_RAW_SCHEMA
SNOWFLAKE_RAW_STAGE
```

Current flattened Snowflake sources:

- `v_raw_play_by_play_flat`
- `v_raw_games_flat`
- `v_raw_teams_colors_logos_flat`
- `v_raw_stats_player_week_flat`
- `v_raw_roster_weekly_flat`
- `v_raw_stats_team_week_flat`

## dbt Warehouse

The dbt project is located at `data/nfl_data`.

Staging models:

- `stg_play_by_play`
- `stg_games`
- `stg_teams_colors_logos`
- `stg_stats_player_week`
- `stg_roster_weekly`
- `stg_stats_team_week`

Dimensions:

- `dim_franchise`
- `dim_team_code`
- `dim_game`
- `dim_date`
- `dim_player`
- `dim_player_season`

Core facts:

- `fct_play`
- `fct_game`
- `fct_drive`
- `fct_player_game`

Play subfacts:

- `fct_play_pass`
- `fct_play_rush`
- `fct_play_kick`
- `fct_play_penalty`

The model uses canonical franchise identifiers and seed-based team-code
normalization so historical abbreviations map to stable franchises.

Run the complete dbt project:

```powershell
dbt build --project-dir data\nfl_data
```

Run a specific model:

```powershell
dbt run --project-dir data\nfl_data --select fct_play
dbt test --project-dir data\nfl_data --select fct_play
```

Tests cover primary keys, composite grain, dimension relationships, subfact
filter rules, and other model-specific data contracts.

## Machine Learning

The first ML use case predicts whether an offensive play will be successful
using pre-snap context.

The tested dbt feature table is:

```text
ml_play_success_features
```

It contains one row per `game_id + play_id`, filters to eligible pass and run
plays, and creates a numeric `is_successful_play` target. Result fields such as
yards gained and touchdowns are used only to create the target and are not
included in the final feature set. `play_type` is used only for eligibility
filtering.

The Python module is scaffolded under:

```text
ml/play_success_prediction/
|-- README.md
|-- config.py
|-- train_model.py
|-- requirements.txt
|-- models/
`-- outputs/
```

The first Python training implementation reads the feature table from
Snowflake, uses a chronological season split, trains a dummy baseline and
logistic regression model, and writes metrics and predictions back to
Snowflake result tables.

Build and test the ML feature table:

```powershell
dbt run --project-dir data\nfl_data --select ml_play_success_features
dbt test --project-dir data\nfl_data --select ml_play_success_features
```

## Audit Logging

Structured audit metadata is written to Snowflake audit tables:

- `pipeline_run`
- `pipeline_task_run`
- `pipeline_file_event`
- `ingestion_file_manifest`

Airflow remains the source for detailed task logs. Snowflake stores structured
run/task/file metadata and log references, not full raw log text.

Audit writes require scoped Snowflake variables:

```text
SNOWFLAKE_AUDIT_DATABASE
SNOWFLAKE_AUDIT_SCHEMA
```

## Airflow

The local Airflow environment is under `airflow/`. The repository is mounted
inside Airflow containers at `/opt/project`.

The current DAG is `nfl_pipeline_v1`:

```text
start_pipeline_audit
  -> ingest_all
  -> choose_ingestion_path
  -> load_snowflake_raw
  -> dbt_deps
  -> dbt_run
  -> dbt_test
  -> train_play_success_model
  -> validate_ml_outputs
  -> end
```

The ingestion task runs with `--sync`, writes a manifest, and passes a
DAG-generated `run_id`. After ingestion, `choose_ingestion_path` reads the
manifest and skips the raw load, dbt, and ML tasks when no files are eligible
for Snowflake loading.

To force downstream tasks even when no new files were uploaded, trigger the DAG
with this run config:

```json
{
  "force_downstream": true
}
```

You can also set the Airflow Variable `NFL_PIPELINE_FORCE_DOWNSTREAM` to
`true`, but the DAG run config is preferred for one-off manual runs.

Start local Airflow:

```powershell
cd airflow
docker compose up --build
```

The Airflow web interface is available at `http://localhost:8080`.

## Terraform

Terraform files under `infra/` define the AWS resources and Snowflake storage
integration permissions used by the pipeline.

Review every plan before applying infrastructure changes:

```powershell
cd infra
terraform init
terraform plan
terraform apply
```

This project previously encountered unnecessary AWS networking costs, so
infrastructure changes should remain minimal and cost-aware.

## Repository Structure

```text
.
|-- airflow/                  # Local Airflow and Docker configuration
|-- data/
|   |-- ingest_s3.py         # nflverse to S3 ingestion and sync metadata
|   |-- load_snowflake_raw.py # Manifest-driven raw load entry point
|   |-- snowflake_client.py  # Shared Snowflake connection/dataframe helpers
|   |-- snowflake_load.py    # Idempotent Snowflake raw loading
|   |-- pipeline_audit.py    # Snowflake audit metadata helpers
|   `-- nfl_data/            # dbt project
|-- infra/                    # Terraform configuration
|-- ml/                       # Machine learning modules
|-- tests/                    # Python unit tests
`-- README.md
```

## Security

The repository must not contain:

- AWS credentials
- Snowflake passwords or tokens
- Snowflake private keys
- private-key passphrases
- `.env` files
- dbt `profiles.yml`
- Terraform variable files containing sensitive values

Snowflake authentication uses a private key stored outside the repository.

## Current Status

Implemented:

- nflverse ingestion into S3
- Sync mode for skipping unchanged source files
- Dry-run mode for safe ingestion previews
- Manifest handoff between S3 ingestion and Snowflake raw loading
- Structured ingestion logging and failure handling
- Idempotent Snowflake raw loading
- Snowflake flattened raw views
- dbt staging, dimensions, facts, and play subfacts
- dbt data-quality tests
- Local Airflow orchestration
- Snowflake audit run/task/file metadata
- Terraform infrastructure configuration
- Tested play-success ML feature table
- Baseline play-success model training and Snowflake result writes

Planned:

- Make large fact tables incremental
- Add CI/CD
- Add a small dashboard or analytics layer
