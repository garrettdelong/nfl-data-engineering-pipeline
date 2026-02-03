with ranked as (
  select
    gsis_id as player_id,
    full_name,
    first_name,
    last_name,
    birth_date,
    height,
    espn_id,
    pfr_id,
    entry_year,
    rookie_year,
    draft_club,
    draft_number,
    row_number() over (
      partition by gsis_id
      order by season desc, week desc
    ) as rn
  from {{ ref('stg_weekly_rosters') }}
  where gsis_id is not null
)

select
  player_id,
  full_name,
  first_name,
  last_name,
  birth_date,
  height,
  espn_id,
  pfr_id,
  entry_year,
  rookie_year,
  draft_club,
  draft_number
from ranked
where rn = 1;
