WITH schedule AS (

    SELECT
        schedule.*
    FROM {{ ref('stg_schedule') }} AS schedule

),

team_mapped AS (

    SELECT
        schedule.*,
        home_team_code.franchise_id as home_franchise_id,
        home_team_code.team_code    as home_team_code,
        away_team_code.franchise_id as away_franchise_id,
        away_team_code.team_code    as away_team_code
    FROM schedule
    LEFT JOIN {{ ref('dim_team_code') }} as home_team_code
        ON home_team_code.source_team_code = schedule.home_team  -- or sch.HOME_TEAM
    LEFT JOIN {{ ref('dim_team_code') }} as away_team_code
        ON away_team_code.source_team_code = schedule.away_team  -- or sch.AWAY_TEAM

)
    SELECT
        game_id,
        season,
        game_type,
        week,
        gameday,
        weekday,
        gametime,
        home_franchise_id,
        away_franchise_id,
        home_team_code,
        away_team_code,
        home_score,
        away_score,
        total,
        game_location,
        game_result,
        overtime,
        away_moneyline,
        home_moneyline,
        spread_line,
        away_spread_odds,
        home_spread_odds,
        total_line,
        under_odds,
        over_odds,
        away_rest,
        home_rest,
        div_game,
        roof,
        surface,
        temperature,
        wind,
        stadium_id,
        stadium,
        referee,
        away_qb_id,
        home_qb_id,
        away_qb_name,
        home_qb_name,
        away_coach,
        home_coach,
        old_game_id,
        gsis,
        nfl_detail_id,
        pfr,
        pff,
        espn,
        ftn
    FROM team_mapped
