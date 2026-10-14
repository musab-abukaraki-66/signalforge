import numpy as np
import pandas as pd
import pytest

from signalforge.analytics import forecast as fc


def _series(values):
    return pd.DataFrame(
        {
            "week_start": pd.date_range("2018-01-01", periods=len(values), freq="W-MON"),
            "value": values,
        }
    )


def test_holdout_is_the_final_weeks_and_models_never_see_them():
    values = list(range(10, 50))  # steady growth of 1/week
    res = fc.evaluate(_series(values), fc.ForecastSettings(horizon=8))
    bt = res["backtest"]
    assert list(bt["actual"]) == values[-8:]
    assert res["weeks_train"] == len(values) - 8
    # naive repeats the last TRAIN value, not a held-out value
    assert (bt["naive"] == values[-9]).all()


def test_trend_model_beats_naive_on_a_clean_trend():
    res = fc.evaluate(_series(np.arange(10.0, 60.0)))
    assert res["beats_baseline"]
    assert res["metrics"]["holt"]["mae"] < res["metrics"]["naive"]["mae"]


def test_intervals_widen_with_horizon_and_forecast_is_future():
    rng = np.random.default_rng(0)
    series = _series(100 + np.arange(40) + rng.normal(0, 5, 40))
    res = fc.evaluate(series)
    width = (res["future"]["hi80"] - res["future"]["lo80"]).to_numpy()
    assert width[-1] > width[0]
    assert res["future"]["week_start"].min() > series["week_start"].max()


def test_too_short_series_rejected():
    with pytest.raises(ValueError, match="complete weeks"):
        fc.evaluate(_series([1.0] * 10))


def test_weekly_series_from_warehouse_drops_partial_weeks(con):
    s = fc.weekly_series(con, "orders")
    assert len(s) > 30 and (s["week_start"].dt.dayofweek == 0).all()
    total = con.execute(
        "SELECT count(*) FROM gold.fact_order WHERE order_status NOT IN ('canceled','unavailable')"
    ).fetchone()[0]
    assert s["value"].sum() <= total  # partial edge weeks excluded
    with pytest.raises(ValueError):
        fc.weekly_series(con, "profit")
