SELECT
  fct_play_rush.game_id,
  fct_play_rush.play_id
FROM {{ ref('fct_play_rush') }} AS fct_play_rush
LEFT JOIN {{ ref('fct_play') }} AS fct_play
  ON fct_play.game_id = fct_play_rush.game_id
  AND fct_play.play_id = fct_play_rush.play_id
WHERE fct_play.game_id IS NULL
