CREATE SCHEMA IF NOT EXISTS nfl_analytics.audit;

CREATE TABLE IF NOT EXISTS nfl_analytics.audit.pipeline_run (
    run_id STRING NOT NULL,
    pipeline_name STRING,
    dag_id STRING,
    airflow_run_id STRING,
    run_status STRING,
    started_at TIMESTAMP_NTZ,
    finished_at TIMESTAMP_NTZ,
    duration_seconds NUMBER,
    triggered_by STRING,
    environment_name STRING,
    git_commit_sha STRING,
    error_message STRING,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS nfl_analytics.audit.pipeline_task_run (
    run_id STRING NOT NULL,
    task_name STRING NOT NULL,
    task_status STRING,
    attempt_number NUMBER NOT NULL,
    started_at TIMESTAMP_NTZ,
    finished_at TIMESTAMP_NTZ,
    duration_seconds NUMBER,
    input_record_count NUMBER,
    output_record_count NUMBER,
    error_message STRING,
    log_reference STRING,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS nfl_analytics.audit.pipeline_file_event (
    run_id STRING NOT NULL,
    dataset_name STRING,
    source_year NUMBER,
    source_url STRING,
    s3_bucket STRING,
    s3_key STRING NOT NULL,
    upload_status STRING,
    snowflake_load_status STRING,
    snowflake_table_name STRING,
    rows_loaded NUMBER,
    started_at TIMESTAMP_NTZ,
    finished_at TIMESTAMP_NTZ,
    duration_seconds NUMBER,
    error_message STRING,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
