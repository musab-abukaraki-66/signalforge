"""KPI and breakdown queries over the gold layer. One definition per KPI, used everywhere.

All functions take an open DuckDB connection and optional ``Filters``. Filters select ORDERS
(by purchase date, customer state, primary category); item-level measures then include every
item of the selected orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import duckdb
import pandas as pd

# Statuses excluded from sales KPIs (no goods were, or will be, delivered).
NON_SALES_STATUSES = ("canceled", "unavailable")

KPI_DEFINITIONS: dict[str, str] = {
    "Orders": "Distinct orders with status other than canceled/unavailable, by purchase date.",
    "GMV": "Sum of item price (freight excluded) over the orders counted as Orders. "
    "Not revenue or profit: commissions and costs are not in the data.",
    "Average order value": "GMV / orders that have at least one item.",
    "Freight share": "Sum of freight value / GMV, over the same orders.",
    "On-time rate": "Delivered orders with a delivery date, delivered on or before the estimated "
    "delivery date (day resolution) / such orders. Delivered orders only.",
    "Late rate": "1 - on-time rate.",
    "Average delivery time": "Mean days from purchase date to delivery date, delivered orders only.",
    "Average review score": "Mean score of the most recent review per order (1-5). Only orders "
    "whose customer left a review; reviewers are self-selected.",
    "Cancellation rate": "Orders with status canceled / all orders purchased in the period.",
    "Repeat rate (90d)": "Customers (customer_unique_id) with a second delivered order within "
    "90 days of their first / customers whose first order is at least 90 days before the end "
    "of the data.",
}


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    states: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = field(default_factory=tuple)

    def where(self, alias: str = "o") -> tuple[str, list]:
        clauses, params = ["TRUE"], []
        if self.date_from:
            clauses.append(f"{alias}.purchase_date >= ?")
            params.append(self.date_from)
        if self.date_to:
            clauses.append(f"{alias}.purchase_date <= ?")
            params.append(self.date_to)
        if self.states:
            clauses.append(f"{alias}.customer_state IN ({','.join('?' * len(self.states))})")
            params += list(self.states)
        if self.categories:
            clauses.append(f"{alias}.primary_category IN ({','.join('?' * len(self.categories))})")
            params += list(self.categories)
        return " AND ".join(clauses), params


_SALES = "o.order_status NOT IN ('canceled','unavailable')"


def _df(con: duckdb.DuckDBPyConnection, sql: str, params: list) -> pd.DataFrame:
    return con.execute(sql, params).df()


def overview(con: duckdb.DuckDBPyConnection, f: Filters = Filters()) -> dict:
    where, params = f.where()
    row = con.execute(
        f"""
        SELECT
          count(*) FILTER (WHERE {_SALES}) AS orders,
          coalesce(sum(o.items_value) FILTER (WHERE {_SALES}), 0) AS gmv,
          coalesce(sum(o.freight_value) FILTER (WHERE {_SALES}), 0) AS freight,
          count(*) FILTER (WHERE {_SALES} AND o.items_value IS NOT NULL) AS orders_with_items,
          count(*) FILTER (WHERE o.is_late IS NOT NULL) AS delivered_scored,
          count(*) FILTER (WHERE o.is_late) AS late_orders,
          avg(o.delivery_days) AS avg_delivery_days,
          avg(o.review_score) AS avg_review_score,
          count(o.review_score) AS reviewed_orders,
          count(*) FILTER (WHERE o.order_status = 'canceled') AS canceled,
          count(*) AS all_orders
        FROM gold.fact_order o WHERE {where}
        """,
        params,
    ).fetchone()
    keys = [
        "orders",
        "gmv",
        "freight",
        "orders_with_items",
        "delivered_scored",
        "late_orders",
        "avg_delivery_days",
        "avg_review_score",
        "reviewed_orders",
        "canceled",
        "all_orders",
    ]
    d = dict(zip(keys, row, strict=True))
    d["aov"] = d["gmv"] / d["orders_with_items"] if d["orders_with_items"] else None
    d["freight_share"] = d["freight"] / d["gmv"] if d["gmv"] else None
    d["late_rate"] = d["late_orders"] / d["delivered_scored"] if d["delivered_scored"] else None
    d["on_time_rate"] = None if d["late_rate"] is None else 1 - d["late_rate"]
    d["cancellation_rate"] = d["canceled"] / d["all_orders"] if d["all_orders"] else None
    return d


def monthly_trend(con, f: Filters = Filters()) -> pd.DataFrame:
    where, params = f.where()
    return _df(
        con,
        f"""
        SELECT o.purchase_month AS month,
               count(*) FILTER (WHERE {_SALES}) AS orders,
               coalesce(sum(o.items_value) FILTER (WHERE {_SALES}), 0) AS gmv,
               avg(o.items_value) FILTER (WHERE {_SALES}) AS aov,
               count(*) FILTER (WHERE o.is_late IS NOT NULL) AS delivered_scored,
               avg(o.is_late::INT) AS late_rate,
               avg(o.delivery_days) AS avg_delivery_days,
               avg(o.review_score) AS avg_review_score,
               avg((o.order_status = 'canceled')::INT) AS cancellation_rate
        FROM gold.fact_order o WHERE {where} GROUP BY 1 ORDER BY 1
        """,
        params,
    )


def category_breakdown(con, f: Filters = Filters(), limit: int = 15) -> pd.DataFrame:
    where, params = f.where()
    return _df(
        con,
        f"""
        SELECT p.category, count(DISTINCT i.order_id) AS orders, count(*) AS items,
               sum(i.price) AS gmv, sum(i.freight_value) AS freight, avg(i.price) AS avg_item_price
        FROM gold.fact_order_item i
        JOIN gold.fact_order o USING (order_id)
        JOIN gold.dim_product p USING (product_id)
        WHERE {where} AND {_SALES}
        GROUP BY 1 ORDER BY gmv DESC LIMIT {int(limit)}
        """,
        params,
    )


def seller_breakdown(
    con, f: Filters = Filters(), min_orders: int = 30, limit: int = 15
) -> pd.DataFrame:
    """Sellers by GMV. Order-level metrics use the order's primary seller; n is shown."""
    where, params = f.where()
    return _df(
        con,
        f"""
        WITH gmv AS (
            SELECT i.seller_id, sum(i.price) AS gmv, count(DISTINCT i.order_id) AS orders_with_seller
            FROM gold.fact_order_item i JOIN gold.fact_order o USING (order_id)
            WHERE {where} AND {_SALES} GROUP BY 1
        ), perf AS (
            SELECT o.primary_seller_id AS seller_id,
                   count(*) FILTER (WHERE o.is_late IS NOT NULL) AS delivered_scored,
                   avg(o.is_late::INT) AS late_rate, avg(o.review_score) AS avg_review_score
            FROM gold.fact_order o WHERE {where} GROUP BY 1
        )
        SELECT g.seller_id, s.state, g.gmv, g.orders_with_seller AS orders,
               pf.delivered_scored, pf.late_rate, pf.avg_review_score
        FROM gmv g JOIN gold.dim_seller s USING (seller_id)
        LEFT JOIN perf pf USING (seller_id)
        WHERE g.orders_with_seller >= {int(min_orders)}
        ORDER BY g.gmv DESC LIMIT {int(limit)}
        """,
        params + params,
    )


def state_breakdown(con, f: Filters = Filters()) -> pd.DataFrame:
    where, params = f.where()
    return _df(
        con,
        f"""
        SELECT o.customer_state AS state,
               count(*) FILTER (WHERE {_SALES}) AS orders,
               coalesce(sum(o.items_value) FILTER (WHERE {_SALES}), 0) AS gmv,
               avg(o.items_value) FILTER (WHERE {_SALES}) AS aov,
               avg(o.freight_value / nullif(o.items_value, 0)) FILTER (WHERE {_SALES}) AS freight_to_value,
               count(*) FILTER (WHERE o.is_late IS NOT NULL) AS delivered_scored,
               avg(o.is_late::INT) AS late_rate,
               avg(o.delivery_days) AS avg_delivery_days,
               avg(o.review_score) AS avg_review_score
        FROM gold.fact_order o WHERE {where} GROUP BY 1 ORDER BY gmv DESC
        """,
        params,
    )


def route_late_rate(con, f: Filters = Filters()) -> pd.DataFrame:
    """Late rate by whether the primary seller and the customer are in the same state."""
    where, params = f.where()
    return _df(
        con,
        f"""
        SELECT CASE WHEN o.primary_seller_state = o.customer_state THEN 'Same state'
                    ELSE 'Different state' END AS route,
               count(*) AS delivered_scored, avg(o.is_late::INT) AS late_rate,
               avg(o.delivery_days) AS avg_delivery_days, avg(o.review_score) AS avg_review_score
        FROM gold.fact_order o
        WHERE {where} AND o.is_late IS NOT NULL AND o.primary_seller_state IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """,
        params,
    )


def review_by_delay(con, f: Filters = Filters()) -> pd.DataFrame:
    """Average review score and low-score share by delivery outcome (association only)."""
    where, params = f.where()
    return _df(
        con,
        f"""
        SELECT CASE WHEN o.delay_days <= -7 THEN '1. 7+ days early'
                    WHEN o.delay_days <= 0 THEN '2. 0-6 days early / on the day'
                    WHEN o.delay_days <= 7 THEN '3. 1-7 days late'
                    ELSE '4. 8+ days late' END AS delivery_outcome,
               count(o.review_score) AS reviewed_orders,
               avg(o.review_score) AS avg_review_score,
               avg((o.review_score <= 2)::INT) FILTER (WHERE o.review_score IS NOT NULL) AS low_score_share
        FROM gold.fact_order o
        WHERE {where} AND o.delay_days IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """,
        params,
    )


def repeat_cohorts(con, f: Filters = Filters()) -> pd.DataFrame:
    """90-day repeat rate by first-purchase month; only cohorts fully observed for 90 days."""
    where, params = f.where()
    return _df(
        con,
        f"""
        WITH as_of AS (SELECT max(purchase_date) AS d FROM gold.fact_order),
        ranked AS (
            SELECT o.customer_unique_id, o.purchase_date,
                   row_number() OVER (PARTITION BY o.customer_unique_id
                                      ORDER BY o.purchased_at, o.order_id) AS rn
            FROM gold.fact_order o WHERE {where} AND o.order_status = 'delivered'
        ), firsts AS (
            SELECT a.customer_unique_id, a.purchase_date AS first_date,
                   b.purchase_date AS second_date
            FROM ranked a LEFT JOIN ranked b
              ON a.customer_unique_id = b.customer_unique_id AND b.rn = 2
            WHERE a.rn = 1
        )
        SELECT strftime(first_date, '%Y-%m') AS cohort_month, count(*) AS customers,
               avg((second_date IS NOT NULL
                    AND date_diff('day', first_date, second_date) <= 90)::INT) AS repeat_rate_90d
        FROM firsts WHERE first_date <= (SELECT d FROM as_of) - INTERVAL 90 DAY
        GROUP BY 1 ORDER BY 1
        """,
        params,
    )


def customer_segments(con) -> pd.DataFrame:
    """Rule-based segments (frequency is mostly 1, so quintile RFM would be arbitrary)."""
    return con.execute(
        """
        SELECT CASE WHEN frequency >= 2 THEN 'Repeat customer (2+ delivered orders)'
                    WHEN recency_days <= 90 THEN 'One-time, bought in last 90 days'
                    ELSE 'One-time, lapsed (>90 days)' END AS segment,
               count(*) AS customers, avg(monetary) AS avg_item_value, avg(recency_days) AS avg_recency_days
        FROM gold.mart_customer_rfm GROUP BY 1 ORDER BY 2 DESC
        """
    ).df()


def filter_options(con) -> dict:
    lo, hi = con.execute(
        "SELECT min(purchase_date), max(purchase_date) FROM gold.fact_order"
    ).fetchone()
    states = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT customer_state FROM gold.fact_order WHERE customer_state IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]
    cats = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT primary_category FROM gold.fact_order WHERE primary_category IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]
    return {"date_min": lo, "date_max": hi, "states": states, "categories": cats}
