"""Independent expected values for SQL boundary behavior, not research results."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]


def check():
    with duckdb.connect(str(ROOT / 'warehouse/fixture.duckdb'), read_only=True) as con:
        def row(crossing, year):
            frame = con.execute('select * from fct_crossing_year where crossing_id=? and year=?',
                                [crossing, year]).df()
            assert len(frame) == 1, (crossing, year, len(frame))
            return frame.iloc[0]

        first = row('000001A', 2014)
        assert first.annualaveragedailytrafficcount == 100  # exact Jan 1 is too late
        assert first.n_incidents == 2 and first.had_incident == 1
        assert first.prior_incident_count_1yr == 1
        assert first.prior_incident_count_5yr == 2 and first.prior_killed_5yr == 3
        assert row('000001A', 2015).annualaveragedailytrafficcount == 200
        assert row('000001A', 2015).prior_incident_count_1yr == 2
        assert row('000004D', 2018).prior_killed_5yr == 4
        assert con.execute("select count(*) from fct_crossing_year where crossing_id='000004D' and year in (2016,2017)").fetchone()[0] == 0
        for excluded in ['000003C', '000006F', '000007G', '000008H', '000009I']:
            assert con.execute('select count(*) from fct_crossing_year where crossing_id=?', [excluded]).fetchone()[0] == 0
        assert row('000010J', 2015).years_since_last_incident == 6
        assert row('000010J', 2015).prior_incident_count_5yr == 0
        for included in ['000002B', '000011K', '000012L']:
            row(included, 2014)
        assert bool(row('000011K', 2014).future_warning_installation_masked)
        assert con.execute("select countroadwaygatearms from fct_crossing_year where crossing_id='000011K' and year=2014").fetchone() == (None,)
        masked = con.execute("select annualaveragedailytrafficcount, totaldaylightthrutrains, countroadwaygatearms, signsorsignals, whistleban, numberofmaintracks, maximumtimetablespeed from fct_crossing_year where crossing_id='000005E' and year=2014").fetchone()
        assert masked == (None,) * 7, masked
        assert con.execute("select in_inventory, in_reports from dim_crossing where crossing_id='999999Z'").fetchone() == (False, True)
        assert con.execute('select count(*) from fct_crossing_year').fetchone()[0] == 82
        print('Fixture assertions passed: strict cutoff, raw conflicts, masks, gaps, recency, identity, labels, 82 rows.')


if __name__ == '__main__':
    check()
