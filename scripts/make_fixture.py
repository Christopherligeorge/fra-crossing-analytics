"""Generate deliberately synthetic boundary cases; never used for research claims."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
from research.crossing_risk.build_dataset import INVENTORY_COLS

META = ['revisiondate', 'crossingidsuffix', 'crossingclosed', 'crossingposition',
        'crossingpurpose', 'reporttype', 'reportstatus', 'reportingagencytype',
        'annualaveragedailytrafficyear', 'trainsperyear', 'installationdateactivewa', 'whistledate']


def make_fixture(destination):
    fields = ['source_row_id'] + list(dict.fromkeys(INVENTORY_COLS + META))
    base = dict.fromkeys(fields, '')
    base.update(revisiondate='2013-06-01', crossingclosed='No', crossingtype='Public',
                crossingposition='At Grade', crossingpurpose='Highway', reporttype='Major',
                statename='TEXAS', annualaveragedailytrafficcount='100',
                annualaveragedailytrafficyear='2012', totaldaylightthrutrains='2',
                totalnighttimethrutrains='1', trainsperyear='2012',
                countroadwaygatearms='2', signsorsignals='Gates', whistleban='No')
    rows = []

    def revision(crossing, **overrides):
        row = {**base, 'crossingid': crossing, 'source_row_id': str(len(rows) + 1), **overrides}
        rows.append(row)
        return row

    revision(' 000001a ')  # normalization
    revision('000001A', revisiondate='2014-01-01', annualaveragedailytrafficcount='200')
    revision('000002B')
    revision('000002B', reportingagencytype='State')  # ignored field: identical
    revision('000003C', totaldaylightthrutrains='02')
    revision('000003C', totaldaylightthrutrains='2')  # raw conflict despite equal numbers
    revision('000004D')
    revision('000004D', revisiondate='2015-06-01', crossingclosed='Yes')
    revision('000004D', revisiondate='2017-06-01')  # history survives closure
    revision('000005E', annualaveragedailytrafficyear='2014', trainsperyear='2014',
             installationdateactivewa='2014-01-01', whistledate='2014-01-01',
             numberofmaintracks='-1', maximumtimetablespeed='bad')
    revision('000006F', crossingtype='Private')
    revision('000007G', crossingposition='RR Under')
    revision('000008H', revisiondate='bad')
    revision(' ')
    revision('000009I', countyname='A')
    revision('000009I', countyname='B')  # conflict outside model predictors
    revision('000010J')  # old report retained in recency, outside five-year window
    revision('000011K', crossingpurpose='Pedestrian', installationdateactivewa='071975')
    # Purpose does not exclude; frozen legacy parsing reads this as 2075-07-19.
    inventory_current = [{**base, 'source_row_id': '1', 'crossingid': '000012L'}]
    # The repeated source_row_id across datasets is legal.
    reports = []
    for crossing, year, killed in [('000001A', 2009, 1), ('000001A', 2013, 2),
                                  ('000001A', 2014, 3), ('000001A', 2014, 0),
                                  ('000001A', 2025, 8), ('000004D', 2016, 4),
                                  ('000010J', 2009, 1), ('999999Z', 2014, 0)]:
        key = str(len(reports) + 1)
        reports.append(dict(source_row_id=key, reportkey=key, incidentnumber=key,
                            gradecrossingid=crossing.lower(), date=f'{year}-06-01',
                            crossinguserskilled=killed, crossingusersinjured=1))
    reports.append(dict(source_row_id='9', reportkey='9', incidentnumber='9',
                        gradecrossingid='000001A', date='bad',
                        crossinguserskilled='', crossingusersinjured=''))
    for dataset, records, columns in [('vhwz-raag', rows, fields),
                                      ('m2f8-22s6', inventory_current, fields),
                                      ('7wn6-i5b9', reports, list(reports[0]))]:
        folder = Path(destination) / dataset
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'page_00000000.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)


if __name__ == '__main__':
    make_fixture(ROOT / 'data/fixture/sources')
