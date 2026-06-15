SELECT
  fct_play_penalty.game_id,
  fct_play_penalty.play_id,
  COUNT(*) AS row_count
FROM {{ ref('fct_play_penalty') }} AS fct_play_penalty
GROUP BY
  fct_play_penalty.game_id,
  fct_play_penalty.play_id
HAVING COUNT(*) > 1
