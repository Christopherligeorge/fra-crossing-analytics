{% macro numeric_features() %}
  {{ return(['annualaveragedailytrafficcount', 'totaldaylightthrutrains',
    'totalnighttimethrutrains', 'totaltransittrains', 'maximumtimetablespeed',
    'numberofmaintracks', 'numberofsidingtracks', 'numberofyardtracks',
    'numberofindustrytracks', 'numberoftransittracks', 'numbercrossbuckassemblies',
    'countroadwaygatearms']) }}
{% endmacro %}

{% macro legacy_measurement_date(column) %}
    -- Reproduce pandas/dateutil mixed parsing AS OF the 2026 frozen release.
    -- Compact six-digit values were read MMDDYY, not the apparent MMYYYY.
    -- Freeze the 76 two-digit-year pivot instead of letting wall-clock time move it.
    case when regexp_full_match({{ column }}, '[0-9]{6}') then
        try_strptime(left({{ column }}, 4)
            || case when try_cast(right({{ column }}, 2) as integer) >= 76 then '19' else '20' end
            || right({{ column }}, 2), '%m%d%Y')
    when regexp_full_match({{ column }}, '[0-9]{4}') then try_strptime({{ column }}, '%Y')
    else coalesce(try_cast({{ column }} as timestamp),
        try_strptime({{ column }}, ['%d%b%y', '%m/%d/%Y', '%m/%d/%y'])) end
{% endmacro %}

{% macro inventory_comparison_fields() %}
  {{ return(['crossing_id', 'latitude', 'longitude', 'countycode', 'countyname']
    + numeric_features() + ['statename', 'crossingtype', 'signsorsignals',
    'highwaypaved', 'crossingilluminated', 'whistleban', 'crossingclosed',
    'crossingposition', 'crossingpurpose', 'reporttype',
    'annualaveragedailytrafficyear', 'trainsperyear', 'installationdateactivewa',
    'whistledate']) }}
{% endmacro %}

{% macro stage_inventory(source_name, dataset_id) %}
with normalized as (
    select * exclude (crossingid),
        nullif(upper(trim(crossingid)), '') as crossing_id,
        try_cast(revisiondate as date) as inventory_revisiondate,
        '{{ dataset_id }}' as inventory_source_dataset
    from {{ source('fra', source_name) }}
)
select *,
    -- Match the frozen builder: compare raw values before casting or masking.
    hash({{ inventory_comparison_fields() | join(', ') }}) as feature_hash
from normalized
{% endmacro %}
