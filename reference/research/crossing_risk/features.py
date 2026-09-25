"""Shared feature prep for the crossing-risk models (baselines + ML).

Keeps X/y construction and the sklearn preprocessor in one place so every model
agrees on the feature space. Day 16 adds named feature sets for the prior-history
ablation:

  - infrastructure_only            : track layout + physical warning devices + geo
  - infrastructure_exposure        : + traffic/train exposure  (the Day 11-15 set)
  - infrastructure_exposure_history: + leakage-safe prior-incident history

`year` is included in all sets (exogenous time, not part of the ablation), and the
categorical set (state + warning-device categories) is constant across sets.
"""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.crossing_risk.build_dataset import (
    CATEGORICAL_FEATURES,
    HISTORY_FEATURES,
    NUMERIC_EXPOSURE,
    NUMERIC_INFRA,
    SPATIAL_FEATURES,
)

CATEGORICAL = CATEGORICAL_FEATURES
TARGET = "had_incident"

FEATURE_SETS: dict[str, dict[str, list[str]]] = {
    "infrastructure_only": {
        "numeric": NUMERIC_INFRA + ["year"],
        "categorical": CATEGORICAL,
    },
    "infrastructure_exposure": {
        "numeric": NUMERIC_INFRA + NUMERIC_EXPOSURE + ["year"],
        "categorical": CATEGORICAL,
    },
    "infrastructure_exposure_history": {
        "numeric": NUMERIC_INFRA + NUMERIC_EXPOSURE + HISTORY_FEATURES + ["year"],
        "categorical": CATEGORICAL,
    },
    "infrastructure_exposure_history_spatial": {
        "numeric": NUMERIC_INFRA + NUMERIC_EXPOSURE + HISTORY_FEATURES + SPATIAL_FEATURES + ["year"],
        "categorical": CATEGORICAL,
    },
}
DEFAULT_SET = "infrastructure_exposure"  # the Day 11-15 feature space (unchanged)

# Backward-compat aliases used by Day 12-15 code.
NUMERIC = FEATURE_SETS[DEFAULT_SET]["numeric"]
FEATURES = NUMERIC + CATEGORICAL


def feature_columns(feature_set: str = DEFAULT_SET) -> tuple[list[str], list[str], list[str]]:
    """Return (numeric, categorical, all) column lists for a named feature set."""
    spec = FEATURE_SETS[feature_set]
    return spec["numeric"], spec["categorical"], spec["numeric"] + spec["categorical"]


def make_xy(df: pd.DataFrame, feature_set: str = DEFAULT_SET) -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) for a feature set. Numerics coerced, categoricals filled."""
    numeric, categorical, cols = feature_columns(feature_set)
    X = df.reindex(columns=cols).copy()
    for c in numeric:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    for c in categorical:
        X[c] = X[c].astype("string").fillna("NA")
    return X, df[TARGET].astype(int)


def make_preprocessor(feature_set: str = DEFAULT_SET, scale: bool = False) -> ColumnTransformer:
    """ColumnTransformer: median-impute numerics, one-hot rare-collapsed cats."""
    numeric, categorical, _ = feature_columns(feature_set)
    num_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    cat = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="NA")),
            ("ohe", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50)),
        ]
    )
    return ColumnTransformer(
        [("num", Pipeline(num_steps), numeric), ("cat", cat, categorical)],
        remainder="drop",
    )
