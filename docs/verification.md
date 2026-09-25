# Verification record — September 24, 2026

## Executed locally

- Full frozen-source build: 10 dbt models and 20 data tests passed.
- Full parity: 1,526,612 rows, identical crossing/year keys, all 55 reference columns
  equal under null-aware comparison. No unmatched keys or differing values.
- Python evaluation: all six AP values and all fields of 251,028 test predictions
  match the existing release at absolute tolerance 1e-12.
- HGB AP without history: 0.07661394857574302; with history: 0.10123781711931616.
- Fixture: 10 models, 19 data tests, and independent boundary assertions passed on
  82 synthetic crossing-years. The full-size test is deliberately disabled here.
- Every fact column has a dbt description; dbt documentation generated successfully.
- Streamlit AppTest: headline values and Texas/2024 filters passed. Browser preview
  inspected for readable layout and actual chart/table rendering.
- Mermaid diagram validated and rendered to SVG.

Machine-readable full parity and evaluation evidence is in
[`dashboard_data/facts.json`](../dashboard_data/facts.json). Successful dbt build/test
results are preserved separately from docs-generation results in
`target/full_build_run_results.json` and `target/fixture_build_run_results.json`.
GitHub Actions publishes the fixture build evidence as a workflow artifact.

## Review and limitations

A bounded independent source review found two evidence-binding defects. Dashboard
generation now reads hash-checked panel/prediction/metric exports, not an unbound
database. The build now preserves actual test results before docs generation overwrites
dbt's default result file. The affected end-to-end paths were rerun successfully.
All eight reference Python files were independently compared byte-for-byte with the
canonical research source and remain unchanged.

The legacy compact-date issue was diagnosed through full-column parity and preserved
explicitly; see [the limitation](legacy-date-parsing.md). This record is evidence of
engineering replication, not independent scientific validation or domain review.

The small CI test is not a full model-training run. Cloud dashboard hosting is not part
of the current release; the app runs locally from the public repository. Personal
mastery/independent reproduction by Christopher is not claimed.
