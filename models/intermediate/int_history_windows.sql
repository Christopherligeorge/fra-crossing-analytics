select p.crossing_id, p.year,
    coalesce(sum(r.n_incidents) filter (where r.year >= p.year - 1), 0) as prior_incident_count_1yr,
    coalesce(sum(r.n_incidents) filter (where r.year >= p.year - 3), 0) as prior_incident_count_3yr,
    coalesce(sum(r.n_incidents) filter (where r.year >= p.year - 5), 0) as prior_incident_count_5yr,
    coalesce(sum(r.n_killed) filter (where r.year >= p.year - 5), 0) as prior_killed_5yr,
    coalesce(sum(r.n_injured) filter (where r.year >= p.year - 5), 0) as prior_injured_5yr,
    p.year - max(r.year) as years_since_last_incident,
    max(r.year) as latest_history_year
from {{ ref('int_inventory_latest_pre_year') }} p
left join {{ ref('int_reports_by_crossing_year') }} r
    on p.crossing_id = r.crossing_id and r.year < p.year
group by p.crossing_id, p.year

