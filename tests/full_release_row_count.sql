{{ config(enabled=var('full_release', false)) }}
select count(*) as actual_rows from {{ ref('fct_crossing_year') }} having count(*) != 1526612
