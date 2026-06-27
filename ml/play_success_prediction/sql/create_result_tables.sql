CREATE TABLE IF NOT EXISTS nfl_analytics.ml_results.ml_play_success_model_metrics (
    run_id STRING,
    model_name STRING,
    split_name STRING,
    metric_name STRING,
    metric_value FLOAT,
    metric_text STRING,
    created_at TIMESTAMP_NTZ
);

CREATE TABLE IF NOT EXISTS nfl_analytics.ml_results.ml_play_success_predictions (
    run_id STRING,
    model_name STRING,
    split_name STRING,
    game_id STRING,
    play_id NUMBER,
    season NUMBER,
    actual_is_successful_play NUMBER,
    predicted_is_successful_play NUMBER,
    predicted_success_probability FLOAT,
    created_at TIMESTAMP_NTZ
);
