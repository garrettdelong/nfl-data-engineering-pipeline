{{ config(
    materialized = 'table'
) }}

WITH pipeline_runs AS (
  SELECT
    run_id,
    pipeline_name,
    run_status,
    started_at,
    finished_at,
    duration_seconds
  FROM {{ ref('stg_audit__pipeline_run') }}
),

file_manifest AS (
  SELECT
    run_id,
    ingestion_action,
    file_state,
    checked_at,
    uploaded_at
  FROM {{ ref('stg_audit__ingestion_file_manifest') }}
),

file_rollup AS (
  SELECT
    run_id,
    SUM(CASE WHEN ingestion_action = 'uploaded' THEN 1 ELSE 0 END) AS uploaded_file_count,
    SUM(CASE WHEN file_state = 'updated' THEN 1 ELSE 0 END) AS updated_file_count,
    SUM(CASE WHEN file_state = 'unchanged' THEN 1 ELSE 0 END) AS unchanged_file_count,
    SUM(CASE WHEN file_state = 'missing' THEN 1 ELSE 0 END) AS missing_file_count,
    SUM(CASE WHEN file_state = 'failed' THEN 1 ELSE 0 END) AS failed_file_count,
    MAX(checked_at) AS last_file_checked_at,
    MAX(uploaded_at) AS last_file_uploaded_at
  FROM file_manifest
  GROUP BY run_id
),

successful_dbt_refresh AS (
  SELECT
    run_id,
    MAX(finished_at) AS last_successful_dbt_refresh_at
  FROM {{ ref('stg_audit__pipeline_task_run') }}
  WHERE task_name IN ('dbt_build', 'dbt_test')
    AND task_status = 'succeeded'
  GROUP BY run_id
),

last_successful_source_check AS (
  SELECT
    MAX(file_rollup.last_file_checked_at) AS last_successful_source_check_at
  FROM pipeline_runs
  INNER JOIN file_rollup
    ON file_rollup.run_id = pipeline_runs.run_id
  WHERE pipeline_runs.run_status = 'succeeded'
    AND file_rollup.failed_file_count = 0
),

last_successful_pipeline_run AS (
  SELECT
    MAX(finished_at) AS last_successful_pipeline_run_at
  FROM pipeline_runs
  WHERE run_status = 'succeeded'
),

final AS (
  SELECT
    pipeline_runs.run_id,
    pipeline_runs.pipeline_name,
    pipeline_runs.run_status AS pipeline_run_status,
    pipeline_runs.started_at AS pipeline_started_at,
    pipeline_runs.finished_at AS pipeline_finished_at,
    pipeline_runs.duration_seconds AS pipeline_duration_seconds,
    COALESCE(file_rollup.uploaded_file_count, 0) AS uploaded_file_count,
    COALESCE(file_rollup.updated_file_count, 0) AS updated_file_count,
    COALESCE(file_rollup.unchanged_file_count, 0) AS unchanged_file_count,
    COALESCE(file_rollup.missing_file_count, 0) AS missing_file_count,
    COALESCE(file_rollup.failed_file_count, 0) AS failed_file_count,
    CASE
      WHEN COALESCE(file_rollup.failed_file_count, 0) > 0 OR pipeline_runs.run_status = 'failed' THEN 'failed'
      WHEN COALESCE(file_rollup.uploaded_file_count, 0) = 0 THEN 'skip_no_uploaded_files'
      WHEN file_rollup.uploaded_file_count > 0 THEN 'run_uploaded_files'
      ELSE 'unknown'
    END AS refresh_decision,
    file_rollup.last_file_checked_at,
    file_rollup.last_file_uploaded_at,
    successful_dbt_refresh.last_successful_dbt_refresh_at,
    DATEDIFF(
      hour,
      successful_dbt_refresh.last_successful_dbt_refresh_at,
      CURRENT_TIMESTAMP()
    ) AS hours_since_last_successful_dbt_refresh,
    last_successful_source_check.last_successful_source_check_at,
    DATEDIFF(
      hour,
      last_successful_source_check.last_successful_source_check_at,
      CURRENT_TIMESTAMP()
    ) AS hours_since_last_successful_source_check,
    last_successful_pipeline_run.last_successful_pipeline_run_at,
    CASE
      WHEN COALESCE(file_rollup.failed_file_count, 0) > 0 OR pipeline_runs.run_status = 'failed' THEN 'failed'
      WHEN COALESCE(file_rollup.uploaded_file_count, 0) > 0
        AND successful_dbt_refresh.last_successful_dbt_refresh_at IS NOT NULL THEN 'refreshed'
      WHEN COALESCE(file_rollup.uploaded_file_count, 0) > 0 THEN 'failed'
      WHEN COALESCE(file_rollup.uploaded_file_count, 0) = 0 THEN 'not_needed'
      ELSE 'unknown'
    END AS dbt_refresh_status,
    CASE
      WHEN COALESCE(file_rollup.failed_file_count, 0) > 0 OR pipeline_runs.run_status = 'failed' THEN 'failed'
      WHEN DATEDIFF(hour, last_successful_source_check.last_successful_source_check_at, CURRENT_TIMESTAMP()) <= 24 THEN 'fresh'
      WHEN DATEDIFF(hour, last_successful_source_check.last_successful_source_check_at, CURRENT_TIMESTAMP()) <= 48 THEN 'warning'
      ELSE 'stale'
    END AS freshness_status
  FROM pipeline_runs
  LEFT JOIN file_rollup
    ON file_rollup.run_id = pipeline_runs.run_id
  LEFT JOIN successful_dbt_refresh
    ON successful_dbt_refresh.run_id = pipeline_runs.run_id
  CROSS JOIN last_successful_source_check
  CROSS JOIN last_successful_pipeline_run
)

SELECT
  run_id,
  pipeline_name,
  pipeline_run_status,
  pipeline_started_at,
  pipeline_finished_at,
  pipeline_duration_seconds,
  uploaded_file_count,
  updated_file_count,
  unchanged_file_count,
  missing_file_count,
  failed_file_count,
  refresh_decision,
  last_file_checked_at,
  last_file_uploaded_at,
  last_successful_dbt_refresh_at,
  hours_since_last_successful_dbt_refresh,
  last_successful_source_check_at,
  hours_since_last_successful_source_check,
  last_successful_pipeline_run_at,
  dbt_refresh_status,
  freshness_status
FROM final
