select r.year,
    case when p.crossing_id is null then 'outside_eligible_panel' else 'matched' end as join_status,
    count(*) as positive_crossing_years, sum(r.n_incidents) as reports
from {{ ref('int_reports_by_crossing_year') }} r
left join {{ ref('fct_crossing_year') }} p using (crossing_id, year)
where r.year between {{ var('first_year') }} and {{ var('last_year') }}
group by r.year, join_status
