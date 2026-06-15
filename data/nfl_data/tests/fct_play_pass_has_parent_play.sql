SELECT
  fct_play_pass.game_id,
  fct_play_pass.play_id
FROM {{ ref('fct_play_pass') }} AS fct_play_pass
LEFT JOIN {{ ref('fct_play') }} AS fct_play
  ON fct_play.game_id = fct_play_pass.game_id
  AND fct_play.play_id = fct_play_pass.play_id
WHERE fct_play.game_id IS NULL
