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
),

roster_players AS (
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
),

pbp_players AS (
  SELECT DISTINCT player_id
  FROM (
    SELECT passer_player_id AS player_id FROM {{ ref('fct_play') }}
    UNION ALL
    SELECT rusher_player_id AS player_id FROM {{ ref('fct_play') }}
    UNION ALL
    SELECT receiver_player_id AS player_id FROM {{ ref('fct_play') }}
  ) x
  WHERE player_id IS NOT NULL
),

missing_players AS (
  SELECT
    pbp_players.player_id,
    NULL AS first_name,
    NULL AS last_name,
    NULL AS full_name,
    NULL AS birth_date,
    NULL AS height,
    NULL AS espn_id,
    NULL AS pfr_id,
    NULL AS entry_year,
    NULL AS rookie_year,
    NULL AS draft_club,
    NULL AS draft_number
  FROM pbp_players 
  LEFT JOIN roster_players 
    ON pbp_players.player_id = roster_players.player_id
  WHERE roster_players.player_id IS NULL
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
FROM roster_players

  UNION ALL

SELECT  
  pbp_players.player_id,
    NULL AS first_name,
    NULL AS last_name,
    NULL AS full_name,
    NULL AS birth_date,
    NULL AS height,
    NULL AS espn_id,
    NULL AS pfr_id,
    NULL AS entry_year,
    NULL AS rookie_year,
    NULL AS draft_club,
    NULL AS draft_number 
FROM missing_players
