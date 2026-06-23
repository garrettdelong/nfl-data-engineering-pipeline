WITH play_base AS (
  SELECT
    fct_play.game_id,
    fct_play.play_id,
    fct_play.season,
    fct_play.nfl_week,
    fct_play.qtr,
    fct_play.down,
    fct_play.ydstogo,
    fct_play.yardline_100,
    fct_play.play_type,
    fct_play.drive,
    fct_play.offense_franchise_id,
    fct_play.defense_franchise_id,
    fct_play.yards_gained,
    fct_play.touchdown,
    stg_play_by_play.game_seconds_remaining,
    stg_play_by_play.half_seconds_remaining,
    stg_play_by_play.score_differential,
    stg_play_by_play.goal_to_go,
    stg_play_by_play.shotgun,
    stg_play_by_play.no_huddle,
    stg_play_by_play.posteam_timeouts_remaining,
    stg_play_by_play.defteam_timeouts_remaining,
    stg_play_by_play.posteam,
    stg_play_by_play.home_team,
    stg_play_by_play.away_team,
    stg_play_by_play.two_point_attempt,
    stg_play_by_play.qb_kneel,
    stg_play_by_play.qb_spike,
    stg_play_by_play.penalty,
    stg_play_by_play.aborted_play,
    dim_game.roof,
    dim_game.surface,
    dim_game.temperature,
    dim_game.wind
  FROM {{ ref('fct_play') }} AS fct_play
  INNER JOIN {{ ref('stg_play_by_play') }} AS stg_play_by_play
    ON stg_play_by_play.game_id = fct_play.game_id
    AND stg_play_by_play.play_id = fct_play.play_id
  INNER JOIN {{ ref('dim_game') }} AS dim_game
    ON dim_game.game_id = fct_play.game_id
),

eligible_plays AS (
  SELECT
    game_id,
    play_id,
    season,
    nfl_week,
    qtr,
    down,
    ydstogo,
    yardline_100,
    drive,
    offense_franchise_id,
    defense_franchise_id,
    yards_gained,
    touchdown,
    game_seconds_remaining,
    half_seconds_remaining,
    score_differential,
    goal_to_go,
    shotgun,
    no_huddle,
    posteam_timeouts_remaining,
    defteam_timeouts_remaining,
    posteam,
    home_team,
    away_team,
    roof,
    surface,
    temperature,
    wind
  FROM play_base
  WHERE down BETWEEN 1 AND 4
    AND ydstogo IS NOT NULL
    AND yardline_100 IS NOT NULL
    AND yards_gained IS NOT NULL
    AND drive IS NOT NULL
    AND LOWER(play_type) IN ('pass', 'run')
    AND COALESCE(two_point_attempt, 0) = 0
    AND COALESCE(qb_kneel, 0) = 0
    AND COALESCE(qb_spike, 0) = 0
    AND COALESCE(penalty, 0) = 0
    AND COALESCE(aborted_play, 0) = 0
),

final AS (
  SELECT
    game_id,
    play_id,
    season,
    nfl_week,
    qtr,
    down,
    ydstogo,
    yardline_100,
    drive,
    offense_franchise_id,
    defense_franchise_id,
    game_seconds_remaining,
    half_seconds_remaining,
    score_differential,
    goal_to_go,
    shotgun,
    no_huddle,
    posteam_timeouts_remaining,
    defteam_timeouts_remaining,
    CASE
      WHEN posteam = home_team THEN 'home'
      WHEN posteam = away_team THEN 'away'
      ELSE 'unknown'
    END AS offense_home_away,
    roof,
    surface,
    temperature,
    wind,
    CASE
      WHEN touchdown = 1 THEN 1
      WHEN down = 1 AND yards_gained >= 0.40 * ydstogo THEN 1
      WHEN down = 2 AND yards_gained >= 0.60 * ydstogo THEN 1
      WHEN down IN (3, 4) AND yards_gained >= ydstogo THEN 1
      ELSE 0
    END AS is_successful_play
  FROM eligible_plays
)

SELECT
  game_id,
  play_id,
  season,
  nfl_week,
  qtr,
  down,
  ydstogo,
  yardline_100,
  drive,
  offense_franchise_id,
  defense_franchise_id,
  game_seconds_remaining,
  half_seconds_remaining,
  score_differential,
  goal_to_go,
  shotgun,
  no_huddle,
  posteam_timeouts_remaining,
  defteam_timeouts_remaining,
  offense_home_away,
  roof,
  surface,
  temperature,
  wind,
  is_successful_play
FROM final
