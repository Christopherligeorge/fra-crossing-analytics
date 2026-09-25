"""Publish small summaries of the verified mart and reproduced predictions."""
import json
import hashlib
import math
from pathlib import Path
import shutil
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def summarize(predictions, model, year, state):
    budget, captured = 0, 0
    for _, annual in predictions.groupby('year'):
        ordered = annual.sort_values([f'score__{model}', 'crossingid'], ascending=[False, True])
        annual_budget = math.ceil(len(ordered) * .1)
        budget += annual_budget
        captured += int(ordered.head(annual_budget).had_incident.sum())
    positives = int(predictions.had_incident.sum())
    return dict(model=model, year=year, state=state, crossing_years=len(predictions),
                positive_crossing_years=positives, selected_crossing_years=budget,
                captured_positive_years=captured, capture=captured / positives if positives else None)


def main():
    evidence = json.loads((ROOT / 'artifacts/evaluation/verification.json').read_text())
    parity = json.loads((ROOT / 'artifacts/parity.json').read_text())
    if not evidence['all_test_predictions_match'] or not parity['exact_value_parity']:
        raise ValueError('Publish dashboard summaries only after full parity and evaluation pass')
    if evidence['panel_sha256'] != parity['export_sha256']:
        raise ValueError('Evaluation and panel parity refer to different builds')
    with (ROOT / 'artifacts/evaluation/predictions.parquet').open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != evidence['predictions_sha256']:
            raise ValueError('Predictions changed after verification')
    destination = ROOT / 'dashboard_data'
    for filename, expected_hash in [('dbt_panel.parquet', parity['export_sha256']),
                                     ('evaluation/metrics.csv', evidence['metrics_sha256'])]:
        with (ROOT / 'artifacts' / filename).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_hash:
                raise ValueError(f'Verified artifact changed: {filename}')
    destination.mkdir(exist_ok=True)
    with duckdb.connect() as con:
        con.from_parquet(str(ROOT / 'artifacts/dbt_panel.parquet')).create_view('fct_crossing_year')
        panel = con.execute('select year, statename as state, count(*) as crossing_years, sum(had_incident) as positive_crossing_years from fct_crossing_year group by year, statename order by year, statename').df()
        facts = con.execute('select count(*) as crossing_years, count(distinct crossingid) as crossings, sum(had_incident) as positive_crossing_years from fct_crossing_year').df().iloc[0].to_dict()
    panel.to_csv(destination / 'panel.csv', index=False)
    predictions = pd.read_parquet(ROOT / 'artifacts/evaluation/predictions.parquet')
    rows = []
    for model in ['hgb_exposure', 'hgb_history']:
        rows.append(summarize(predictions, model, 'All', 'All'))
        for year, group in predictions.groupby('year'):
            rows.append(summarize(group, model, str(year), 'All'))
        for state, group in predictions.groupby('statename', dropna=False):
            rows.append(summarize(group, model, 'All', str(state)))
        for (year, state), group in predictions.groupby(['year', 'statename'], dropna=False):
            rows.append(summarize(group, model, str(year), str(state)))
    pd.DataFrame(rows).to_csv(destination / 'capture.csv', index=False)
    metrics = pd.read_csv(ROOT / 'artifacts/evaluation/metrics.csv').set_index('model')
    for row in rows:
        if row['state'] == 'All' and row['year'] == 'All':
            assert abs(row['capture'] - metrics.loc[row['model'], 'top10_positive_year_capture']) < 1e-12
    (destination / 'facts.json').write_text(json.dumps({**{k: int(v) for k, v in facts.items()},
        'source_release': '2026-09-06', 'test_years': [2024, 2025], 'kind': 'verified full-data snapshot',
        'parity': parity, 'evaluation': evidence}, indent=2) + '\n')
    shutil.copyfile(ROOT / 'artifacts/evaluation/metrics.csv', destination / 'metrics.csv')
    print('Exported verified dashboard summaries; no synthetic fixture results included.')


if __name__ == '__main__':
    main()
