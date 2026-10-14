import pandas as pd
import pytest

from signalforge.decision_engine import scenarios as sc


def scored():
    # risk descending == late descending: perfect ranking, 3 late of 10
    return pd.DataFrame(
        {
            "risk": [0.9, 0.8, 0.7, 0.4, 0.3, 0.2, 0.1, 0.1, 0.05, 0.01],
            "is_late": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
        }
    )


def test_holdout_outcome_counts():
    r = sc.holdout_outcome(scored(), 0.3)
    assert (r["orders_flagged"], r["late_orders_caught"]) == (3, 3)
    assert (
        r["precision"] == 1 and r["recall"] == 1 and r["lift_vs_random"] == pytest.approx(1 / 0.3)
    )


def test_bad_share_rejected():
    with pytest.raises(ValueError):
        sc.flag_top_share(scored(), 0)


def test_no_invented_numbers_when_inputs_missing():
    res = sc.scenario(scored(), 0.3, sc.Assumptions())
    assert "net_value" not in res and "late_orders_avoided" not in res
    assert len(res["missing_inputs"]) == 3


def test_scenario_uses_only_supplied_inputs():
    res = sc.scenario(scored(), 0.3, sc.Assumptions(0.5, 2.0, 10.0))
    assert res["late_orders_avoided"] == pytest.approx(1.5)
    assert res["intervention_cost"] == pytest.approx(6.0)
    assert res["net_value"] == pytest.approx(1.5 * 10 - 6.0)
    assert not res["missing_inputs"]
