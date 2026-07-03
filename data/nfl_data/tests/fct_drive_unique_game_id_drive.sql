SELECT
  fct_drive.game_id,
  fct_drive.drive,
  COUNT(*) AS row_count
FROM {{ ref('fct_drive') }} AS fct_drive
GROUP BY
  fct_drive.game_id,
  fct_drive.drive
HAVING COUNT(*) > 1
