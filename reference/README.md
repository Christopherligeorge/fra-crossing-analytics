# Unchanged reference evaluation code

These eight Python files are a dependency subset copied from the completed InfraRail
crossing-risk research project, September 6, 2026 release. They are retained unchanged
to prevent an engineering migration from also changing the scientific evaluator.

`research/crossing_risk/build_dataset.py` is the older exploratory builder. Its
constants/shared history definitions are imported here; its legacy panel-building
entry point is **not** used. The new panel is built only by dbt. Imports transitively
require `tools/duckdb_tools.py` and `app/config.py`; no private `.env` is included.

`release_evaluation.py` owns the current fixed six-model comparison. The original
fully pinned research environment is retained in `requirements-research-lock.txt`.
The project-level requirements add dbt and Streamlit for the engineering deliverable.

Do not edit these files to make parity pass. Treat a genuine scientific correction
as a separate versioned research change, not a silent refactor.
