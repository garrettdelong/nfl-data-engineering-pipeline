# NFL dbt Project

This dbt project transforms flattened Snowflake raw NFL data into staging
models, analytics-ready dimensions and facts, play subfacts, marts, and an ML
feature table.

## Project Layout

```text
data/nfl_data/
|-- dbt_project.yml
|-- models/
|   |-- staging/
|   |-- marts/
|   `-- sources.yml
|-- seeds/
`-- tests/
```

## Raw Sources

Snowflake raw views flatten staged Parquet records before dbt reads them.
Current source views include:

- `v_raw_play_by_play_flat`
- `v_raw_games_flat`
- `v_raw_teams_colors_logos_flat`
- `v_raw_stats_player_week_flat`
- `v_raw_roster_weekly_flat`
- `v_raw_stats_team_week_flat`

## Staging Models

Current staging models include:

- `stg_play_by_play`
- `stg_games`
- `stg_teams_colors_logos`
- `stg_stats_player_week`
- `stg_roster_weekly`
- `stg_stats_team_week`

## Analytics Models

Core dimensions:

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

ML feature model:

- `ml_play_success_features`

## Modeling Conventions

- SQL keywords are uppercase.
- Identifiers are lowercase.
- dbt SQL files do not end with semicolons.
- dbt models use `ref()` and `source()` instead of hardcoded relation names.
- Prefer explicit column lists over `SELECT *`.
- Prefer numbers, strings, and dates over booleans.
- Facts define clear grain and include singular tests for composite uniqueness.

## Running dbt

From the repository root:

```powershell
dbt deps --project-dir data\nfl_data
dbt run --project-dir data\nfl_data
dbt test --project-dir data\nfl_data
dbt build --project-dir data\nfl_data
```

Run a focused model:

```powershell
dbt run --project-dir data\nfl_data --select fct_play
dbt test --project-dir data\nfl_data --select fct_play
```

Run the ML feature table:

```powershell
dbt run --project-dir data\nfl_data --select ml_play_success_features
dbt test --project-dir data\nfl_data --select ml_play_success_features
```

## Airflow Context

Inside the local Airflow containers, the repository is mounted at:

```text
/opt/project
```

Airflow dbt commands should use:

```text
/opt/project/data/nfl_data
```

not Windows host paths.

## Authentication

Snowflake/dbt uses key-pair authentication. The dbt profiles file and private
key live outside the repository and must not be committed.
