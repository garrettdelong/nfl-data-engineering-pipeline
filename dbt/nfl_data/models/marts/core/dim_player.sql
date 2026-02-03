WITH ranked AS (
  SELECT
    gsis_id AS player_id,
    full_name,
    first_name,
    last_name,
    birth_date,
    height,
    espn_id,
    pfr_id,
    entry_year,
    rookie_year,
    draft_club,
    draft_number,
    ROW_NUMBER() OVER (
      PARTITION BY gsis_id
      ORDER BY season DESC, week DESC
    ) AS rn
  FROM {{ ref('stg_weekly_rosters') }}
  WHERE gsis_id IS NOT NULL
)

SELECT
  player_id,
  full_name,
  first_name,
  last_name,
  birth_date,
  height,
  espn_id,
  pfr_id,
  entry_year,
  rookie_year,
  draft_club,
  draft_number
FROM ranked
WHERE rn = 1
