
WITH plays AS (
  SELECT
    fct_play.game_id,
    fct_play.drive,
    stg_pbp.drive_play_count,
    fct_play.offense_franchise_id,
    stg_pbp.ydsnet
    fct_play.epa,
    fct_play.success,
    stg_pbp.drive_inside20,
    stg_pbp.drive_ended_with_score
  FROM {{ ref('fct_play') }} AS fct_play
    INNER JOIN {{ ref('stg_pbp') }} AS stg_pbp
      ON stg_pbp.game_id = fct_play.game_id
      AND stg_pbp.play_id = fct_play.play_id
    WHERE fct_play.drive IS NOT NULL
    AND fct_play.play_type != 'no_play'
),

drive_agg AS (
  SELECT
    plays.game_id,
    plays.drive,
    plays.offense_franchise_id,
    plays.drive_play_count,
    plays.ydsnet,
    plays.drive_inside20,
    plays.drive_ended_with_score,
    SUM(plays.epa) AS epa_sum,
    AVG(plays.success) AS success_rate,
  FROM plays
  GROUP BY
    plays.game_id,
    plays.drive
)

SELECT
  drive_agg.game_id,
  drive_agg.drive,
  drive_agg.offense_franchise_id,
  drive_agg.drive_play_count,
  drive_agg.ydsnet AS yards_gained_sum,
  drive_agg.epa_sum,
  drive_agg.success_rate,
  drive_agg.drive_inside20,
  drive_agg.drive_ended_with_score
FROM drive_agg
