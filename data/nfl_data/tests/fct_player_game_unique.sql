SELECT
    game_id,
    player_id,
    COUNT(*) AS row_count
FROM {{ ref('fct_player_game') }}
GROUP BY 1, 2
HAVING COUNT(*) > 1
