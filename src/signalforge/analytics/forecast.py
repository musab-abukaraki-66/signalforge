"""Weekly demand forecast with chronological validation and honest baselines.

Series: weekly sales orders (or GMV) from gold.fact_order, using sales statuses only.
Partial first/last weeks are dropped. The final ``horizon`` complete weeks are held out; every
model is fitted on the earlier weeks only and judged on the held-out weeks. Baselines: naive
(repeat last week) and a 4-week moving average. Candidate: damped-trend exponential smoothing
(Holt) with parameters chosen by one-step in-sample error on the training weeks.

Intervals are approximate: normal, using in-sample one-step residual spread scaled by
sqrt(horizon). They assume stable, independent errors and are labelled as such.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from signalforge.analytics.kpis import NON_SALES_STATUSES

Z80 = 1.2816


@dataclass(frozen=True)
class ForecastSettings:
    horizon: int = 8  # weeks held out, and weeks forecast ahead
    min_train_weeks: int = 16
    ma_window: int = 4


def weekly_series(con: duckdb.DuckDBPyConnection, measure: str = "orders") -> pd.DataFrame:
    """Complete weeks only: columns week_start, value."""
    if measure not in {"orders", "gmv"}:
        raise ValueError("measure must be 'orders' or 'gmv'")
    expr = "count(*)" if measure == "orders" else "sum(items_value)"
    statuses = ",".join(f"'{s}'" for s in NON_SALES_STATUSES)
    df = con.execute(
        f"""
        SELECT date_trunc('week', purchase_date)::DATE AS week_start, {expr} AS value,
               min(purchase_date) AS first_day, max(purchase_date) AS last_day
        FROM gold.fact_order WHERE order_status NOT IN ({statuses}) GROUP BY 1 ORDER BY 1
        """
    ).df()
    if df.empty:
        return df[["week_start", "value"]]
    lo, hi = con.execute(
        "SELECT min(purchase_date), max(purchase_date) FROM gold.fact_order"
    ).fetchone()
    ws = pd.to_datetime(df["week_start"])
    keep = (ws >= pd.Timestamp(lo)) & (ws + pd.Timedelta(days=6) <= pd.Timestamp(hi))
    out = df.loc[keep, ["week_start", "value"]].reset_index(drop=True)
    out["week_start"] = pd.to_datetime(out["week_start"])
    out["value"] = out["value"].astype(float)
    return out


def _holt_fit(y: np.ndarray, alpha: float, beta: float, phi: float):
    level, trend = y[0], y[1] - y[0] if len(y) > 1 else 0.0
    errs = []
    for obs in y[1:]:
        pred = level + phi * trend
        errs.append(obs - pred)
        new_level = alpha * obs + (1 - alpha) * pred
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, np.array(errs)


def holt_forecast(y: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Damped Holt forecast and the per-step standard error (grid-searched on one-step SSE)."""
    best = None
    for a, b, p in itertools.product((0.2, 0.4, 0.6), (0.05, 0.15, 0.3), (0.8, 0.9, 0.98)):
        level, trend, errs = _holt_fit(y, a, b, p)
        sse = float((errs**2).sum())
        if best is None or sse < best[0]:
            best = (sse, a, b, p, level, trend, errs)
    _, _, _, phi, level, trend, errs = best
    steps = np.arange(1, h + 1)
    damp = np.cumsum(phi**steps)
    point = level + damp * trend
    sigma = float(errs.std(ddof=1)) if len(errs) > 2 else 0.0
    return np.maximum(point, 0), sigma * np.sqrt(steps)


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    err = actual - pred
    return {
        "mae": float(np.abs(err).mean()),
        "wmape": float(np.abs(err).sum() / np.abs(actual).sum()),
        "bias": float(err.mean()),
    }


def evaluate(series: pd.DataFrame, s: ForecastSettings = ForecastSettings()) -> dict:
    """Backtest on the final ``horizon`` weeks, then forecast the next ``horizon`` weeks."""
    n = len(series)
    if n < s.min_train_weeks + s.horizon:
        raise ValueError(f"need at least {s.min_train_weeks + s.horizon} complete weeks, have {n}")
    y = series["value"].to_numpy()
    train, test = y[: -s.horizon], y[-s.horizon :]
    naive = np.repeat(train[-1], s.horizon)
    ma = np.repeat(train[-s.ma_window :].mean(), s.horizon)
    holt, se = holt_forecast(train, s.horizon)
    backtest = pd.DataFrame(
        {
            "week_start": series["week_start"].iloc[-s.horizon :].to_numpy(),
            "actual": test,
            "naive": naive,
            "moving_average": ma,
            "holt": holt,
            "holt_lo80": np.maximum(holt - Z80 * se, 0),
            "holt_hi80": holt + Z80 * se,
        }
    )
    metrics = {
        "naive": _metrics(test, naive),
        "moving_average": _metrics(test, ma),
        "holt": _metrics(test, holt),
    }
    metrics["holt"]["coverage_80"] = float(
        ((test >= backtest["holt_lo80"]) & (test <= backtest["holt_hi80"])).mean()
    )
    best_baseline = min(("naive", "moving_average"), key=lambda k: metrics[k]["mae"])
    f_point, f_se = holt_forecast(y, s.horizon)
    last = series["week_start"].iloc[-1]
    future = pd.DataFrame(
        {
            "week_start": [last + pd.Timedelta(weeks=i) for i in range(1, s.horizon + 1)],
            "forecast": f_point,
            "lo80": np.maximum(f_point - Z80 * f_se, 0),
            "hi80": f_point + Z80 * f_se,
        }
    )
    return {
        "weeks_total": n,
        "weeks_train": n - s.horizon,
        "horizon": s.horizon,
        "metrics": metrics,
        "best_baseline": best_baseline,
        "beats_baseline": metrics["holt"]["mae"] < metrics[best_baseline]["mae"],
        "backtest": backtest,
        "future": future,
    }
