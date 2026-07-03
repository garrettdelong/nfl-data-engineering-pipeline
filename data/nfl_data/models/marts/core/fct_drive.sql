{{ config(
    materialized = 'incremental',
    unique_key = 'drive_key',
    incremental_strategy = 'merge',
    on_schema_change = 'sync_all_columns'
) }}

WITH plays AS (
  SELECT
    fct_play.game_id,
    fct_play.drive,
    stg_pbp.drive_play_count,
    fct_play.offense_franchise_id,
    stg_pbp.ydsnet,
    fct_play.epa,
    fct_play.success,
    stg_pbp.drive_inside20,
    stg_pbp.drive_ended_with_score,
    fct_play.loaded_at
  FROM {{ ref('fct_play') }} AS fct_play
    INNER JOIN {{ ref('stg_play_by_play') }} AS stg_pbp
      ON stg_pbp.game_id = fct_play.game_id
      AND stg_pbp.play_id = fct_play.play_id
    WHERE fct_play.drive IS NOT NULL
    AND fct_play.play_type != 'no_play'
    {% if is_incremental() %}
    AND fct_play.loaded_at >= DATEADD(
      DAY,
      -{{ var('incremental_lookback_days', 3) }},
      COALESCE(
        (
          SELECT MAX(loaded_at)
          FROM {{ this }}
        ),
        CAST('1900-01-01' AS TIMESTAMP)
      )
    )
    {% endif %}
),

drive_agg AS (
  SELECT
    game_id,
    drive,
    MAX(offense_franchise_id) AS offense_franchise_id,
    MAX(drive_play_count) AS drive_play_count,
    MAX(ydsnet) AS yards_gained_sum,
    MAX(drive_inside20) AS drive_inside20,
    MAX(drive_ended_with_score) AS drive_ended_with_score,
    SUM(epa) AS epa_sum,
    AVG(success) AS success_rate,
    MAX(loaded_at) AS loaded_at
    FROM plays
    GROUP BY
      game_id,
      drive
)

SELECT
  drive_agg.game_id || '-' || drive_agg.drive AS drive_key,
  drive_agg.game_id,
  drive_agg.drive,
  drive_agg.offense_franchise_id,
  drive_agg.drive_play_count,
  drive_agg.yards_gained_sum,
  drive_agg.epa_sum,
  drive_agg.success_rate,
  drive_agg.drive_inside20,
  drive_agg.drive_ended_with_score,
  drive_agg.loaded_at
FROM drive_agg
