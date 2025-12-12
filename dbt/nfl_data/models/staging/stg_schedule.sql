{{ config(
    materialized = 'view'
) }}

WITH source AS (
    SELECT
        *
    FROM {{ source('nfl_raw', 'v_raw_schedule_flat') }}
)

SELECT GAME_ID
    , SEASON
    , GAME_TYPE
    , WEEK
    , GAMEDAY
    , WEEKDAY
    , GAMETIME
    , AWAY_TEAM
    , AWAY_SCORE
    , HOME_TEAM
    , HOME_SCORE
    , GAME_LOCATION
    , GAME_RESULT
    , TOTAL
    , OVERTIME
    , OLD_GAME_ID
    , GSIS
    , NFL_DETAIL_ID
    , PFR
    , PFF
    , ESPN
    , FTN
    , AWAY_REST
    , HOME_REST
    , AWAY_MONEYLINE
    , HOME_MONEYLINE
    , SPREAD_LINE
    , AWAY_SPREAD_ODDS
    , HOME_SPREAD_ODDS
    , TOTAL_LINE
    , UNDER_ODDS
    , OVER_ODDS
    , DIV_GAME
    , ROOF
    , SURFACE
    , TEMPERATURE
    , WIND
    , AWAY_QB_ID
    , HOME_QB_ID
    , AWAY_QB_NAME
    , HOME_QB_NAME
    , AWAY_COACH
    , HOME_COACH
    , REFEREE
    , STADIUM_ID
    , STADIUM
FROM source
  