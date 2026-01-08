SELECT 
    map_team_code_seed.source_team_code,
	map_team_code_seed.team_code,
	dim_franchise.franchise_id
FROM {{ ref('map_team_code_seed') }} AS map_team_code_seed
LEFT JOIN {{ ref('dim_franchise') }} AS dim_franchise
    ON map_team_code_seed.team_code = dim_franchise.team_code