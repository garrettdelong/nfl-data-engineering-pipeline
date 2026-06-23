SELECT
  game_id,
  play_id,
  COUNT(*) AS row_count
FROM {{ ref('ml_play_success_features') }}
GROUP BY
  game_id,
  play_id
HAVING COUNT(*) > 1
