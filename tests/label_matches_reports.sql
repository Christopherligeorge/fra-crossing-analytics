select f.crossing_id, f.year
from {{ ref('fct_crossing_year') }} f
left join {{ ref('int_reports_by_crossing_year') }} r using (crossing_id, year)
where f.n_incidents != coalesce(r.n_incidents, 0)
    or f.had_incident != (coalesce(r.n_incidents, 0) > 0)::integer
