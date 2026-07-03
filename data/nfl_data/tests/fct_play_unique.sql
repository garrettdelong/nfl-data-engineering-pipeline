SELECT
  fct_play.play_key,
  COUNT(*) AS row_count
FROM {{ ref('fct_play') }} AS fct_play
GROUP BY
  fct_play.play_key
HAVING COUNT(*) > 1
