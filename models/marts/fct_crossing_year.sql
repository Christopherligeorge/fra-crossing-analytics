select p.*, coalesce(r.n_incidents, 0)::bigint as n_incidents,
    trunc(coalesce(r.n_killed, 0))::bigint as n_killed,
    trunc(coalesce(r.n_injured, 0))::bigint as n_injured,
    (coalesce(r.n_incidents, 0) > 0)::integer as had_incident,
    h.* exclude (crossing_id, year)
from {{ ref('int_inventory_latest_pre_year') }} p
left join {{ ref('int_reports_by_crossing_year') }} r using (crossing_id, year)
join {{ ref('int_history_windows') }} h using (crossing_id, year)

