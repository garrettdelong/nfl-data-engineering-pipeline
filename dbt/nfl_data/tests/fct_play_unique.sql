SELECT
  fct_play.game_id,
  fct_play.play_id,
  COUNT(*) AS row_count
FROM {{ ref('fct_play') }} AS fct_play
GROUP BY
  fct_play.game_id,
  fct_play.play_id
HAVING COUNT(*) > 1
