{{ config(
    materialized = 'view'
) }}

WITH source AS (
    SELECT
        *
    FROM {{ source('nfl_raw', 'v_raw_teams_flat') }}
)

SELECT TEAM_ABBR
    , TEAM_NAME
    , TEAM_ID
    , TEAM_NICK
    , TEAM_CONF
    , TEAM_DIVISION
    , TEAM_COLOR
    , TEAM_COLOR2
    , TEAM_COLOR3
    , TEAM_COLOR4
    , TEAM_LOGO_WIKIPEDIA
    , TEAM_LOGO_ESPN
    , TEAM_WORDMARK
    , TEAM_CONFERENCE_LOGO
    , TEAM_LEAGUE_LOGO
    , TEAM_LOGO_SQUARED
FROM source