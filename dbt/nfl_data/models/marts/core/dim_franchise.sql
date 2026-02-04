SELECT 
    franchise_id,
    franchise_name,
    team_code,
    conference,
    division
FROM {{ ref('dim_franchise_seed') }}
