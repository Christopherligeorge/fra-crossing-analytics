with ids as (
    select crossing_id, true as in_inventory, false as in_reports from {{ ref('stg_inventory_history') }}
    union all
    select crossing_id, true, false from {{ ref('stg_inventory_current') }}
    union all
    select crossing_id, false, true from {{ ref('stg_reports') }}
)
select crossing_id, bool_or(in_inventory) as in_inventory, bool_or(in_reports) as in_reports
from ids where crossing_id is not null group by crossing_id
-- Identity universe, not current attributes. Year-specific attributes belong in the fact.

