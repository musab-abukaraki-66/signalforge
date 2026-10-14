"""Decision Room calculations over the held-out scored orders.

Two kinds of numbers come out of here and must stay labelled:
  OBSERVED-ON-HOLDOUT: how many truly late orders (historical outcome) fall inside the flagged
    group. These are facts about the test window, given the model's scores.
  SCENARIO: results that depend on user-entered assumptions (intervention effect, costs).
    They are what-ifs, not forecasts, and are only computed when the inputs are supplied.
No default cost, benefit or effect is invented: leave an input empty and the output says what
is missing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Assumptions:
    """User-supplied inputs for the scenario layer. ``None`` means 'not provided'."""

    intervention_success_rate: float | None = None  # share of flagged late orders rescued
    cost_per_intervention: float | None = None  # currency units per flagged order
    value_per_rescued_order: float | None = None  # currency units per late order avoided

    def missing(self) -> list[str]:
        names = {
            "intervention_success_rate": "share of flagged late orders an intervention rescues",
            "cost_per_intervention": "cost of intervening on one flagged order",
            "value_per_rescued_order": "value of avoiding one late delivery",
        }
        return [desc for key, desc in names.items() if getattr(self, key) is None]


def flag_top_share(scored: pd.DataFrame, share: float) -> pd.DataFrame:
    """Flag the ``share`` (0-1] of orders with the highest model risk."""
    if not 0 < share <= 1:
        raise ValueError("share must be in (0, 1]")
    k = max(1, int(round(len(scored) * share)))
    order = scored.sort_values("risk", ascending=False, kind="stable")
    return order.assign(flagged=np.arange(len(order)) < k)


def holdout_outcome(scored: pd.DataFrame, share: float) -> dict:
    """Observed-on-holdout evidence for reviewing the top ``share`` of orders by risk."""
    flagged = flag_top_share(scored, share)
    n, k = len(flagged), int(flagged["flagged"].sum())
    late_total = int(flagged["is_late"].sum())
    caught = int(flagged.loc[flagged["flagged"], "is_late"].sum())
    base_rate = late_total / n if n else float("nan")
    precision = caught / k if k else float("nan")
    return {
        "orders_in_holdout": n,
        "orders_flagged": k,
        "late_orders_in_holdout": late_total,
        "late_orders_caught": caught,
        "precision": precision,
        "recall": caught / late_total if late_total else float("nan"),
        "base_late_rate": base_rate,
        "lift_vs_random": precision / base_rate if base_rate else float("nan"),
    }


def threshold_table(scored: pd.DataFrame, shares=(0.05, 0.1, 0.2, 0.3, 0.5)) -> pd.DataFrame:
    return pd.DataFrame([{"review_share": s, **holdout_outcome(scored, s)} for s in shares])


def scenario(scored: pd.DataFrame, share: float, a: Assumptions) -> dict:
    """What-if built on the observed holdout outcome plus the user's assumptions."""
    base = holdout_outcome(scored, share)
    result = {
        "label": "SCENARIO (assumption-based, not a forecast)",
        "evidence": base,
        "assumptions": a,
        "missing_inputs": a.missing(),
    }
    if a.intervention_success_rate is not None:
        result["late_orders_avoided"] = base["late_orders_caught"] * a.intervention_success_rate
    if a.cost_per_intervention is not None:
        result["intervention_cost"] = base["orders_flagged"] * a.cost_per_intervention
    if not a.missing():
        result["net_value"] = (
            result["late_orders_avoided"] * a.value_per_rescued_order - result["intervention_cost"]
        )
    return result
