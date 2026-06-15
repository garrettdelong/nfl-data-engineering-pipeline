SELECT
  fct_play_penalty.game_id,
  fct_play_penalty.play_id,
  fct_play_penalty.drive,
  fct_play_penalty.two_point_attempt,
  fct_play_penalty.penalty,
  fct_play_penalty.penalty_team,
  fct_play_penalty.penalty_player_id,
  fct_play_penalty.penalty_yards,
  fct_play_penalty.penalty_type
FROM {{ ref('fct_play_penalty') }} AS fct_play_penalty
WHERE fct_play_penalty.drive IS NULL
  OR COALESCE(fct_play_penalty.two_point_attempt, 0) != 0
  OR (
    COALESCE(fct_play_penalty.penalty, 0) = 0
    AND fct_play_penalty.penalty_team IS NULL
    AND fct_play_penalty.penalty_player_id IS NULL
    AND fct_play_penalty.penalty_yards IS NULL
    AND fct_play_penalty.penalty_type IS NULL
  )
