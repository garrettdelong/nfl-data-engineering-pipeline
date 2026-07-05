{{ config(
    materialized = 'view'
) }}

SELECT
  run_id,
  task_name,
  task_status,
  attempt_number,
  started_at,
  finished_at,
  duration_seconds,
  input_record_count,
  output_record_count,
  error_message,
  log_reference,
  created_at,
  updated_at
FROM {{ source('audit', 'pipeline_task_run') }}
