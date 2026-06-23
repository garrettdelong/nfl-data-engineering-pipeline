SELECT
    game_id,
    play_id,
    play_type,
    offense_franchise_id,
    defense_franchise_id
FROM {{ ref('fct_play') }}
WHERE play_type IS NOT NULL
  AND LOWER(play_type) != 'no_play'
  AND (
    offense_franchise_id IS NULL
    OR defense_franchise_id IS NULL
  )
