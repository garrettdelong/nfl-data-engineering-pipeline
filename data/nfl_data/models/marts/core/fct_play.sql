{{ config(
    materialized = 'incremental',
    unique_key = 'play_key',
    incremental_strategy = 'merge',
    on_schema_change = 'sync_all_columns'
) }}

SELECT
    stg_pbp.game_id || '-' || stg_pbp.play_id || '-' || COALESCE(CAST(stg_pbp.drive AS VARCHAR), 'no_drive') AS play_key,
    stg_pbp.game_id,
    stg_pbp.play_id,
    stg_pbp.season,
    stg_pbp.nfl_week,
    stg_pbp.qtr,
    stg_pbp.down,
    stg_pbp.ydstogo,
    stg_pbp.yardline_100,
    stg_pbp.play_type,
    stg_pbp.play_desc,
    offense_tc.franchise_id AS offense_franchise_id,
    defense_tc.franchise_id AS defense_franchise_id,
    stg_pbp.passer_player_id,
    stg_pbp.rusher_player_id,
    stg_pbp.receiver_player_id,
    stg_pbp.yards_gained,
    stg_pbp.passing_yards,
    stg_pbp.rushing_yards,
    stg_pbp.receiving_yards,
    stg_pbp.yards_after_catch,
    stg_pbp.epa,
    stg_pbp.wp,
    stg_pbp.success,
    stg_pbp.touchdown,
    stg_pbp.pass_touchdown,
    stg_pbp.rush_touchdown,
    stg_pbp.return_touchdown,
    stg_pbp.interception,
    stg_pbp.fumble,
    stg_pbp.fumble_lost,
    stg_pbp.fumble_forced,
    stg_pbp.series,
    stg_pbp.drive,
    stg_pbp.penalty_team,
    stg_pbp.penalty_player_id,
    stg_pbp.penalty_player_name,
    stg_pbp.penalty_yards,
    stg_pbp.penalty_type,
    stg_pbp.penalty,
    stg_pbp.source_file,
    stg_pbp.source_dataset,
    stg_pbp.source_year,
    stg_pbp.loaded_at
FROM {{ ref('stg_play_by_play') }} AS stg_pbp
LEFT JOIN {{ ref('dim_team_code') }} AS offense_tc
    ON offense_tc.source_team_code = stg_pbp.posteam
LEFT JOIN {{ ref('dim_team_code') }} AS defense_tc
    ON defense_tc.source_team_code = stg_pbp.defteam
{% if is_incremental() %}
WHERE stg_pbp.loaded_at >= DATEADD(
    day,
    -{{ var('incremental_lookback_days', 3) }},
    COALESCE(
        (
            SELECT MAX(loaded_at)
            FROM {{ this }}
        ),
        CAST('1900-01-01' AS TIMESTAMP)
    )
)
{% endif %}
