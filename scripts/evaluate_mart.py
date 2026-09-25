"""Run unchanged research evaluation on the parity-checked dbt export."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from research.crossing_risk.release_evaluation import Chronology, fit_release_models, evaluate_predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    parity = json.loads((ROOT / 'artifacts/parity.json').read_text())
    if not parity['exact_value_parity']:
        raise ValueError('Full panel parity must pass before evaluation')
    with (ROOT / 'artifacts/dbt_panel.parquet').open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != parity['export_sha256']:
            raise ValueError('Export changed since full-panel parity was checked')
    panel = pd.read_parquet(ROOT / 'artifacts/dbt_panel.parquet')
    chronology = Chronology(tuple(range(2014, 2022)), (2022,), (2023,), (2024, 2025))
    with threadpool_limits(limits=4):
        predictions, calibration, choices, runtimes, counts = fit_release_models(panel, chronology, 150)
        metrics = evaluate_predictions(predictions['test'], choices)
    expected = pd.read_csv(args.release / 'metrics.csv').set_index('model')
    actual = metrics.set_index('model')
    np.testing.assert_allclose(actual.loc[expected.index, 'average_precision'], expected.average_precision, rtol=0, atol=1e-12)
    original = pd.read_parquet(args.release / 'predictions.parquet').sort_values(['year', 'crossingid']).reset_index(drop=True)
    candidate = predictions['test'].sort_values(['year', 'crossingid']).reset_index(drop=True)
    pd.testing.assert_frame_equal(candidate, original, check_dtype=False, check_exact=False, rtol=0, atol=1e-12)
    output = ROOT / 'artifacts/evaluation'
    output.mkdir(exist_ok=True)
    metrics.to_csv(output / 'metrics.csv', index=False)
    candidate.to_parquet(output / 'predictions.parquet', index=False)
    calibration.to_csv(output / 'calibration_selection.csv', index=False)
    with (output / 'predictions.parquet').open('rb') as stream:
        predictions_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    with (output / 'metrics.csv').open('rb') as stream:
        metrics_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    result = {'all_six_ap_match': True, 'all_test_predictions_match': True, 'absolute_tolerance': 1e-12,
              'panel_sha256': parity['export_sha256'], 'predictions_sha256': predictions_hash,
              'metrics_sha256': metrics_hash,
              'hgb_exposure_ap': float(actual.loc['hgb_exposure', 'average_precision']),
              'hgb_history_ap': float(actual.loc['hgb_history', 'average_precision']),
              'selected_calibration': choices, 'split_counts': counts}
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
