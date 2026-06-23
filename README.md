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
```

Airflow orchestrates ingestion and dbt locally through Docker.

## Technology

- Python for ingestion and Snowflake loading
- AWS S3 for raw Parquet storage
- Snowflake for raw and analytics warehouse layers
- dbt for transformations, tests, and documentation
- Airflow and Docker for local orchestration
- Terraform for AWS infrastructure
- Python and scikit-learn planned for baseline machine learning

## Ingestion

The main ingestion entry point is `data/ingest_s3.py`. It downloads nflverse
release files and streams them into:

```text
s3://nfl-pipeline-raw/
```

Supported dataset arguments:

- `pbp`
- `schedules`
- `teams`
- `player_stats`
- `weekly_rosters`
- `stats_team`
- `all`

Example commands:

```powershell
python data/ingest_s3.py --table teams
python data/ingest_s3.py --table pbp --start-year 2024 --end-year 2024
python data/ingest_s3.py --table pbp --start-year 2024 --end-year 2024 --load-snowflake
```

The script builds a manifest, records uploaded, missing, and failed files, and
uses structured logging suitable for Airflow task logs. Missing remote files
do not fail ingestion, but request, S3, and Snowflake failures produce a
non-zero task result.

## Snowflake Loading

`data/snowflake_load.py` loads successfully uploaded files into Snowflake raw
tables using key-pair authentication.

Loads are idempotent at the source-file level:

1. Delete existing raw rows for the S3 object key.
2. Copy that specific Parquet file from the Snowflake stage.
3. Use `FORCE = TRUE` and `ON_ERROR = ABORT_STATEMENT`.
4. Commit the delete and copy together or roll back on failure.

Snowflake credentials, private keys, and dbt profiles are stored outside the
repository and supplied through environment variables.

Current flattened Snowflake sources:

- `v_raw_play_by_play_flat`
- `v_raw_games_flat`
- `v_raw_teams_colors_logos_flat`
- `v_raw_player_stats_flat`
- `v_raw_roster_weekly_flat`
- `v_raw_stats_team_week_flat`

## dbt Warehouse

The dbt project is located at `data/nfl_data`.

Staging models:

- `stg_play_by_play`
- `stg_games`
- `stg_teams_colors_logos`
- `stg_player_stats`
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

Model training and evaluation are not implemented yet. The planned first
version uses a chronological season split, a dummy baseline, and logistic
regression with standard classification metrics.

Build and test the ML feature table:

```powershell
dbt run --project-dir data\nfl_data --select ml_play_success_features
dbt test --project-dir data\nfl_data --select ml_play_success_features
```

## Airflow

The local Airflow environment is under `airflow/`. The repository is mounted
inside Airflow containers at `/opt/project`.

The current DAG is `nfl_pipeline_v1`:

```text
ingest_all -> dbt_deps -> dbt_run -> dbt_test
```

The ingestion task currently runs without `--load-snowflake`. The Python
ingestion command supports automated Snowflake loading, but that flag still
needs to be integrated into the DAG before the Airflow workflow controls the
complete S3-to-Snowflake path.

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
|   |-- ingest_s3.py         # nflverse to S3 ingestion
|   |-- snowflake_load.py    # Idempotent Snowflake raw loading
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
- Structured ingestion logging and failure handling
- Optional idempotent Snowflake raw loading
- Snowflake flattened raw views
- dbt staging, dimensions, facts, and play subfacts
- dbt data-quality tests
- Local Airflow orchestration
- Terraform infrastructure configuration
- Tested play-success ML feature table

Planned:

- Integrate Snowflake loading into the Airflow DAG
- Improve ingestion synchronization so unchanged files can be skipped
- Make large fact tables incremental
- Add CI/CD
- Implement and evaluate the baseline play-success model
- Add a small dashboard or analytics layer
