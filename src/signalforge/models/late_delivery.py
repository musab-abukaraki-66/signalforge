"""Late-delivery risk model.

TARGET: ``is_late`` = delivered date later than the estimated delivery date (day resolution),
for delivered orders with both dates.

PREDICTION TIME: when the order is placed (purchase). Every feature below is known then:
  - purchase month / weekday / hour                      (purchase timestamp)
  - estimated_days = estimated delivery date - purchase  (the promise shown to the customer)
  - n_items, n_sellers, items_value, freight_value, freight_ratio   (basket at checkout)
  - total_weight_g, total_volume_cm3                     (product catalogue attributes)
  - customer_state, primary_seller_state, same_state     (addresses)
  - primary_category, main_payment_type, max_installments (basket / chosen payment)
EXCLUDED on purpose (post-outcome or not available at purchase): delivered_at, carrier_at,
delivery_days, delay_days, review_score, approved_at, order_status.

LIMITATIONS handled elsewhere: only delivered orders have a label, so the latest purchases
(still in transit at extract time) are missing, which biases the end of the time range.
"""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = [
    "estimated_days",
    "n_items",
    "n_sellers",
    "items_value",
    "freight_value",
    "freight_ratio",
    "total_weight_g",
    "total_volume_cm3",
    "max_installments",
    "purchase_month_num",
    "purchase_dow",
    "purchase_hour",
    "same_state",
]
CATEGORICAL = ["customer_state", "primary_seller_state", "primary_category", "main_payment_type"]
FEATURES = NUMERIC + CATEGORICAL
TARGET = "is_late"
FEATURE_SQL = """
SELECT order_id, purchased_at, is_late::INT AS is_late,
       estimated_days, n_items, n_sellers, items_value, freight_value,
       freight_value / nullif(items_value, 0) AS freight_ratio,
       total_weight_g, total_volume_cm3, max_installments,
       month(purchased_at) AS purchase_month_num, dayofweek(purchased_at) AS purchase_dow,
       hour(purchased_at) AS purchase_hour,
       (primary_seller_state = customer_state)::INT AS same_state,
       customer_state, primary_seller_state, primary_category, main_payment_type
FROM gold.fact_order
WHERE is_late IS NOT NULL AND n_items > 0
ORDER BY purchased_at, order_id
"""


@dataclass(frozen=True)
class TrainSettings:
    train_frac: float = 0.6
    val_frac: float = 0.2  # remainder is the test set
    seed: int = 42
    min_group_size: int = 30  # segments smaller than this are not reported
    segment_top_n: int = 8
    recall_target: float = 0.5  # operating threshold: highest precision with val recall >= target


def load_dataset(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(FEATURE_SQL).df()


def chronological_split(
    df: pd.DataFrame, s: TrainSettings
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rows are sorted by purchase time; earlier rows train, later rows validate/test."""
    df = df.sort_values(["purchased_at", "order_id"]).reset_index(drop=True)
    n = len(df)
    i, j = int(n * s.train_frac), int(n * (s.train_frac + s.val_frac))
    return df.iloc[:i], df.iloc[i:j], df.iloc[j:]


def _preprocessor(scale: bool) -> ColumnTransformer:
    num_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            ("num", Pipeline(num_steps), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL),
        ]
    )


def candidate_models(seed: int) -> dict[str, Pipeline]:
    return {
        "baseline_prior": Pipeline(
            [("prep", _preprocessor(False)), ("clf", DummyClassifier(strategy="prior"))]
        ),
        "logistic_regression": Pipeline(
            [
                ("prep", _preprocessor(True)),
                (
                    "clf",
                    LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed),
                ),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            [
                ("prep", _preprocessor(False)),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_depth=4, learning_rate=0.05, max_iter=200, random_state=seed
                    ),
                ),
            ]
        ),
    }


def _metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    pred = p >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)),
        "late_rate": float(y.mean()),
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
        "brier": float(brier_score_loss(y, p)),
        "threshold": float(threshold),
        "precision": float(tp / (tp + fp)) if tp + fp else None,
        "recall": float(tp / (tp + fn)) if tp + fn else None,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def pick_threshold(y_val: np.ndarray, p_val: np.ndarray, recall_target: float) -> float:
    """Highest-precision threshold on VALIDATION data that still reaches the recall target."""
    prec, rec, thr = precision_recall_curve(y_val, p_val)
    ok = np.flatnonzero(rec[:-1] >= recall_target)
    if len(ok) == 0:
        return float(thr[0])
    best = ok[np.argmax(prec[:-1][ok])]
    return float(thr[best])


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict]:
    frame = pd.DataFrame({"y": y, "p": p})
    frame["bin"] = pd.qcut(frame["p"], bins, duplicates="drop")
    grouped = frame.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean")
    )
    return [
        {"mean_predicted": float(r.mean_pred), "observed_rate": float(r.observed), "n": int(r.n)}
        for r in grouped.itertuples()
    ]


def segment_errors(test: pd.DataFrame, p: np.ndarray, threshold: float, s: TrainSettings) -> dict:
    out = {}
    frame = test.assign(pred=p >= threshold, y=test[TARGET].astype(bool))
    for col in ("customer_state", "primary_category"):
        rows = []
        for key, g in frame.groupby(col):
            if len(g) < s.min_group_size:
                continue
            tp = int((g.pred & g.y).sum())
            rows.append(
                {
                    "segment": str(key),
                    "n": int(len(g)),
                    "late_rate": float(g.y.mean()),
                    "flag_rate": float(g.pred.mean()),
                    "precision": float(tp / g.pred.sum()) if g.pred.sum() else None,
                    "recall": float(tp / g.y.sum()) if g.y.sum() else None,
                }
            )
        out[col] = sorted(rows, key=lambda r: -r["n"])[: s.segment_top_n]
    return out


def train_and_evaluate(
    df: pd.DataFrame, s: TrainSettings = TrainSettings()
) -> tuple[Pipeline, dict, pd.DataFrame]:
    """Fit candidates on train, select by validation PR-AUC, report once on the later test window."""
    train, val, test = chronological_split(df, s)
    if (
        min(len(train), len(val), len(test)) < 50
        or min(train[TARGET].sum(), val[TARGET].sum(), test[TARGET].sum()) < 5
    ):
        raise ValueError("not enough rows/late orders in each split to train and evaluate reliably")
    models, val_scores, fitted = candidate_models(s.seed), {}, {}
    for name, pipe in models.items():
        pipe.fit(train[FEATURES], train[TARGET])  # preprocessing is fitted on train only
        pv = pipe.predict_proba(val[FEATURES])[:, 1]
        val_scores[name] = float(average_precision_score(val[TARGET], pv))
        fitted[name] = pipe
    real = {k: v for k, v in val_scores.items() if k != "baseline_prior"}
    chosen = max(real, key=real.get)
    thr = pick_threshold(
        val[TARGET].to_numpy(), fitted[chosen].predict_proba(val[FEATURES])[:, 1], s.recall_target
    )

    report = {"chosen_model": chosen, "validation_pr_auc": val_scores, "test": {}}
    for name in ("baseline_prior", chosen):
        pt = fitted[name].predict_proba(test[FEATURES])[:, 1]
        t = thr if name == chosen else float(train[TARGET].mean())
        report["test"][name] = _metrics(test[TARGET].to_numpy(), pt, t)
    p_test = fitted[chosen].predict_proba(test[FEATURES])[:, 1]
    report["calibration_test"] = calibration_table(test[TARGET].to_numpy(), p_test)
    report["segments_test"] = segment_errors(test, p_test, thr, s)
    # A transparent rule baseline: flag every cross-state order.
    rule = (1 - test["same_state"].fillna(0)).to_numpy()
    tp = int(((rule == 1) & (test[TARGET] == 1)).sum())
    report["test"]["rule_cross_state"] = {
        "precision": float(tp / rule.sum()) if rule.sum() else None,
        "recall": float(tp / test[TARGET].sum()),
        "flag_rate": float(rule.mean()),
    }
    report["split"] = {
        name: {
            "n": len(part),
            "late_rate": float(part[TARGET].mean()),
            "from": str(part["purchased_at"].min()),
            "to": str(part["purchased_at"].max()),
        }
        for name, part in (("train", train), ("validation", val), ("test", test))
    }
    scored = test[
        [
            "order_id",
            "purchased_at",
            "customer_state",
            "primary_seller_state",
            "primary_category",
            TARGET,
        ]
    ].copy()
    scored["risk"] = p_test
    meta = {
        "settings": asdict(s),
        "features": FEATURES,
        "target": TARGET,
        "excluded_post_outcome_columns": [
            "delivered_at",
            "carrier_at",
            "delivery_days",
            "delay_days",
            "review_score",
            "approved_at",
            "order_status",
        ],
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
        },
        "report": report,
        "threshold": thr,
    }
    return fitted[chosen], meta, scored


def save_artifacts(
    model: Pipeline, meta: dict, scored: pd.DataFrame, out_dir: Path, data_source: str
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "data_source": data_source}
    paths = {
        "model": out_dir / "late_delivery_model.joblib",
        "metadata": out_dir / "late_delivery_metadata.json",
        "scored_test": out_dir / "late_delivery_scored_test.parquet",
    }
    joblib.dump(model, paths["model"])
    paths["metadata"].write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    scored.to_parquet(paths["scored_test"], index=False)
    return paths
