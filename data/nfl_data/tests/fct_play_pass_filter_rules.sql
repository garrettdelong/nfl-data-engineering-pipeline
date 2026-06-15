SELECT
  fct_play_pass.game_id,
  fct_play_pass.play_id,
  fct_play_pass.play_type,
  fct_play_pass.drive,
  fct_play_pass.two_point_attempt,
  fct_play_pass.qb_spike,
  fct_play_pass.qb_kneel,
  fct_play_pass.pass_attempt,
  fct_play_pass.sack,
  fct_play_pass.qb_scramble
FROM {{ ref('fct_play_pass') }} AS fct_play_pass
WHERE fct_play_pass.drive IS NULL
  OR LOWER(fct_play_pass.play_type) = 'no_play'
  OR COALESCE(fct_play_pass.two_point_attempt, 0) != 0
  OR COALESCE(fct_play_pass.qb_spike, 0) != 0
  OR COALESCE(fct_play_pass.qb_kneel, 0) != 0
  OR (
    COALESCE(fct_play_pass.pass_attempt, 0) = 0
    AND COALESCE(fct_play_pass.sack, 0) = 0
    AND COALESCE(fct_play_pass.qb_scramble, 0) = 0
  )
