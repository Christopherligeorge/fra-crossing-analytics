"""Statistical baselines for crossing-risk prediction (Day 12).

The conventional models the ML must beat (H2):

  - prevalence : predict the train-set base rate for everyone (null model).
  - exposure   : logistic regression on log1p(AADT x total daily trains).
                 This simple exposure reference does not reproduce FRA APS/GXAPS.
  - logistic   : regularized logistic regression on the full feature set.

All return a fitted object exposing predict_proba, so evaluate.evaluate works
uniformly across baselines and ML models.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from research.crossing_risk.features import make_preprocessor


class PrevalenceBaseline:
    """Predicts the training base rate for every row."""

    def fit(self, X, y):
        self.rate_ = float(np.asarray(y).mean())
        return self

    def predict_proba(self, X):
        p = np.full(len(X), self.rate_, dtype=float)
        return np.column_stack([1 - p, p])


class ExposureBaseline:
    """Logistic regression on a single log-exposure score (AADT x trains)."""

    def _score(self, X: pd.DataFrame) -> np.ndarray:
        aadt = pd.to_numeric(X["annualaveragedailytrafficcount"], errors="coerce").fillna(0)
        trains = (
            pd.to_numeric(X["totaldaylightthrutrains"], errors="coerce").fillna(0)
            + pd.to_numeric(X["totalnighttimethrutrains"], errors="coerce").fillna(0)
        )
        return np.log1p(aadt * trains).to_numpy().reshape(-1, 1)

    def fit(self, X, y):
        self.lr_ = LogisticRegression(class_weight="balanced", max_iter=1000)
        self.lr_.fit(self._score(X), y)
        return self

    def predict_proba(self, X):
        return self.lr_.predict_proba(self._score(X))


def _logistic() -> Pipeline:
    return Pipeline(
        [
            ("prep", make_preprocessor(scale=True)),
            ("lr", LogisticRegression(class_weight="balanced", max_iter=1000)),
        ]
    )


def fit_baselines(X, y) -> dict:
    """Fit and return the conventional baselines keyed by name."""
    models = {
        "prevalence": PrevalenceBaseline(),
        "exposure": ExposureBaseline(),
        "logistic": _logistic(),
    }
    for m in models.values():
        m.fit(X, y)
    return models
