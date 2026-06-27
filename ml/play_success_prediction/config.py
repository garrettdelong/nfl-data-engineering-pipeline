"""Configuration for play success prediction."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]

FEATURE_TABLE = "ml_play_success_features"
FEATURE_DATABASE = "nfl_analytics"
FEATURE_SCHEMA = "dbt_gdelong_marts"
RESULT_DATABASE = "nfl_analytics"
RESULT_SCHEMA = "ml_results"
METRICS_TABLE = "ml_play_success_model_metrics"
PREDICTIONS_TABLE = "ml_play_success_predictions"

TARGET_COLUMN = "is_successful_play"

ID_COLUMNS = [
    "game_id",
    "play_id",
]

NON_FEATURE_COLUMNS = [
    "game_id",
    "play_id",
    "play_type",
    "is_successful_play",
]

NUMERIC_FEATURES = [
    "season",
    "nfl_week",
    "qtr",
    "down",
    "ydstogo",
    "yardline_100",
    "drive",
    "game_seconds_remaining",
    "half_seconds_remaining",
    "score_differential",
    "goal_to_go",
    "shotgun",
    "no_huddle",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
    "temperature",
    "wind",
]

CATEGORICAL_FEATURES = [
    "offense_franchise_id",
    "defense_franchise_id",
    "offense_home_away",
    "roof",
    "surface",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
