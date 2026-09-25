"""Probability calibration + risk stratification (Day 16).

The Day 13 model ranks well but is not probability-calibrated (balanced class
weights inflate predicted risk). This module recalibrates predicted probabilities
on a held-out calibration set and quantifies the improvement.

  - Platt / sigmoid : logistic fit on the log-odds of the base probabilities.
  - Isotonic        : sklearn IsotonicRegression (monotonic, non-parametric).

Both are fit on (base_prob, y) from a calibration split disjoint from the data
that trained the base model and from the test set. Also provides Brier
comparison, calibration-curve data, and risk-decile analysis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss


def _logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


class PlattCalibrator:
    """Sigmoid recalibration: p_cal = sigmoid(a * logit(p_base) + b)."""

    def fit(self, prob, y):
        self.lr_ = LogisticRegression(max_iter=1000)
        self.lr_.fit(_logit(prob).reshape(-1, 1), np.asarray(y).astype(int))
        return self

    def predict(self, prob):
        return self.lr_.predict_proba(_logit(prob).reshape(-1, 1))[:, 1]


class IsotonicCalibrator:
    """Monotonic non-parametric recalibration."""

    def fit(self, prob, y):
        self.ir_ = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.ir_.fit(np.asarray(prob, dtype=float), np.asarray(y).astype(int))
        return self

    def predict(self, prob):
        return np.clip(self.ir_.predict(np.asarray(prob, dtype=float)), 0.0, 1.0)


def fit_calibrator(method: str, prob, y):
    """method in {'platt', 'sigmoid', 'isotonic'}."""
    if method in ("platt", "sigmoid"):
        return PlattCalibrator().fit(prob, y)
    if method == "isotonic":
        return IsotonicCalibrator().fit(prob, y)
    raise ValueError(f"unknown calibration method: {method!r}")


def calibration_table(y, prob, n_bins: int = 10) -> pd.DataFrame:
    """Quantile calibration curve: mean predicted vs observed rate per bin."""
    frac_pos, mean_pred = calibration_curve(
        np.asarray(y).astype(int), np.asarray(prob, dtype=float), n_bins=n_bins, strategy="quantile"
    )
    return pd.DataFrame({"mean_predicted": mean_pred, "observed_rate": frac_pos})


def compare_brier(y, prob_before, prob_after) -> dict:
    y = np.asarray(y).astype(int)
    before = float(brier_score_loss(y, np.asarray(prob_before, dtype=float)))
    after = float(brier_score_loss(y, np.asarray(prob_after, dtype=float)))
    return {"brier_before": before, "brier_after": after, "brier_reduction": before - after}


def risk_decile_table(y, prob, n_deciles: int = 10) -> pd.DataFrame:
    """Rank rows by predicted risk into deciles (10 = highest) and report, per
    decile: population, incidents, observed rate, mean predicted, lift over the
    base rate, and cumulative share of incidents / population from the top down.

    Tests whether the top deciles capture a disproportionate share of incidents.
    """
    df = pd.DataFrame({"y": np.asarray(y).astype(int), "p": np.asarray(prob, dtype=float)})
    # rank(method='first') breaks ties so qcut always yields n_deciles bins even
    # when many predictions are identical.
    df["decile"] = pd.qcut(df["p"].rank(method="first"), n_deciles, labels=False) + 1
    base = df["y"].mean()
    total_inc = df["y"].sum()
    g = (
        df.groupby("decile")
        .agg(n=("y", "size"), incidents=("y", "sum"), mean_pred=("p", "mean"), observed_rate=("y", "mean"))
        .sort_index(ascending=False)  # decile 10 (highest risk) first
    )
    g["lift"] = g["observed_rate"] / base if base > 0 else np.nan
    g["share_of_incidents"] = g["incidents"] / total_inc if total_inc > 0 else np.nan
    g["cum_share_incidents"] = g["share_of_incidents"].cumsum()
    g["cum_share_population"] = g["n"].cumsum() / g["n"].sum()
    return g.reset_index().rename(columns={"decile": "risk_decile"})
