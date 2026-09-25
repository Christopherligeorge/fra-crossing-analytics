"""Compare every reference column and keyed row; export only after exact equality."""
import argparse
import hashlib
import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]


def quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    reference = args.release.resolve() / 'data/crossing_year_panel.parquet'
    manifest = json.loads((args.release / 'data_manifest.json').read_text())
    expected = next(a['sha256'] for a in manifest['artifacts'] if a['path'] == 'data/crossing_year_panel.parquet')
    with reference.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('Reference panel does not match frozen manifest')
    output = ROOT / 'artifacts'
    output.mkdir(exist_ok=True)
    with duckdb.connect(str(ROOT / 'warehouse/full.duckdb'), read_only=True) as con:
        reference_sql = str(reference).replace("'", "''")
        con.execute(f"create temp view reference as select * from read_parquet('{reference_sql}')")
        columns = [c[0] for c in con.execute('describe reference').fetchall()]
        con.execute('create temp view candidate as select * exclude (crossing_id, latest_history_year), crossing_id as crossingid from fct_crossing_year')
        missing_keys = con.execute('select count(*) from reference r full join candidate c using(crossingid, year) where r.crossingid is null or c.crossingid is null').fetchone()[0]
        differences = {}
        for col in columns:
            name = quote(col)
            n = con.execute(f'select count(*) from reference r join candidate c using(crossingid,year) where r.{name} is distinct from c.{name}').fetchone()[0]
            if n:
                differences[col] = n
        rows = con.execute('select count(*) from candidate').fetchone()[0]
        result = {'rows': rows, 'reference_columns_compared': len(columns), 'missing_or_extra_keys': missing_keys,
                  'column_mismatches': differences, 'reference_sha256': expected,
                  'exact_value_parity': rows == 1526612 and missing_keys == 0 and not differences}
        (output / 'parity.json').write_text(json.dumps(result, indent=2) + '\n')
        if not result['exact_value_parity']:
            raise AssertionError(result)
        projection = ', '.join(map(quote, columns))
        destination = str(output / 'dbt_panel.parquet').replace("'", "''")
        con.execute(f"copy (select {projection} from candidate order by crossingid, year) to '{destination}' (format parquet)")
        with (output / 'dbt_panel.parquet').open('rb') as stream:
            result['export_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        (output / 'parity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
