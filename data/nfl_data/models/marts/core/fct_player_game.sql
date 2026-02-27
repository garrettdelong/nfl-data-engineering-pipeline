WITH player_play AS (

    SELECT
        game_id,
        season,
        nfl_week,
        passer_player_id AS player_id,
        offense_franchise_id AS franchise_id,
        CASE WHEN LOWER(play_type) = 'no_play' THEN 1 ELSE 0 END AS is_no_play,
        1 AS is_passer,
        0 AS is_rusher,
        0 AS is_receiver,
        epa
    FROM {{ ref('fct_play') }}
    WHERE passer_player_id IS NOT NULL

    UNION ALL

    SELECT
        game_id,
        season,
        nfl_week,
        rusher_player_id AS player_id,
        offense_franchise_id AS franchise_id,
        CASE WHEN LOWER(play_type) = 'no_play' THEN 1 ELSE 0 END AS is_no_play,
        0 AS is_passer,
        1 AS is_rusher,
        0 AS is_receiver,
        epa
    FROM {{ ref('fct_play') }}
    WHERE rusher_player_id IS NOT NULL

    UNION ALL

    SELECT
        game_id,
        season,
        nfl_week,
        receiver_player_id AS player_id,
        offense_franchise_id AS franchise_id,
        CASE WHEN LOWER(play_type) = 'no_play' THEN 1 ELSE 0 END AS is_no_play,
        0 AS is_passer,
        0 AS is_rusher,
        1 AS is_receiver,
        epa
    FROM {{ ref('fct_play') }}
    WHERE receiver_player_id IS NOT NULL

),

player_game_team AS (

    SELECT
        game_id,
        player_id,
        franchise_id,
        COUNT(*) AS role_play_count,
        ROW_NUMBER() OVER (
            PARTITION BY game_id, player_id
            ORDER BY COUNT(*) DESC
        ) AS franchise_rank
    FROM player_play
    GROUP BY 1, 2, 3

),

player_game AS (

    SELECT
        player_play.game_id,
        player_play.player_id,
        MAX(player_play.season) AS season,
        MAX(player_play.nfl_week) AS nfl_week,

        MAX(CASE WHEN player_game_team.franchise_rank = 1 THEN player_game_team.franchise_id END) AS franchise_id,

        COUNT(*) AS play_count,
        SUM(player_play.is_no_play) AS no_play_count,
        SUM(CASE WHEN player_play.is_no_play = 0 THEN 1 ELSE 0 END) AS real_play_count,

        SUM(player_play.is_passer) AS passer_play_count,
        SUM(player_play.is_rusher) AS rusher_play_count,
        SUM(player_play.is_receiver) AS receiver_play_count,

        SUM(CASE WHEN player_play.is_no_play = 0 THEN COALESCE(player_play.epa, 0) ELSE 0 END) AS epa_sum

    FROM player_play 
    LEFT JOIN player_game_team 
        ON player_play.game_id = player_game_team.game_id
        AND player_play.player_id = player_game_team.player_id
        AND player_play.franchise_id = player_game_team.franchise_id
    GROUP BY 1, 2

)
    SELECT
        player_game.game_id,
        player_game.player_id,
        player_game.season,
        player_game.nfl_week,
        player_game.franchise_id,

        CASE
            WHEN player_game.franchise_id = dim_game.home_franchise_id THEN dim_game.away_franchise_id
            WHEN player_game.franchise_id = dim_game.away_franchise_id THEN dim_game.home_franchise_id
            ELSE NULL
        END AS opponent_franchise_id,

        CASE
            WHEN player_game.franchise_id = dim_game.home_franchise_id THEN 'home'
            WHEN player_game.franchise_id = dim_game.away_franchise_id THEN 'away'
            ELSE 'unknown'
        END AS game_team_side,

        player_game.play_count,
        player_game.no_play_count,
        player_game.real_play_count,
        player_game.passer_play_count,
        player_game.rusher_play_count,
        player_game.receiver_play_count,
        player_game.epa_sum

    FROM player_game
    LEFT JOIN {{ ref('dim_game') }} dim_game
        ON player_game.game_id = dim_game.game_id
