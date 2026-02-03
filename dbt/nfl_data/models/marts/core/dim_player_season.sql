WITH base AS (
  SELECT
    gsis_id AS player_id,
    season,
    week,
    team AS team_code,
    player_position,
    jersey_number,
    years_exp,
    weight
  FROM {{ ref('stg_weekly_rosters') }}
  WHERE gsis_id IS NOT NULL
    AND season IS NOT NULL
    AND week IS NOT NULL
),

-- canonicalize team codes (so STL/SL/LA etc. collapse correctly)
mapped AS (
  SELECT
    base.player_id,
    base.season,
    base.week,
    dim_team_code.team_code,
    dim_team_code.franchise_id,
    base.player_position,
    base.jersey_number,
    base.years_exp,
    base.weight
  FROM base
  LEFT JOIN {{ ref('dim_team_code') }} AS dim_team_code
    ON dim_team_code.source_team_code = base.team_code
),

-- count weeks per team per season
team_counts AS (
  SELECT
    mapped.player_id,
    mapped.season,
    mapped.team_code,
    COUNT(DISTINCT mapped.week) AS weeks_on_team,
    MAX(mapped.week) AS last_week_on_team
  FROM mapped
  WHERE mapped.team_code IS NOT NULL
  GROUP BY
    mapped.player_id,
    mapped.season,
    mapped.team_code
),

primary_team AS (
    SELECT
        team_counts.player_id,
        team_counts.season,
        team_counts.team_code,
        team_counts.weeks_on_team,
        team_counts.last_week_on_team,
        ROW_NUMBER() OVER (
        PARTITION BY team_counts.player_id, team_counts.season
        ORDER BY
            team_counts.weeks_on_team DESC,
            team_counts.last_week_on_team DESC,
            team_counts.team_code ASC  -- deterministic tiebreaker
        ) AS rn
    FROM team_counts
),

latest_record AS (
  SELECT
    mapped.player_id,
    mapped.season,
    mapped.week,
    mapped.team_code,
    mapped.player_position,
    mapped.jersey_number,
    mapped.years_exp,
    mapped.weight,
    ROW_NUMBER() OVER (
      PARTITION BY mapped.player_id, mapped.season
      ORDER BY mapped.week DESC
    ) AS rn
  FROM mapped
),

latest_player_season AS (
  SELECT
    latest_record.player_id,
    latest_record.season,
    latest_record.week,
    latest_record.team_code,
    latest_record.player_position,
    latest_record.jersey_number,
    latest_record.years_exp,
    latest_record.weight
  FROM latest_record
  WHERE latest_record.rn = 1
)

SELECT
  latest_player_season.player_id,
  latest_player_season.season,
  primary_team.team_code,
  latest_player_season.player_position,
  latest_player_season.jersey_number,
  latest_player_season.years_exp,
  latest_player_season.weight
FROM latest_player_season
LEFT JOIN primary_team
  ON primary_team.player_id = latest_player_season.player_id
 AND primary_team.season = latest_player_season.season
WHERE primary_team.rn = 1
