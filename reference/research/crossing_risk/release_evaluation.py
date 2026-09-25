"""Chronological crossing-risk benchmark with paired crossing-cluster inference.

Raw scores define ranking. Calibration candidates are fitted on one year and
selected on a later year; final outcomes are used only after that choice is fixed.
"""
from __future__ import annotations

from dataclasses import dataclass
import gc
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from research.crossing_risk.baseline_models import ExposureBaseline, PrevalenceBaseline, _logistic
from research.crossing_risk.build_dataset import HISTORY_FEATURES
from research.crossing_risk.calibration import fit_calibrator
from research.crossing_risk.features import feature_columns, make_xy
from research.crossing_risk.train_models import _to_category


MODEL_NAMES = (
    "prevalence", "exposure", "history_only", "full_logistic", "hgb_exposure", "hgb_history"
)
MODEL_LABELS = {
    "prevalence": "Training prevalence",
    "exposure": "Exposure logistic",
    "history_only": "History-only logistic",
    "full_logistic": "Infrastructure + exposure logistic",
    "hgb_exposure": "Infrastructure + exposure HGB",
    "hgb_history": "Infrastructure + exposure + history HGB",
}


@dataclass(frozen=True)
class Chronology:
    fit: tuple[int, ...]
    calibration: tuple[int, ...]
    selection: tuple[int, ...]
    test: tuple[int, ...]

    def as_dict(self) -> dict[str, list[int]]:
        return {name: list(getattr(self, name)) for name in ("fit", "calibration", "selection", "test")}

    def validate(self) -> None:
        previous = None
        for name, years in self.as_dict().items():
            if not years or years != sorted(set(years)):
                raise ValueError(f"{name} years must be nonempty, ordered, and unique")
            if previous is not None and min(years) <= previous:
                raise ValueError("Fit, calibration, selection, and test years must be strictly chronological")
            previous = max(years)


def chronological_split(panel: pd.DataFrame, chronology: Chronology) -> dict[str, pd.DataFrame]:
    chronology.validate()
    if panel[["crossingid", "year"]].isna().any().any():
        raise ValueError("Crossing IDs and years must be present")
    if panel.duplicated(["crossingid", "year"]).any():
        raise ValueError("Panel must have exactly one row per crossing/year")
    if not panel["had_incident"].isin([0, 1]).all():
        raise ValueError("had_incident must be binary")
    declared = {year for years in chronology.as_dict().values() for year in years}
    if set(panel.year.unique()) != declared:
        raise ValueError("Observed panel years must equal the declared chronology")
    out = {}
    for name, years in chronology.as_dict().items():
        part = panel.loc[panel.year.isin(years)].sort_values(["year", "crossingid"]).reset_index(drop=True)
        if set(part.year.unique()) != set(years) or part.had_incident.nunique() != 2:
            raise ValueError(f"{name} must contain all its declared years and both outcomes")
        out[name] = part
    return out


def select_calibration(
    calibration_scores, calibration_labels, selection_scores, selection_labels,
    *, calibration_years, selection_years, test_years, allow_calibration: bool = True,
):
    """This interface deliberately receives no final-test scores or outcomes."""
    if not (max(calibration_years) < min(selection_years) and max(selection_years) < min(test_years)):
        raise ValueError("Calibration selection must precede final test and follow calibration fitting")
    candidates = {"uncalibrated": None}
    if allow_calibration:
        for method in ("platt", "isotonic"):
            candidates[method] = fit_calibrator(method, calibration_scores, calibration_labels)
    rows = []
    for name, calibrator in candidates.items():
        probability = selection_scores if calibrator is None else calibrator.predict(selection_scores)
        rows.append({"method": name, "selection_brier": float(brier_score_loss(selection_labels, probability))})
    # Candidate insertion order is the predeclared tie-break: identity, Platt, isotonic.
    chosen = min(rows, key=lambda row: row["selection_brier"])["method"]
    for row in rows:
        row["selected"] = row["method"] == chosen
    return chosen, candidates[chosen], pd.DataFrame(rows)


def _model_and_features(name: str, panel: pd.DataFrame, hgb_iterations: int):
    feature_set = "infrastructure_exposure_history" if name == "hgb_history" else "infrastructure_exposure"
    if name == "history_only":
        model = Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("logistic", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=0)),
        ])
        return model, panel[HISTORY_FEATURES].apply(pd.to_numeric, errors="coerce")
    X, _ = make_xy(panel, feature_set)
    if name == "prevalence":
        return PrevalenceBaseline(), X
    if name == "exposure":
        return ExposureBaseline(), X
    if name == "full_logistic":
        return _logistic(), X
    model = HistGradientBoostingClassifier(
        learning_rate=0.1, max_iter=hgb_iterations, max_leaf_nodes=31,
        l2_regularization=1.0, categorical_features="from_dtype",
        class_weight="balanced", early_stopping=False, random_state=0,
    )
    return model, _to_category(X)


def feature_manifest() -> dict:
    exposure = feature_columns("infrastructure_exposure")[2]
    history = feature_columns("infrastructure_exposure_history")[2]
    return {
        "prevalence": [],
        "exposure": ["log1p(annualaveragedailytrafficcount * (totaldaylightthrutrains + totalnighttimethrutrains))"],
        "history_only": HISTORY_FEATURES,
        "full_logistic": exposure,
        "hgb_exposure": exposure,
        "hgb_history": history,
    }


def fit_release_models(panel: pd.DataFrame, chronology: Chronology, hgb_iterations: int = 150):
    """Fit six fixed models on shared rows; return score/probability audit tables."""
    missing = set(feature_columns("infrastructure_exposure_history")[2]) - set(panel.columns)
    if missing:
        raise ValueError(f"Release panel is missing declared predictors: {sorted(missing)}")
    splits = chronological_split(panel, chronology)
    keys = [c for c in ("crossingid", "year", "had_incident", "n_incidents", "statename") if c in panel]
    predictions = {part: splits[part][keys].copy() for part in ("calibration", "selection", "test")}
    selection_rows, runtimes = [], []
    choices = {}
    for name in MODEL_NAMES:
        started = time.perf_counter()
        print(f"Fitting {name} on {len(splits['fit']):,} crossing-years", flush=True)
        model, Xfit = _model_and_features(name, splits["fit"], hgb_iterations)
        model.fit(Xfit, splits["fit"].had_incident.to_numpy())
        del Xfit
        raw = {}
        for part in ("calibration", "selection"):
            _, X = _model_and_features(name, splits[part], hgb_iterations)
            raw[part] = model.predict_proba(X)[:, 1]
            del X
        chosen, calibrator, rows = select_calibration(
            raw["calibration"], splits["calibration"].had_incident.to_numpy(),
            raw["selection"], splits["selection"].had_incident.to_numpy(),
            calibration_years=chronology.calibration, selection_years=chronology.selection,
            test_years=chronology.test, allow_calibration=name != "prevalence",
        )
        rows.insert(0, "model", name)
        selection_rows.append(rows)
        choices[name] = chosen
        # The test is first predicted after this model's calibration choice is fixed.
        _, Xtest = _model_and_features(name, splits["test"], hgb_iterations)
        raw["test"] = model.predict_proba(Xtest)[:, 1]
        for part in ("calibration", "selection", "test"):
            predictions[part][f"score__{name}"] = raw[part]
            predictions[part][f"probability__{name}"] = (
                raw[part] if calibrator is None else calibrator.predict(raw[part])
            )
        elapsed = time.perf_counter() - started
        runtimes.append({"model": name, "runtime_seconds": elapsed})
        print(f"  {name}: calibration={chosen}; elapsed={elapsed:.1f}s", flush=True)
        del model, Xtest, raw, calibrator
        gc.collect()
    counts = {name: {"rows": len(part), "crossings": int(part.crossingid.nunique()),
                     "positive_crossing_years": int(part.had_incident.sum()),
                     "base_rate": float(part.had_incident.mean())} for name, part in splits.items()}
    return predictions, pd.concat(selection_rows, ignore_index=True), choices, pd.DataFrame(runtimes), counts


class RankingStatistics:
    """Pre-sort scores once for exact weighted AP and annual capacity ranking."""

    def __init__(self, crossing_ids, years, labels, scores):
        self.y = np.asarray(labels, dtype=float)
        self.scores = np.asarray(scores, dtype=float)
        self.years = np.asarray(years)
        ids = np.asarray(crossing_ids, dtype=str)
        if not np.isfinite(self.scores).all() or not np.isin(self.y, [0, 1]).all():
            raise ValueError("Ranking requires finite scores and binary labels")
        if not (len(ids) == len(self.years) == len(self.y) == len(self.scores)):
            raise ValueError("Ranking inputs must have matching lengths")
        if len(self.y) == 0:
            raise ValueError("Ranking inputs must be nonempty")
        self.ap_order = np.argsort(-self.scores, kind="stable")
        ordered_scores = self.scores[self.ap_order]
        self.group_ends = np.r_[np.flatnonzero(np.diff(ordered_scores)), len(self.y) - 1]
        self.year_orders = []
        for year in np.unique(self.years):
            indices = np.flatnonzero(self.years == year)
            order = np.lexsort((ids[indices], -self.scores[indices]))
            self.year_orders.append(indices[order])

    def average_precision(self, weights=None) -> float:
        weights = np.ones(len(self.y)) if weights is None else np.asarray(weights)
        w = weights[self.ap_order]
        positives = np.cumsum(w * self.y[self.ap_order])[self.group_ends]
        population = np.cumsum(w)[self.group_ends]
        if positives[-1] <= 0:
            return float("nan")
        precision = np.divide(positives, population, out=np.zeros_like(positives, dtype=float), where=population > 0)
        return float(np.sum(np.diff(np.r_[0.0, positives]) * precision) / positives[-1])

    def capture(self, weights=None, fraction: float = 0.1) -> float:
        """Select ceil(fraction * population) within each year, including in replicates."""
        if not 0 < fraction <= 1:
            raise ValueError("Capacity fraction must be in (0, 1]")
        weights = np.ones(len(self.y)) if weights is None else np.asarray(weights)
        positives = float(np.dot(weights, self.y))
        if positives <= 0:
            return float("nan")
        captured = 0.0
        for order in self.year_orders:
            w = weights[order]
            capacity = int(np.ceil(fraction * w.sum()))
            before = np.cumsum(w) - w
            admitted = np.clip(capacity - before, 0, w)
            captured += float(np.dot(admitted, self.y[order]))
        return captured / positives


def crossing_cluster_weights(crossing_ids, rng: np.random.Generator) -> np.ndarray:
    """Exact multinomial cluster bootstrap: all years share crossing multiplicity."""
    unique, inverse = np.unique(np.asarray(crossing_ids, dtype=str), return_inverse=True)
    draws = rng.integers(0, len(unique), size=len(unique))
    counts = np.bincount(draws, minlength=len(unique))
    return counts[inverse]


def evaluate_predictions(predictions: pd.DataFrame, choices: dict[str, str]) -> pd.DataFrame:
    y = predictions.had_incident.to_numpy()
    null = predictions["probability__prevalence"].to_numpy()
    null_brier = float(brier_score_loss(y, null))
    rows = []
    for name in MODEL_NAMES:
        score = predictions[f"score__{name}"].to_numpy()
        probability = predictions[f"probability__{name}"].to_numpy()
        ranking = RankingStatistics(predictions.crossingid, predictions.year, y, score)
        ap = float(average_precision_score(y, score))
        if not np.isclose(ap, ranking.average_precision(), atol=1e-12):
            raise AssertionError("Independent weighted AP implementation disagrees with sklearn")
        brier = float(brier_score_loss(y, probability))
        rows.append({
            "model": name, "model_label": MODEL_LABELS[name], "calibration": choices[name],
            "n_crossing_years": len(y), "n_crossings": int(predictions.crossingid.nunique()),
            "positive_crossing_years": int(y.sum()), "base_rate": float(y.mean()),
            "average_precision": ap, "roc_auc": float(roc_auc_score(y, score)),
            "brier": brier, "brier_uncalibrated": float(brier_score_loss(y, score)),
            "training_prevalence_brier": null_brier, "brier_skill_vs_prevalence": 1 - brier / null_brier,
            "top10_positive_year_capture": ranking.capture(),
            "top20_positive_year_capture": ranking.capture(fraction=0.2),
        })
    return pd.DataFrame(rows)


def paired_cluster_bootstrap(predictions: pd.DataFrame, n_bootstrap: int = 200, seed: int = 20260906):
    if n_bootstrap < 2:
        raise ValueError("At least two bootstrap replicates are required")
    y = predictions.had_incident.to_numpy()
    rankings = {name: RankingStatistics(predictions.crossingid, predictions.year, y, predictions[f"score__{name}"])
                for name in MODEL_NAMES if f"score__{name}" in predictions}
    rng = np.random.default_rng(seed)
    clusters, inverse = np.unique(predictions.crossingid.to_numpy(dtype=str), return_inverse=True)
    rows = []
    for replicate in range(n_bootstrap):
        counts = np.bincount(rng.integers(0, len(clusters), size=len(clusters)), minlength=len(clusters))
        weights = counts[inverse]
        if np.dot(weights, y) == 0:
            raise ValueError("Bootstrap generated no positives; inference is not supportable at this sample size")
        for name, ranking in rankings.items():
            rows.append({"replicate": replicate, "model": name,
                         "average_precision": ranking.average_precision(weights),
                         "top10_positive_year_capture": ranking.capture(weights)})
        if (replicate + 1) % 50 == 0:
            print(f"Cluster bootstrap: {replicate + 1}/{n_bootstrap}", flush=True)
    replicates = pd.DataFrame(rows)
    result = []
    for metric in ("average_precision", "top10_positive_year_capture"):
        table = replicates.pivot(index="replicate", columns="model", values=metric)
        point = {name: (ranking.average_precision() if metric == "average_precision" else ranking.capture())
                 for name, ranking in rankings.items()}
        contrasts = [(name, "") for name in rankings]
        if "hgb_history" in rankings:
            contrasts += [("hgb_history", ref) for ref in ("hgb_exposure", "history_only", "full_logistic") if ref in rankings]
        for name, reference in contrasts:
            values = table[name].to_numpy()
            estimate = point[name]
            if reference:
                values = values - table[reference].to_numpy()
                estimate -= point[reference]
            lower, upper = np.quantile(values, [0.025, 0.975])
            result.append({"metric": metric, "model": name, "reference_model": reference,
                           "estimate": estimate, "ci_lower": lower, "ci_upper": upper,
                           "n_bootstrap": n_bootstrap, "confidence_level": 0.95,
                           "method": "paired_crossing_cluster_percentile_bootstrap",
                           "includes_model_refitting": False})
    return pd.DataFrame(result), replicates


def risk_deciles(predictions: pd.DataFrame) -> pd.DataFrame:
    """Annual equal-capacity bins rank raw scores; ID tie-break is row-order invariant."""
    rows = []
    for name in MODEL_NAMES:
        ranking = RankingStatistics(predictions.crossingid, predictions.year, predictions.had_incident,
                                    predictions[f"score__{name}"])
        for order in ranking.year_orders:
            bounds = np.ceil(np.arange(1, 11) * len(order) / 10).astype(int)
            start = 0
            for decile, end in enumerate(bounds, start=1):
                part = predictions.iloc[order[start:end]]
                rows.append({"model": name, "year": int(predictions.year.iloc[order[0]]),
                             "risk_decile": 11 - decile, "n_crossing_years": len(part),
                             "positive_crossing_years": int(part.had_incident.sum()),
                             "mean_probability": float(part[f"probability__{name}"].mean()),
                             "observed_rate": float(part.had_incident.mean())})
                start = end
    return pd.DataFrame(rows)


def subgroup_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Describe heldout-year/state variation; these are not geographic holdouts."""
    rows = []
    for group_column in ("year", "statename"):
        if group_column not in predictions:
            continue
        for group_value, part in predictions.groupby(group_column, dropna=False):
            y = part.had_incident.to_numpy()
            for name in MODEL_NAMES:
                score = part[f"score__{name}"].to_numpy()
                probability = part[f"probability__{name}"].to_numpy()
                both_classes = 0 < y.sum() < len(y)
                rows.append({"group_type": group_column, "group": str(group_value), "model": name,
                             "n_crossing_years": len(y), "positive_crossing_years": int(y.sum()),
                             "base_rate": float(y.mean()),
                             "average_precision": float(average_precision_score(y, score)) if both_classes else np.nan,
                             "brier": float(brier_score_loss(y, probability)),
                             "interpretation": "descriptive temporal-test subgroup; not a geographic holdout"})
    return pd.DataFrame(rows)


def plot_release(predictions, metrics, intervals, deciles, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 180, "figure.facecolor": "white"})
    years = f"{int(predictions.year.min())}–{int(predictions.year.max())}"
    ci = intervals[(intervals.metric == "average_precision") & (intervals.reference_model == "")].set_index("model")
    m = metrics.set_index("model").loc[list(MODEL_NAMES)]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    point = m.average_precision.to_numpy()
    lower = ci.loc[list(MODEL_NAMES)].ci_lower.to_numpy()
    upper = ci.loc[list(MODEL_NAMES)].ci_upper.to_numpy()
    colors = ["#c4cccd"] * 4 + ["#548491", "#087e83"]
    positions = np.arange(len(m))
    ax.barh(positions, point, color=colors)
    ax.hlines(positions, lower, upper, color="#273c40", lw=1)
    ax.vlines(lower, positions - 0.08, positions + 0.08, color="#273c40", lw=1)
    ax.vlines(upper, positions - 0.08, positions + 0.08, color="#273c40", lw=1)
    ax.set_yticks(positions, m.model_label)
    ax.invert_yaxis()
    ax.set_xlabel("Average precision (raw scores)")
    ax.set_title(f"Ranking performance in {years}", loc="left", fontweight="bold")
    fig.text(0.01, 0.01, "Bars: point estimates. Whiskers: 95% crossing-cluster bootstrap intervals; fitted models held fixed.", fontsize=8)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_dir / "average_precision.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.plot([0, 1], [0, 1], "--", color="#a0a7a8", label="Proportional capture")
    for name, color in (("exposure", "#929d9e"), ("history_only", "#bd7b3a"),
                        ("hgb_exposure", "#548491"), ("hgb_history", "#087e83")):
        d = deciles[deciles.model == name].groupby("risk_decile")[
            ["n_crossing_years", "positive_crossing_years"]].sum().sort_index(ascending=False)
        x = np.r_[0, d.n_crossing_years.cumsum() / d.n_crossing_years.sum()]
        y = np.r_[0, d.positive_crossing_years.cumsum() / d.positive_crossing_years.sum()]
        ax.plot(x, y, "o-", ms=3, color=color, label=MODEL_LABELS[name])
    ax.set(xlabel="Share of crossing-years prioritized within each year", ylabel="Share of positive crossing-years captured",
           xlim=(0, 1), ylim=(0, 1))
    ax.set_title(f"Annual screening capacity and capture, {years}", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.text(0.01, 0.01, "Raw-score ranking; ties use crossing ID. Positives are crossing-years with ≥1 reported incident.", fontsize=8)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_dir / "risk_capture.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    d = deciles[deciles.model == "hgb_history"]
    bins = []
    for _, part in d.groupby("risk_decile"):
        bins.append((np.average(part.mean_probability, weights=part.n_crossing_years),
                     part.positive_crossing_years.sum() / part.n_crossing_years.sum()))
    bins = np.asarray(bins)
    limit = max(bins.max() * 1.1, 0.01)
    ax.plot([0, limit], [0, limit], "--", color="#a0a7a8", label="Perfect calibration")
    ax.plot(bins[:, 0], bins[:, 1], "o-", color="#087e83", label="HGB + history; selected calibration")
    ax.set(xlabel="Mean calibrated probability", ylabel="Observed positive-year rate", xlim=(0, limit), ylim=(0, limit))
    ax.set_title(f"Probability calibration in {years}", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    fig.text(0.01, 0.01, "Bins use annual raw-score deciles. Calibrators fit before selection; choice fixed before final scoring.", fontsize=8)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_dir / "calibration.png")
    plt.close(fig)
