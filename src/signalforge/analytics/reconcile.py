"""Independent reconciliation: recompute headline KPIs from the RAW CSVs with pandas and
compare them with the gold layer (which is built by SQL). Disagreement means a modelling bug."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from signalforge.analytics.kpis import NON_SALES_STATUSES, overview


@dataclass(frozen=True)
class Reconciliation:
    kpi: str
    gold: float
    independent: float
    tolerance: float = 1e-6

    @property
    def ok(self) -> bool:
        return abs(self.gold - self.independent) <= self.tolerance * max(1.0, abs(self.independent))


def independent_kpis(raw_dir: Path) -> dict[str, float]:
    orders = pd.read_csv(
        raw_dir / "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    items = pd.read_csv(raw_dir / "olist_order_items_dataset.csv")
    sales = orders[~orders["order_status"].isin(NON_SALES_STATUSES)]
    item_sum = items.groupby("order_id")["price"].sum()
    sales_items = item_sum[item_sum.index.isin(sales["order_id"])]
    delivered = orders[
        (orders["order_status"] == "delivered")
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
    ]
    late = (
        delivered["order_delivered_customer_date"].dt.normalize()
        > delivered["order_estimated_delivery_date"].dt.normalize()
    )
    days = (
        delivered["order_delivered_customer_date"].dt.normalize()
        - delivered["order_purchase_timestamp"].dt.normalize()
    ).dt.days
    return {
        "orders": float(len(sales)),
        "gmv": float(sales_items.sum()),
        "aov": float(sales_items.mean()),
        "late_rate": float(late.mean()),
        "avg_delivery_days": float(days.mean()),
        "cancellation_rate": float((orders["order_status"] == "canceled").mean()),
    }


def reconcile(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> list[Reconciliation]:
    gold = overview(con)
    ind = independent_kpis(raw_dir)
    return [Reconciliation(k, float(gold[k]), v) for k, v in ind.items()]
