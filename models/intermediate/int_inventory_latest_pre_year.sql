with years as (
    select range::integer as year, make_date(range::integer, 1, 1) as cutoff
    from range({{ var('first_year') }}, {{ var('last_year') + 1 }})
), eligible as (
    select r.*, y.year, y.cutoff,
        coalesce(try_cast(annualaveragedailytrafficyear as double) >= y.year, false) as future_aadt_masked,
        coalesce(try_cast(trainsperyear as double) >= y.year, false) as future_train_count_masked,
        coalesce(({{ legacy_measurement_date('installationdateactivewa') }}) >= y.cutoff, false) as future_warning_installation_masked
    from {{ ref('int_inventory_revision_periods') }} r
    join years y on r.inventory_revisiondate < y.cutoff
        and (r.next_revisiondate >= y.cutoff or r.next_revisiondate is null)
    where distinct_versions = 1 and crossingclosed = 'No'
        and crossingtype = 'Public' and crossingposition = 'At Grade'
)
select * exclude (feature_hash, distinct_versions, next_revisiondate, cutoff)
    replace (
    {% for col in numeric_features() %}
        case
        {% if col == 'annualaveragedailytrafficcount' %}
            when future_aadt_masked then null
        {% elif col in ['totaldaylightthrutrains', 'totalnighttimethrutrains', 'totaltransittrains'] %}
            when future_train_count_masked then null
        {% elif col == 'countroadwaygatearms' %}
            when future_warning_installation_masked then null
        {% endif %}
            when try_cast({{ col }} as double) < 0 then null
            else try_cast({{ col }} as double) end as {{ col }},
    {% endfor %}
        case when future_warning_installation_masked then null else signsorsignals end as signsorsignals,
        case when ({{ legacy_measurement_date('whistledate') }}) >= cutoff then null else whistleban end as whistleban
    ),
    date_diff('day', inventory_revisiondate, cutoff) / 365.25 as inventory_age_years,
    'reported_open_public_at_grade_asof_revision' as historical_eligibility,
    false as availability_timestamp_verified
from eligible
