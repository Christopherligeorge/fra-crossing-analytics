select source_row_id, reportkey as report_key, incidentnumber as incident_number,
    nullif(upper(trim(gradecrossingid)), '') as crossing_id,
    try_cast(date as timestamp) as reported_at,
    year(try_cast(date as timestamp))::integer as year,
    coalesce(try_cast(crossinguserskilled as double), 0) as n_killed,
    coalesce(try_cast(crossingusersinjured as double), 0) as n_injured
from {{ source('fra', 'reports') }}

