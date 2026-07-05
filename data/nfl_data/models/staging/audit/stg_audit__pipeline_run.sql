{{ config(
    materialized = 'view'
) }}

SELECT
  run_id,
  pipeline_name,
  dag_id,
  airflow_run_id,
  run_status,
  started_at,
  finished_at,
  duration_seconds,
  triggered_by,
  environment_name,
  git_commit_sha,
  error_message,
  created_at,
  updated_at
FROM {{ source('audit', 'pipeline_run') }}
