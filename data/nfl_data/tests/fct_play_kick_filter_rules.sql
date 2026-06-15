SELECT
  fct_play_kick.game_id,
  fct_play_kick.play_id,
  fct_play_kick.play_type,
  fct_play_kick.drive,
  fct_play_kick.two_point_attempt,
  fct_play_kick.punt_attempt,
  fct_play_kick.kickoff_attempt,
  fct_play_kick.field_goal_attempt,
  fct_play_kick.extra_point_attempt
FROM {{ ref('fct_play_kick') }} AS fct_play_kick
WHERE fct_play_kick.drive IS NULL
  OR LOWER(fct_play_kick.play_type) = 'no_play'
  OR COALESCE(fct_play_kick.two_point_attempt, 0) != 0
  OR (
    COALESCE(fct_play_kick.punt_attempt, 0) = 0
    AND COALESCE(fct_play_kick.kickoff_attempt, 0) = 0
    AND COALESCE(fct_play_kick.field_goal_attempt, 0) = 0
    AND COALESCE(fct_play_kick.extra_point_attempt, 0) = 0
  )
