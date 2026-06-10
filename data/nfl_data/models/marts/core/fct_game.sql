WITH game_context AS (
  SELECT
    dim_game.game_id,
    dim_game.home_franchise_id,
    dim_game.away_franchise_id
  FROM {{ ref('dim_game') }} AS dim_game
),

schedule_measures AS (
  SELECT
    stg_schedule.game_id,
    stg_schedule.home_score,
    stg_schedule.away_score,
    stg_schedule.total,
    stg_schedule.game_result,
    stg_schedule.away_moneyline,
    stg_schedule.home_moneyline,
    stg_schedule.spread_line,
    stg_schedule.away_spread_odds,
    stg_schedule.home_spread_odds,
    stg_schedule.total_line,
    stg_schedule.under_odds,
    stg_schedule.over_odds,
    stg_schedule.away_rest,
    stg_schedule.home_rest
  FROM {{ ref('stg_schedule') }} AS stg_schedule
),

play_agg_game AS (
  SELECT
    fct_play.game_id,
    COUNT(*) AS play_count,
    SUM(CASE WHEN LOWER(fct_play.play_type) = 'no_play' THEN 1 ELSE 0 END) AS no_play_count,
    SUM(CASE WHEN fct_play.play_type IS NOT NULL AND LOWER(fct_play.play_type) != 'no_play' THEN 1 ELSE 0 END) AS real_play_count,
    SUM(CASE WHEN fct_play.play_type IS NOT NULL AND LOWER(fct_play.play_type) != 'no_play' THEN fct_play.epa ELSE 0 END) AS epa_sum,
    AVG(CASE WHEN fct_play.play_type IS NOT NULL AND LOWER(fct_play.play_type) != 'no_play' THEN fct_play.success ELSE NULL END) AS success_rate
  FROM {{ ref('fct_play') }} AS fct_play
  GROUP BY fct_play.game_id
)

SELECT
  game_context.game_id,
  game_context.home_franchise_id,
  game_context.away_franchise_id,

  schedule_measures.home_score,
  schedule_measures.away_score,
  schedule_measures.total,
  schedule_measures.game_result,
  schedule_measures.away_rest,
  schedule_measures.home_rest,
  schedule_measures.away_moneyline,
  schedule_measures.home_moneyline,
  schedule_measures.spread_line,
  schedule_measures.away_spread_odds,
  schedule_measures.home_spread_odds,
  schedule_measures.total_line,
  schedule_measures.under_odds,
  schedule_measures.over_odds,

  play_agg_game.play_count,
  play_agg_game.no_play_count,
  play_agg_game.real_play_count,
  play_agg_game.epa_sum,
  play_agg_game.success_rate

FROM game_context
LEFT JOIN schedule_measures
  ON schedule_measures.game_id = game_context.game_id
LEFT JOIN play_agg_game
  ON play_agg_game.game_id = game_context.game_id
