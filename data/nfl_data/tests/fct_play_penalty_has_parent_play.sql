SELECT
  fct_play_penalty.game_id,
  fct_play_penalty.play_id
FROM {{ ref('fct_play_penalty') }} AS fct_play_penalty
LEFT JOIN {{ ref('fct_play') }} AS fct_play
  ON fct_play.game_id = fct_play_penalty.game_id
  AND fct_play.play_id = fct_play_penalty.play_id
WHERE fct_play.game_id IS NULL
