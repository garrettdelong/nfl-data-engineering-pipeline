SELECT
  dim_player_season.player_id,
  dim_player_season.season,
  COUNT(*) AS row_count
FROM {{ ref('dim_player_season') }} AS dim_player_season
GROUP BY
  dim_player_season.player_id,
  dim_player_season.season
HAVING COUNT(*) > 1
