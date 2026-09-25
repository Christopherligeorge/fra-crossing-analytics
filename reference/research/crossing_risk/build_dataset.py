"""Dataset builder for the crossing-risk research module.

Two entry points:

- build_feature_audit()  — Day 9 schema inspection (delegates to scripts/).
- build_modeling_dataset() — Day 11: the labeled crossing-year panel.

This is the legacy exploratory builder. It repeats current inventory predictors
across historical years without establishing historical crossing eligibility.
Temporal and state split masks do not resolve post-outcome predictor information.
Use release_data.py and scripts/run_crossing_research_release.py for the revised
research workflow. The legacy functions remain for reproducing old artifacts and
for shared feature definitions and strictly prior-year incident calculations.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.duckdb_tools import register_parquet_table  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "crossing_risk"

# Frozen legacy study window; this is not a statement about current source completeness.
YEAR_START, YEAR_END = 2014, 2023
# Prior-history features look back this many years before each label year. Incident
# data is loaded from YEAR_START - HISTORY_LOOKBACK so the earliest panel year
# (YEAR_START) has a full lookback window available.
HISTORY_LOOKBACK = 5

INVENTORY_URL = "https://data.transportation.gov/resource/m2f8-22s6.csv"
INCIDENT_URL = "https://data.transportation.gov/resource/7wn6-i5b9.csv"

# --- Feature groups (Day 16 splits these for the history ablation) -----------
# Exposure: traffic + train activity + speed (the FRA-formula drivers).
NUMERIC_EXPOSURE = [
    "annualaveragedailytrafficcount",
    "totaldaylightthrutrains",
    "totalnighttimethrutrains",
    "totaltransittrains",
    "maximumtimetablespeed",
]
# Infrastructure: track layout + physical warning-device counts.
NUMERIC_INFRA = [
    "numberofmaintracks",
    "numberofsidingtracks",
    "numberofyardtracks",
    "numberofindustrytracks",
    "numberoftransittracks",
    "numbercrossbuckassemblies",
    "countroadwaygatearms",
]
# Leakage-safe prior-incident history (Day 16). Computed in compute_prior_history
# using ONLY incident years strictly before the row's label year.
HISTORY_FEATURES = [
    "prior_incident_count_1yr",
    "prior_incident_count_3yr",
    "prior_incident_count_5yr",
    "years_since_last_incident",
    "prior_killed_5yr",
    "prior_injured_5yr",
]
# Leakage-safe spatial / neighborhood context (Day 16 H5). Derived in
# add_spatial_context from the already-leakage-safe prior_incident_count_5yr, so
# they inherit the strictly-before-Y guarantee. County = countycode (FIPS).
SPATIAL_FEATURES = [
    "crossing_density",  # # crossings in the county (static area exposure)
    "county_prior_incident_count_5yr",  # leave-one-out neighbor incidents, prior 5yr
    "county_prior_incident_rate_5yr",  # per-neighbor-crossing rate
    "state_prior_incident_rate_5yr",  # coarser regional prior rate
]
CATEGORICAL_FEATURES = [
    "statename",
    "crossingtype",
    "signsorsignals",
    "highwaypaved",
    "crossingilluminated",
    "whistleban",
]
# Backward-compat: the Day 11-15 inventory numeric predictor set (no history).
NUMERIC_FEATURES = NUMERIC_EXPOSURE + NUMERIC_INFRA
# countycode (FIPS) + countyname feed the spatial-context join key; not predictors themselves.
INVENTORY_COLS = (
    ["crossingid", "latitude", "longitude", "countycode", "countyname"]
    + NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)


def _socrata_csv(url: str, select: str, where: str | None, out: Path) -> Path:
    """Download a focused Socrata extract, paging past the 50k row cap."""
    out.parent.mkdir(parents=True, exist_ok=True)
    frames, offset, page = [], 0, 50000
    while True:
        params = {"$select": select, "$limit": page, "$offset": offset, "$order": ":id"}
        if where:
            params["$where"] = where
        r = requests.get(url, params=params, timeout=180)
        r.raise_for_status()
        chunk = pd.read_csv(io.StringIO(r.text))
        if chunk.empty:
            break
        frames.append(chunk)
        offset += page
        if len(chunk) < page:
            break
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    df.to_csv(out, index=False)
    return out


def _load_inventory() -> pd.DataFrame:
    out = DATA_DIR / "inventory_features.csv"
    # Re-download if the cached extract predates a column added to INVENTORY_COLS.
    if out.exists():
        cached = set(pd.read_csv(out, nrows=0).columns)
        if not set(INVENTORY_COLS).issubset(cached):
            out.unlink()
    if not out.exists():
        _socrata_csv(INVENTORY_URL, ",".join(INVENTORY_COLS), None, out)
    df = pd.read_csv(out, dtype={"crossingid": str, "countycode": str}, low_memory=False)
    return df.dropna(subset=["crossingid"]).drop_duplicates("crossingid")


def add_spatial_context(panel: pd.DataFrame) -> pd.DataFrame:
    """Add leakage-safe neighborhood / spatial-context features (H5).

    Requires columns crossingid, year, statename, prior_incident_count_5yr, and a
    `county_key` (FIPS countycode). Everything is derived from the already
    leakage-safe prior_incident_count_5yr, so no current/future incident leaks in.
    County / state neighbor counts are LEAVE-ONE-OUT (a crossing's own prior
    incidents are subtracted) so the feature measures the *neighborhood*, not self.
    """
    panel = panel.copy()
    # Static area exposure: how many crossings share this county.
    panel["crossing_density"] = panel.groupby("county_key")["crossingid"].transform("nunique")

    county_year = panel.groupby(["county_key", "year"])["prior_incident_count_5yr"].transform("sum")
    panel["county_prior_incident_count_5yr"] = county_year - panel["prior_incident_count_5yr"]
    panel["county_prior_incident_rate_5yr"] = panel["county_prior_incident_count_5yr"] / (
        panel["crossing_density"] - 1
    ).clip(lower=1)

    state_year = panel.groupby(["statename", "year"])["prior_incident_count_5yr"].transform("sum")
    state_cnt = panel.groupby("statename")["crossingid"].transform("nunique")
    panel["state_prior_incident_rate_5yr"] = (state_year - panel["prior_incident_count_5yr"]) / (
        state_cnt - 1
    ).clip(lower=1)
    return panel


def _load_incidents() -> pd.DataFrame:
    """Load incidents from YEAR_START - HISTORY_LOOKBACK through YEAR_END.

    The pre-window years (e.g. 2009-2013) are used ONLY to compute prior-history
    features for the earliest label years; they are not labeled themselves.
    """
    hist_start = YEAR_START - HISTORY_LOOKBACK
    out = DATA_DIR / f"incidents_{hist_start}_{YEAR_END}.csv"
    if not out.exists():
        where = f"date >= '{hist_start}-01-01' AND date <= '{YEAR_END}-12-31'"
        _socrata_csv(
            INCIDENT_URL,
            "gradecrossingid,date,crossinguserskilled,crossingusersinjured",
            where,
            out,
        )
    df = pd.read_csv(out, dtype={"gradecrossingid": str}, low_memory=False)
    df = df.dropna(subset=["gradecrossingid", "date"])
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df[(df["year"] >= hist_start) & (df["year"] <= YEAR_END)]


def compute_prior_history(cy: pd.DataFrame, panel_keys: pd.DataFrame) -> pd.DataFrame:
    """Leakage-safe prior-incident history for each (crossingid, year) key.

    `cy` is per-crossing-year incident counts (columns: crossingid, year,
    n_incidents, n_killed, n_injured) covering the full loaded range including
    pre-window years. For a row with label year Y, EVERY feature uses only
    incident years strictly < Y — current-year and future incidents are excluded.

    Returns panel_keys (crossingid, year) plus the six HISTORY_FEATURES.
    Crossings with no prior incidents get 0 counts and NaN years_since_last.
    """
    keys = panel_keys[["crossingid", "year"]].drop_duplicates()
    if cy.empty:
        out = keys.copy()
        for c in HISTORY_FEATURES:
            out[c] = 0.0
        out["years_since_last_incident"] = np.nan
        return out

    # Dense contiguous (crossing x year) grid for every crossing that ever had an
    # incident, so year-window shifts are well defined. Crossings never in `cy`
    # are absent here and fall through the left-merge as all-zero / NaN.
    crossings = cy["crossingid"].unique()
    y0 = int(cy["year"].min())
    y1 = int(keys["year"].max())
    grid = pd.MultiIndex.from_product(
        [crossings, range(y0, y1 + 1)], names=["crossingid", "year"]
    ).to_frame(index=False)
    g = grid.merge(cy, on=["crossingid", "year"], how="left").sort_values(["crossingid", "year"])
    for c in ["n_incidents", "n_killed", "n_injured"]:
        g[c] = g[c].fillna(0.0)

    grp = g.groupby("crossingid", sort=False)
    # shift(1) makes every window start at the PREVIOUS year -> strictly < Y.
    g["prior_incident_count_1yr"] = grp["n_incidents"].transform(lambda s: s.shift(1))
    g["prior_incident_count_3yr"] = grp["n_incidents"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).sum()
    )
    g["prior_incident_count_5yr"] = grp["n_incidents"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    g["prior_killed_5yr"] = grp["n_killed"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    g["prior_injured_5yr"] = grp["n_injured"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    # Most recent incident year strictly before Y, then the gap.
    g["_masked_year"] = g["year"].where(g["n_incidents"] > 0)
    last_prior = g.groupby("crossingid", sort=False)["_masked_year"].transform(
        lambda s: s.shift(1).ffill()
    )
    g["years_since_last_incident"] = g["year"] - last_prior

    out = keys.merge(g[["crossingid", "year"] + HISTORY_FEATURES], on=["crossingid", "year"], how="left")
    count_cols = [c for c in HISTORY_FEATURES if c != "years_since_last_incident"]
    out[count_cols] = out[count_cols].fillna(0.0)
    return out


def build_modeling_dataset(persist: bool = True) -> pd.DataFrame:
    """Build the labeled crossing-year panel. Returns the DataFrame.

    One row per (crossingid, year) for year in [YEAR_START, YEAR_END]. Label
    `had_incident` = 1 if >=1 incident at that crossing that year. Also carries
    `n_incidents`, `n_killed`, `n_injured` (current-year, for count/severity
    extensions) and the six leakage-safe HISTORY_FEATURES (prior years only).
    """
    inv = _load_inventory()
    inc = _load_incidents()  # covers YEAR_START - HISTORY_LOOKBACK .. YEAR_END

    # Per-crossing-year incident aggregates over the FULL loaded range (incl.
    # pre-window years, which feed prior-history but are never labeled).
    cy = (
        inc.groupby(["gradecrossingid", "year"])
        .agg(
            n_incidents=("date", "size"),
            n_killed=("crossinguserskilled", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
            n_injured=("crossingusersinjured", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
        )
        .reset_index()
        .rename(columns={"gradecrossingid": "crossingid"})
    )
    labels = cy[(cy["year"] >= YEAR_START) & (cy["year"] <= YEAR_END)]

    years = pd.DataFrame({"year": range(YEAR_START, YEAR_END + 1)})
    panel = inv.assign(_k=1).merge(years.assign(_k=1), on="_k").drop(columns="_k")
    panel = panel.merge(labels, on=["crossingid", "year"], how="left")
    for c in ["n_incidents", "n_killed", "n_injured"]:
        panel[c] = panel[c].fillna(0).astype(int)
    panel["had_incident"] = (panel["n_incidents"] > 0).astype(int)

    # Leakage-safe prior-incident history (strictly-before-Y windows).
    history = compute_prior_history(cy, panel[["crossingid", "year"]])
    panel = panel.merge(history, on=["crossingid", "year"], how="left")

    # Leakage-safe spatial / neighborhood context (H5), built from the history.
    panel["county_key"] = panel["countycode"].astype("string").fillna("UNKNOWN")
    panel = add_spatial_context(panel)

    if persist:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        pq = DATA_DIR / "crossing_year_panel.parquet"
        panel.to_parquet(pq, index=False)
        register_parquet_table(
            "crossing_year_panel",
            pq,
            source_id="fra_safety_data",
            dataset_name="crossing_year_panel",
        )
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return panel


def build_feature_audit() -> int:
    """Run the Day 9 feature audit (schema inspection + quality stats)."""
    from scripts.day9_crossing_risk_setup import main as run_audit

    return run_audit()


if __name__ == "__main__":
    df = build_modeling_dataset()
    pos = int(df["had_incident"].sum())
    print(f"Panel rows: {len(df):,}  ({YEAR_START}-{YEAR_END})")
    print(f"Crossings:  {df['crossingid'].nunique():,}")
    print(f"Positives:  {pos:,}  ({100 * pos / len(df):.3f}% base rate)")
    print(f"Killed:     {int(df['n_killed'].sum()):,}   Injured: {int(df['n_injured'].sum()):,}")
    have_hist = [c for c in HISTORY_FEATURES if c in df.columns]
    print(f"History features: {have_hist}")
    print(f"Rows with prior_incident_count_5yr>0: {int((df['prior_incident_count_5yr'] > 0).sum()):,}")
    have_spatial = [c for c in SPATIAL_FEATURES if c in df.columns]
    print(f"Spatial features: {have_spatial}")
    print(f"Counties: {df['county_key'].nunique():,}   "
          f"median crossings/county: {int(df.groupby('county_key')['crossingid'].nunique().median())}")
