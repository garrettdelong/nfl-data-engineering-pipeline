{{ config(
    materialized = 'view'
) }}

SELECT
  run_id,
  pipeline_name,
  run_type,
  table_arg,
  dataset,
  file_stem,
  source_year,
  source_url,
  s3_bucket,
  s3_key,
  http_status_code,
  remote_etag,
  remote_last_modified,
  remote_content_length,
  previous_remote_etag,
  previous_remote_last_modified,
  previous_remote_content_length,
  file_state,
  ingestion_action,
  checked_at,
  uploaded_at,
  started_at,
  finished_at,
  duration_seconds,
  error_message,
  created_at
FROM {{ source('audit', 'ingestion_file_manifest') }}
