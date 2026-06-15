SELECT
  fct_play_pass.game_id,
  fct_play_pass.play_id,
  COUNT(*) AS row_count
FROM {{ ref('fct_play_pass') }} AS fct_play_pass
GROUP BY
  fct_play_pass.game_id,
  fct_play_pass.play_id
HAVING COUNT(*) > 1
