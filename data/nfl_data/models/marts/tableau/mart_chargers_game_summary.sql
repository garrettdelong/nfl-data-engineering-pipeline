{{ config(
    materialized = 'table'
) }}

WITH chargers_games AS (
  SELECT
    dim_game.game_id,
    dim_game.season,
    dim_game.week AS nfl_week,
    dim_game.game_type AS season_type,
    dim_game.gameday AS game_date,
    CASE
      WHEN dim_game.home_franchise_id = 'chargers' THEN dim_game.home_team_code
      ELSE dim_game.away_team_code
    END AS chargers_team_code,
    CASE
      WHEN dim_game.home_franchise_id = 'chargers' THEN dim_game.away_team_code
      ELSE dim_game.home_team_code
    END AS opponent_team_code,
    CASE
      WHEN dim_game.home_franchise_id = 'chargers' THEN dim_game.away_franchise_id
      ELSE dim_game.home_franchise_id
    END AS opponent_franchise_id,
    CASE
      WHEN dim_game.home_franchise_id = 'chargers' THEN 'home'
      ELSE 'away'
    END AS home_away
  FROM {{ ref('dim_game') }} AS dim_game
  WHERE (
      dim_game.home_franchise_id = 'chargers'
      OR dim_game.away_franchise_id = 'chargers'
    )
    AND dim_game.game_type = 'REG'
),

game_scores AS (
  SELECT
    fct_game.game_id,
    CASE
      WHEN chargers_games.home_away = 'home' THEN fct_game.home_score
      ELSE fct_game.away_score
    END AS points_for,
    CASE
      WHEN chargers_games.home_away = 'home' THEN fct_game.away_score
      ELSE fct_game.home_score
    END AS points_against
  FROM {{ ref('fct_game') }} AS fct_game
  INNER JOIN chargers_games
    ON chargers_games.game_id = fct_game.game_id
),

play_metrics AS (
  SELECT
    fct_play.game_id,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN 1 ELSE 0 END) AS offensive_play_count,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' THEN 1 ELSE 0 END) AS defensive_play_count,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN fct_play.yards_gained ELSE 0 END) AS offensive_yards,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN fct_play.passing_yards ELSE 0 END) AS passing_yards,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN fct_play.rushing_yards ELSE 0 END) AS rushing_yards,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN fct_play.epa ELSE 0 END) AS offensive_epa,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' THEN fct_play.epa ELSE 0 END) AS defensive_epa_allowed,
    AVG(CASE WHEN fct_play.offense_franchise_id = 'chargers' THEN fct_play.success ELSE NULL END) AS offensive_success_rate,
    AVG(CASE WHEN fct_play.defense_franchise_id = 'chargers' THEN fct_play.success ELSE NULL END) AS defensive_success_rate_allowed,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' AND fct_play.down = 3 THEN 1 ELSE 0 END) AS third_down_attempts,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' AND fct_play.down = 3 AND (fct_play.yards_gained >= fct_play.ydstogo OR fct_play.touchdown = 1) THEN 1 ELSE 0 END) AS third_down_conversions,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' AND (fct_play.interception = 1 OR fct_play.fumble_lost = 1) THEN 1 ELSE 0 END) AS turnovers_committed,
    SUM(CASE WHEN fct_play.offense_franchise_id = 'chargers' AND fct_play.yards_gained >= 20 THEN 1 ELSE 0 END) AS explosive_plays,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' AND fct_play.down = 3 THEN 1 ELSE 0 END) AS opponent_third_down_attempts,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' AND fct_play.down = 3 AND (fct_play.yards_gained >= fct_play.ydstogo OR fct_play.touchdown = 1) THEN 1 ELSE 0 END) AS opponent_third_down_conversions,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' AND (fct_play.interception = 1 OR fct_play.fumble_lost = 1) THEN 1 ELSE 0 END) AS takeaways,
    SUM(CASE WHEN fct_play.defense_franchise_id = 'chargers' AND fct_play.yards_gained >= 20 THEN 1 ELSE 0 END) AS explosive_plays_allowed,
    MAX(fct_play.loaded_at) AS last_loaded_at
  FROM {{ ref('fct_play') }} AS fct_play
  INNER JOIN chargers_games
    ON chargers_games.game_id = fct_play.game_id
  WHERE fct_play.play_type IS NOT NULL
    AND LOWER(fct_play.play_type) != 'no_play'
  GROUP BY fct_play.game_id
),

pass_game_metrics AS (
  SELECT
    fct_play_pass.game_id,
    SUM(CASE WHEN fct_play_pass.offense_franchise_id = 'chargers' AND fct_play_pass.pass_attempt = 1 THEN 1 ELSE 0 END) AS passing_attempts,
    SUM(CASE WHEN fct_play_pass.offense_franchise_id = 'chargers' AND fct_play_pass.sack = 1 THEN 1 ELSE 0 END) AS sacks_allowed,
    SUM(CASE WHEN fct_play_pass.defense_franchise_id = 'chargers' AND fct_play_pass.sack = 1 THEN 1 ELSE 0 END) AS sacks,
    SUM(CASE WHEN fct_play_pass.offense_franchise_id = 'chargers' THEN fct_play_pass.epa ELSE 0 END) AS passing_epa,
    SUM(CASE WHEN fct_play_pass.offense_franchise_id = 'chargers' AND fct_play_pass.down IN (1, 2) THEN 1 ELSE 0 END) AS early_down_pass_count
  FROM {{ ref('fct_play_pass') }} AS fct_play_pass
  INNER JOIN chargers_games
    ON chargers_games.game_id = fct_play_pass.game_id
  GROUP BY fct_play_pass.game_id
),

rush_game_metrics AS (
  SELECT
    fct_play_rush.game_id,
    SUM(CASE WHEN fct_play_rush.offense_franchise_id = 'chargers' AND fct_play_rush.rush_attempt = 1 THEN 1 ELSE 0 END) AS rush_attempts,
    SUM(CASE WHEN fct_play_rush.offense_franchise_id = 'chargers' AND fct_play_rush.qb_scramble = 1 THEN 1 ELSE 0 END) AS qb_scrambles,
    SUM(CASE WHEN fct_play_rush.offense_franchise_id = 'chargers' THEN fct_play_rush.epa ELSE 0 END) AS rushing_epa,
    SUM(CASE WHEN fct_play_rush.offense_franchise_id = 'chargers' AND fct_play_rush.down IN (1, 2) THEN 1 ELSE 0 END) AS early_down_rush_count
  FROM {{ ref('fct_play_rush') }} AS fct_play_rush
  INNER JOIN chargers_games
    ON chargers_games.game_id = fct_play_rush.game_id
  GROUP BY fct_play_rush.game_id
),

final AS (
  SELECT
    chargers_games.game_id,
    chargers_games.season,
    chargers_games.nfl_week,
    chargers_games.season_type,
    chargers_games.game_date,
    chargers_games.chargers_team_code,
    chargers_games.opponent_team_code,
    opponent_franchise.franchise_name AS opponent_name,
    chargers_games.home_away,
    CASE
      WHEN game_scores.points_for > game_scores.points_against THEN 'win'
      WHEN game_scores.points_for < game_scores.points_against THEN 'loss'
      WHEN game_scores.points_for = game_scores.points_against THEN 'tie'
      ELSE NULL
    END AS result,
    game_scores.points_for,
    game_scores.points_against,
    game_scores.points_for - game_scores.points_against AS point_differential,
    play_metrics.offensive_play_count,
    play_metrics.defensive_play_count,
    play_metrics.offensive_yards,
    play_metrics.passing_yards,
    play_metrics.rushing_yards,
    play_metrics.offensive_epa,
    play_metrics.defensive_epa_allowed,
    play_metrics.offensive_epa - play_metrics.defensive_epa_allowed AS net_epa,
    play_metrics.offensive_epa / NULLIF(play_metrics.offensive_play_count, 0) AS offensive_epa_per_play,
    play_metrics.defensive_epa_allowed / NULLIF(play_metrics.defensive_play_count, 0) AS defensive_epa_allowed_per_play,
    (play_metrics.offensive_epa - play_metrics.defensive_epa_allowed) / NULLIF(play_metrics.offensive_play_count + play_metrics.defensive_play_count, 0) AS net_epa_per_play,
    play_metrics.offensive_success_rate,
    play_metrics.defensive_success_rate_allowed,
    play_metrics.offensive_success_rate - play_metrics.defensive_success_rate_allowed AS success_rate_margin,
    pass_game_metrics.passing_attempts,
    pass_game_metrics.sacks_allowed,
    pass_game_metrics.passing_attempts + pass_game_metrics.sacks_allowed AS pass_play_count,
    rush_game_metrics.rush_attempts,
    rush_game_metrics.qb_scrambles,
    rush_game_metrics.rush_attempts + rush_game_metrics.qb_scrambles AS rush_play_count,
    (pass_game_metrics.passing_attempts + pass_game_metrics.sacks_allowed) / NULLIF(pass_game_metrics.passing_attempts + pass_game_metrics.sacks_allowed + rush_game_metrics.rush_attempts + rush_game_metrics.qb_scrambles, 0) AS pass_rate,
    (rush_game_metrics.rush_attempts + rush_game_metrics.qb_scrambles) / NULLIF(pass_game_metrics.passing_attempts + pass_game_metrics.sacks_allowed + rush_game_metrics.rush_attempts + rush_game_metrics.qb_scrambles, 0) AS rush_rate,
    pass_game_metrics.passing_epa / NULLIF(pass_game_metrics.passing_attempts + pass_game_metrics.sacks_allowed, 0) AS passing_epa_per_play,
    rush_game_metrics.rushing_epa / NULLIF(rush_game_metrics.rush_attempts + rush_game_metrics.qb_scrambles, 0) AS rushing_epa_per_play,
    pass_game_metrics.early_down_pass_count / NULLIF(pass_game_metrics.early_down_pass_count + rush_game_metrics.early_down_rush_count, 0) AS early_down_pass_rate,
    play_metrics.third_down_attempts,
    play_metrics.third_down_conversions,
    play_metrics.third_down_conversions / NULLIF(play_metrics.third_down_attempts, 0) AS third_down_conversion_rate,
    play_metrics.turnovers_committed,
    play_metrics.explosive_plays,
    play_metrics.opponent_third_down_attempts,
    play_metrics.opponent_third_down_conversions,
    1 - (play_metrics.opponent_third_down_conversions / NULLIF(play_metrics.opponent_third_down_attempts, 0)) AS defensive_third_down_stop_rate,
    pass_game_metrics.sacks,
    play_metrics.takeaways,
    play_metrics.explosive_plays_allowed,
    play_metrics.last_loaded_at,
    CURRENT_TIMESTAMP() AS mart_refreshed_at
  FROM chargers_games
  INNER JOIN game_scores
    ON game_scores.game_id = chargers_games.game_id
  INNER JOIN play_metrics
    ON play_metrics.game_id = chargers_games.game_id
  INNER JOIN pass_game_metrics
    ON pass_game_metrics.game_id = chargers_games.game_id
  INNER JOIN rush_game_metrics
    ON rush_game_metrics.game_id = chargers_games.game_id
  INNER JOIN {{ ref('dim_franchise') }} AS opponent_franchise
    ON opponent_franchise.franchise_id = chargers_games.opponent_franchise_id
)

SELECT
  game_id,
  season,
  nfl_week,
  season_type,
  game_date,
  chargers_team_code,
  opponent_team_code,
  opponent_name,
  home_away,
  result,
  points_for,
  points_against,
  point_differential,
  offensive_play_count,
  defensive_play_count,
  offensive_yards,
  passing_yards,
  rushing_yards,
  offensive_epa,
  defensive_epa_allowed,
  net_epa,
  offensive_epa_per_play,
  defensive_epa_allowed_per_play,
  net_epa_per_play,
  offensive_success_rate,
  defensive_success_rate_allowed,
  success_rate_margin,
  passing_attempts,
  sacks_allowed,
  pass_play_count,
  rush_attempts,
  qb_scrambles,
  rush_play_count,
  pass_rate,
  rush_rate,
  passing_epa_per_play,
  rushing_epa_per_play,
  early_down_pass_rate,
  third_down_attempts,
  third_down_conversions,
  third_down_conversion_rate,
  turnovers_committed,
  explosive_plays,
  opponent_third_down_attempts,
  opponent_third_down_conversions,
  defensive_third_down_stop_rate,
  sacks,
  takeaways,
  explosive_plays_allowed,
  last_loaded_at,
  mart_refreshed_at
FROM final
