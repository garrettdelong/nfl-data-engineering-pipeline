SELECT
  fct_drive.drive_key,
  COUNT(*) AS row_count
FROM {{ ref('fct_drive') }} AS fct_drive
GROUP BY
  fct_drive.drive_key
HAVING COUNT(*) > 1
