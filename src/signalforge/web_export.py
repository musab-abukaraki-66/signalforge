"""Export a demo bundle (JSON) for the public web app from the gold layer and model outputs.

The bundle carries an order-level table so the browser can recompute KPIs under filters with
the same definitions, plus Python-computed expected values that the web tests compare against
(parity check). Contents are exactly as labelled in ``meta.data_source``; synthetic data stays
labelled synthetic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from signalforge.analytics import forecast, kpis
from signalforge.decision_engine import scenarios
from signalforge.quality.checks import run_checks

ORDER_COLUMNS = (
    "purchase_date",
    "customer_state",
    "seller_state",
    "category",
    "status",
    "items_value",
    "freight_value",
    "late",
    "delivery_days",
    "delay_days",
    "review_score",
)
SHARES = (0.05, 0.1, 0.2, 0.3, 0.5)
PARITY_FILTERS = {
    "states": ["SP"],
    "categories": [],
    "date_from": "2017-06-01",
    "date_to": "2018-03-31",
}


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return round(value, 4) if isinstance(value, float) else value


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def _orders(con: duckdb.DuckDBPyConnection) -> list[list]:
    rows = con.execute(
        """
        SELECT strftime(purchase_date, '%Y-%m-%d'), customer_state, primary_seller_state,
               primary_category, order_status, round(items_value, 2), round(freight_value, 2),
               CASE WHEN is_late IS NULL THEN NULL ELSE is_late::INT END,
               delivery_days, delay_days, review_score
        FROM gold.fact_order ORDER BY purchased_at, order_id
        """
    ).fetchall()
    return [[_clean(v) for v in r] for r in rows]


def _overview(con, f: kpis.Filters) -> dict:
    return {k: _clean(v) for k, v in kpis.overview(con, f).items()}


def build_bundle(con: duckdb.DuckDBPyConnection, processed_dir: Path) -> dict:
    source = con.execute("SELECT data_source FROM gold.meta").fetchone()[0]
    opts = kpis.filter_options(con)
    summary_path = processed_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    pf = PARITY_FILTERS
    expected_filters = kpis.Filters(
        pd.Timestamp(pf["date_from"]).date(),
        pd.Timestamp(pf["date_to"]).date(),
        tuple(pf["states"]),
    )
    bundle: dict = {
        "meta": {
            "data_source": source,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "date_min": str(opts["date_min"]),
            "date_max": str(opts["date_max"]),
            "states": opts["states"],
            "categories": opts["categories"],
            "gold_rows": summary.get("gold_rows", {}),
            "bronze_rows": summary.get("bronze_rows", {}),
        },
        "definitions": kpis.KPI_DEFINITIONS,
        "order_columns": list(ORDER_COLUMNS),
        "orders": _orders(con),
        "expected": {
            "overview_all": _overview(con, kpis.Filters()),
            "parity_filters": pf,
            "overview_filtered": _overview(con, expected_filters),
        },
        "cohorts": _records(kpis.repeat_cohorts(con)),
        "segments": _records(kpis.customer_segments(con)),
        "quality": [
            {
                "name": r.check.name,
                "severity": r.check.severity,
                "violations": r.violations,
                "passed": r.passed,
                "description": r.check.description,
            }
            for r in run_checks(con, raise_on_error=False)
        ],
        "forecast": {},
    }
    for measure in ("orders", "gmv"):
        res = forecast.evaluate(forecast.weekly_series(con, measure))
        series = forecast.weekly_series(con, measure)
        bundle["forecast"][measure] = {
            "series": [
                {"week": d.strftime("%Y-%m-%d"), "value": round(v, 2)}
                for d, v in zip(series["week_start"], series["value"], strict=True)
            ],
            "metrics": res["metrics"],
            "best_baseline": res["best_baseline"],
            "horizon": res["horizon"],
            "backtest": [
                {
                    k: (v.strftime("%Y-%m-%d") if k == "week_start" else round(float(v), 2))
                    for k, v in row.items()
                }
                for row in res["backtest"].to_dict("records")
            ],
            "future": [
                {
                    k: (v.strftime("%Y-%m-%d") if k == "week_start" else round(float(v), 2))
                    for k, v in row.items()
                }
                for row in res["future"].to_dict("records")
            ],
        }
    meta_path = processed_dir / "models" / "late_delivery_metadata.json"
    scored_path = processed_dir / "models" / "late_delivery_scored_test.parquet"
    if meta_path.exists() and scored_path.exists():
        meta = json.loads(meta_path.read_text())
        scored = pd.read_parquet(scored_path)
        rep = meta["report"]
        bundle["model"] = {
            "chosen": rep["chosen_model"],
            "validation_pr_auc": rep["validation_pr_auc"],
            "test": rep["test"],
            "calibration": rep["calibration_test"],
            "segments": rep["segments_test"],
            "split": rep["split"],
            "features": meta["features"],
            "excluded": meta["excluded_post_outcome_columns"],
            "threshold": meta["threshold"],
            "scored": [
                [round(float(r), 4), int(y)]
                for r, y in zip(scored["risk"], scored["is_late"], strict=True)
            ],
            "expected_threshold_table": _records(scenarios.threshold_table(scored, SHARES)),
        }
    return bundle


def export_web(con: duckdb.DuckDBPyConnection, processed_dir: Path, out_path: Path) -> Path:
    bundle = build_bundle(con, processed_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(bundle, separators=(",", ":"), allow_nan=False), encoding="utf-8"
    )
    return out_path
