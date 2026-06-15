SELECT
  fct_play_rush.game_id,
  fct_play_rush.play_id,
  COUNT(*) AS row_count
FROM {{ ref('fct_play_rush') }} AS fct_play_rush
GROUP BY
  fct_play_rush.game_id,
  fct_play_rush.play_id
HAVING COUNT(*) > 1
