"""Configuration for play success prediction."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

INPUT_CSV_PATH = PROJECT_DIR / "data" / "ml_play_success_features.csv"

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

MODELS_DIR = PROJECT_DIR / "models"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
METRICS_DIR = OUTPUTS_DIR / "metrics"
PREDICTIONS_DIR = OUTPUTS_DIR / "predictions"
FIGURES_DIR = OUTPUTS_DIR / "figures"

METRICS_PATH = METRICS_DIR / "baseline_metrics.json"
MODEL_PATH = MODELS_DIR / "logistic_regression_pipeline.joblib"
