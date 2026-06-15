SELECT
  fct_play_kick.game_id,
  fct_play_kick.play_id
FROM {{ ref('fct_play_kick') }} AS fct_play_kick
LEFT JOIN {{ ref('fct_play') }} AS fct_play
  ON fct_play.game_id = fct_play_kick.game_id
  AND fct_play.play_id = fct_play_kick.play_id
WHERE fct_play.game_id IS NULL
