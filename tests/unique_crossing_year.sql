select crossing_id, year from {{ ref('fct_crossing_year') }}
group by crossing_id, year having count(*) != 1
