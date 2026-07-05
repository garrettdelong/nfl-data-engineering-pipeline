SELECT
  fct_play_rush.game_id,
  fct_play_rush.play_id,
  fct_play_rush.play_type,
  fct_play_rush.drive,
  fct_play_rush.two_point_attempt,
  fct_play_rush.qb_kneel,
  fct_play_rush.sack,
  fct_play_rush.rush_attempt,
  fct_play_rush.qb_scramble,
  fct_play_rush.special_flag
FROM {{ ref('fct_play_rush') }} AS fct_play_rush
WHERE fct_play_rush.drive IS NULL
  OR LOWER(fct_play_rush.play_type) = 'no_play'
  OR COALESCE(fct_play_rush.two_point_attempt, 0) != 0
  OR COALESCE(fct_play_rush.qb_kneel, 0) != 0
  OR COALESCE(fct_play_rush.sack, 0) != 0
  OR COALESCE(fct_play_rush.special_flag, 0) != 0
  OR LOWER(fct_play_rush.play_type) IN ('field_goal', 'extra_point', 'kickoff', 'punt')
  OR (
    COALESCE(fct_play_rush.rush_attempt, 0) = 0
    AND COALESCE(fct_play_rush.qb_scramble, 0) = 0
  )
