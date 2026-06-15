SELECT
  fct_play_kick.game_id,
  fct_play_kick.play_id,
  COUNT(*) AS row_count
FROM {{ ref('fct_play_kick') }} AS fct_play_kick
GROUP BY
  fct_play_kick.game_id,
  fct_play_kick.play_id
HAVING COUNT(*) > 1
