"""ML models for crossing-risk prediction (Day 13).

Gradient-boosted trees (sklearn HistGradientBoostingClassifier) test H2 (beat
baselines) and H4 (nonlinear device x exposure interactions, which trees capture
without manual interaction terms). Class imbalance is handled with balanced
sample weights; probabilities stay usable for PR-AUC / calibration.

HGB handles NaN and native categoricals directly, so no one-hot/impute step is
needed — categoricals are cast to pandas `category` dtype and passed through.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.utils.class_weight import compute_sample_weight

from research.crossing_risk.features import CATEGORICAL


def _to_category(X):
    X = X.copy()
    for c in CATEGORICAL:
        X[c] = X[c].astype("category")
    return X


def _hgb() -> Pipeline:
    return Pipeline(
        [
            ("cast", FunctionTransformer(_to_category)),
            (
                "hgb",
                HistGradientBoostingClassifier(
                    learning_rate=0.1,
                    max_iter=300,
                    max_leaf_nodes=63,
                    l2_regularization=1.0,
                    categorical_features="from_dtype",
                    early_stopping=True,
                    validation_fraction=0.1,
                    random_state=0,
                ),
            ),
        ]
    )


def train(X, y, split: str = "temporal") -> Pipeline:
    """Train the gradient-boosted model. `split` is metadata only (the caller
    has already carved out the train rows); kept for signature stability."""
    model = _hgb()
    sw = compute_sample_weight(class_weight="balanced", y=np.asarray(y))
    model.fit(X, y, hgb__sample_weight=sw)
    return model
