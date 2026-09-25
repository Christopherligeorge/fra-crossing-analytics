select * from {{ ref('fct_crossing_year') }}
where inventory_revisiondate >= make_date(year, 1, 1)
    or crossingclosed != 'No' or crossingtype != 'Public' or crossingposition != 'At Grade'
    or (future_aadt_masked and annualaveragedailytrafficcount is not null)
    or (future_train_count_masked and (totaldaylightthrutrains is not null
        or totalnighttimethrutrains is not null or totaltransittrains is not null))
    or (future_warning_installation_masked and (countroadwaygatearms is not null or signsorsignals is not null))
