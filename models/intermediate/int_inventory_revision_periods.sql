with revisions as (
    select * from {{ ref('stg_inventory_history') }}
    union all
    select * from {{ ref('stg_inventory_current') }}
), same_date as (
    select *, count(distinct feature_hash) over (
        partition by crossing_id, inventory_revisiondate
    ) as distinct_versions
    from revisions
    where crossing_id is not null and inventory_revisiondate is not null
    qualify row_number() over (
        partition by crossing_id, inventory_revisiondate order by source_row_id
    ) = 1
)
select *, lead(inventory_revisiondate) over (
    partition by crossing_id order by inventory_revisiondate
) as next_revisiondate
from same_date
-- Keep closed/conflicting revisions here: they must supersede older good records.

