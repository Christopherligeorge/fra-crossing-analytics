# Decisions worth being able to explain

## Grain and time

The fact table's grain is one eligible crossing per prediction year. Neither one
inventory revision nor one report is a fact-table row. Joining raw reports directly
would multiply inventory rows and change model weights. Reports are aggregated first.

`stg_` models standardize source identities and dates. `int_` models implement reusable
business rules. `fct_` stores observations/measures at a declared grain; `dim_` stores
identities used to join them. Here crossing attributes change over time, so they live
on the year-specific fact, not on a misleading current-state dimension.

Revision periods use `(revision_date, next_revision_date]` for the January 1 cutoff.
The open left edge means a revision exactly on January 1 is too late. Conflict and
closed rows remain in the period calculation so a later bad row cannot resurrect
an older eligible revision. All crossing purposes are retained.

## Why staging keeps raw numeric strings

The frozen Python builder detects same-date disagreements before casting. `02` and
`2` are different source claims under that contract even if numerically equivalent.
Changing the policy would change the research cohort. We preserve raw fields until
that decision, then convert invalid/negative numeric predictors to null and mask
future-dated measurements. Null means unknown; it is not replaced by zero exposure.

## Why history is not a window over eligible rows

A crossing may close and reopen. Reports during a gap in eligibility still contribute
to later histories. SQL joins the full crossing/report-year aggregate using `report
year < prediction year`; conditional sums implement calendar-year windows. Recency
uses all observed prior reports, even those older than five years. Its observation
window begins in 2009. Outcome-year casualties and reports must never be predictors.

## Relationships do not establish cohort eligibility

The identity dimension contains the union of inventory/report IDs, so a report at a
private or closed crossing is not treated as an invalid foreign key. The relationship
test checks identity integrity, not inventory linkage. The report-join audit separately
counts unmatched reports. Missing IDs/dates are retained in staging for inspection,
but do not enter annual aggregates; duplicate report keys fail the build.

## Materialization and reproducibility

Models are tables: the 1.1 GB raw vintage is read once per staging model, and reviewers
can inspect intermediate results. The revision-period join avoids expanding every raw
revision across all years. Full rebuilds are intentional; an incremental design would
need explicit correction/backfill rules before it could safely replace this approach.

CI uses 82 synthetic crossing-years with hand-computed boundary expectations. It tests
behavior, not the published cohort size. The separate full build verifies source hashes,
1,526,612 rows, every key and all 55 reference columns, then reruns the fixed evaluator.
Passing CI alone never certifies full-data parity. No tests are downloaded at runtime.

## Python boundary

`reference/` is an unchanged dependency subset of the prior research code. It is not a
second new model implementation. The bridge exports the checked dbt fact to Parquet,
renaming `crossing_id` to the evaluator's historical `crossingid` contract. Python keeps
the original splits: fit 2014–2021, calibration 2022, selection 2023, test 2024–2025.
The test years were already examined in the original study; they are not new holdouts.

## Sources and access

- Historical Form 71: https://data.transportation.gov/resource/vhwz-raag.csv
- Current Form 71: https://data.transportation.gov/resource/m2f8-22s6.csv
- Form 57 reports: https://data.transportation.gov/resource/7wn6-i5b9.csv

The frozen manifest contains the exact paginated download URLs, selected fields,
filters, retrieval times and SHA-256 hashes. The live endpoints can change: downloading
them today is not necessarily the frozen vintage. Full replication uses the original
local release directory or the checksum-pinned GitHub release asset; raw files are not
in Git history. A clean clone can run CI and
the genuine-results dashboard without those files. Hash verification must fail rather
than silently accept a newer vintage. No paid APIs or accounts are needed for local use.

Implementation references: [dbt-duckdb source configuration](https://github.com/duckdb/dbt-duckdb),
[DuckDB CSV loading](https://duckdb.org/docs/stable/data/csv/overview), and
[Streamlit app tests](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
