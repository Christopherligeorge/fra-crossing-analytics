select * from {{ ref('fct_crossing_year') }}
where latest_history_year >= year or years_since_last_incident < 1
    or prior_incident_count_1yr > prior_incident_count_3yr
    or prior_incident_count_3yr > prior_incident_count_5yr
