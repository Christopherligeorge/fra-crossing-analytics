select crossing_id, year, count(*)::bigint as n_incidents,
    sum(n_killed) as n_killed, sum(n_injured) as n_injured
from {{ ref('stg_reports') }}
where crossing_id is not null and year is not null
group by crossing_id, year

