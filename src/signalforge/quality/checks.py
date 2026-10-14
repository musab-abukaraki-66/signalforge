"""Data-quality checks run against the silver and gold layers.

A check is a SQL query that returns the number of violating rows; zero means pass.
``error`` severity failures stop the pipeline, ``warn`` failures are reported only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb

from signalforge.errors import DataQualityError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Check:
    name: str
    sql: str  # returns one number: count of violating rows
    severity: str = "error"
    description: str = ""


@dataclass(frozen=True)
class CheckResult:
    check: Check
    violations: int

    @property
    def passed(self) -> bool:
        return self.violations == 0


def _unique(table: str, key: str) -> Check:
    return Check(
        f"unique:{table}({key})",
        f"SELECT count(*) FROM (SELECT {key} FROM {table} GROUP BY {key} HAVING count(*) > 1)",
        description=f"{table} must have one row per ({key})",
    )


def _not_null(table: str, col: str) -> Check:
    return Check(f"not_null:{table}.{col}", f"SELECT count(*) FROM {table} WHERE {col} IS NULL")


def _fk(child: str, col: str, parent: str, pcol: str, severity: str = "error") -> Check:
    return Check(
        f"fk:{child}.{col}->{parent}.{pcol}",
        f"SELECT count(*) FROM {child} c WHERE c.{col} IS NOT NULL "
        f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pcol} = c.{col})",
        severity,
    )


def _range(table: str, expr: str, name: str, severity: str = "error") -> Check:
    return Check(
        f"range:{table}:{name}", f"SELECT count(*) FROM {table} WHERE NOT ({expr})", severity
    )


def _cast_loss(silver: str, bronze: str, col_silver: str, col_bronze: str) -> Check:
    return Check(
        f"typed:{silver}.{col_silver}",
        f"SELECT (SELECT count(*) FROM {bronze} WHERE nullif(trim({col_bronze}), '') IS NOT NULL)"
        f" - (SELECT count(*) FROM {silver} WHERE {col_silver} IS NOT NULL)",
        description="values present in bronze but unparseable in silver",
    )


CHECKS: tuple[Check, ...] = (
    # silver typing: nothing may be lost in casting
    _cast_loss("silver.orders", "bronze.orders", "purchased_at", "order_purchase_timestamp"),
    _cast_loss("silver.orders", "bronze.orders", "delivered_at", "order_delivered_customer_date"),
    _cast_loss(
        "silver.orders", "bronze.orders", "estimated_delivery_at", "order_estimated_delivery_date"
    ),
    _cast_loss("silver.order_items", "bronze.order_items", "price", "price"),
    _cast_loss("silver.order_items", "bronze.order_items", "freight_value", "freight_value"),
    _cast_loss("silver.order_payments", "bronze.order_payments", "payment_value", "payment_value"),
    _not_null("silver.order_reviews", "review_score"),
    # keys and grain
    _unique("silver.orders", "order_id"),
    _unique("silver.order_items", "order_id, order_item_id"),
    _unique("silver.order_payments", "order_id, payment_sequential"),
    _unique("silver.order_reviews", "review_id, order_id"),
    _unique("silver.customers", "customer_id"),
    _unique("silver.sellers", "seller_id"),
    _unique("silver.products", "product_id"),
    _unique("gold.fact_order", "order_id"),
    _unique("gold.fact_order_item", "order_id, order_item_id"),
    _unique("gold.dim_product", "product_id"),
    _not_null("silver.orders", "order_id"),
    _not_null("silver.orders", "customer_id"),
    _not_null("silver.orders", "purchased_at"),
    _not_null("silver.order_items", "seller_id"),
    # referential integrity
    _fk("silver.orders", "customer_id", "silver.customers", "customer_id"),
    _fk("silver.order_items", "order_id", "silver.orders", "order_id"),
    _fk("silver.order_items", "product_id", "silver.products", "product_id"),
    _fk("silver.order_items", "seller_id", "silver.sellers", "seller_id"),
    _fk("silver.order_payments", "order_id", "silver.orders", "order_id"),
    _fk("silver.order_reviews", "order_id", "silver.orders", "order_id"),
    # accepted ranges and business rules
    _range("silver.order_items", "price >= 0 AND freight_value >= 0", "non_negative_money"),
    _range("silver.order_payments", "payment_value >= 0", "non_negative_payment"),
    _range("silver.order_reviews", "review_score BETWEEN 1 AND 5", "score_1_to_5"),
    _range(
        "silver.orders",
        "delivered_at IS NULL OR delivered_at >= purchased_at",
        "delivery_not_before_purchase",
    ),
    _range(
        "silver.orders",
        "order_status IN ('created','approved','invoiced','processing','shipped','delivered',"
        "'unavailable','canceled')",
        "known_status",
    ),
    # warnings: informative, not blocking
    Check(
        "warn:delivered_without_delivery_date",
        "SELECT count(*) FROM silver.orders WHERE order_status='delivered' AND delivered_at IS NULL",
        "warn",
        "delivered orders lacking a delivery timestamp are excluded from delivery KPIs",
    ),
    Check(
        "warn:items_without_gold_product_category",
        "SELECT count(*) FROM gold.fact_order WHERE primary_category = 'unknown'",
        "warn",
        "orders whose primary product has no category",
    ),
    Check(
        "warn:payment_vs_item_value_mismatch",
        "SELECT count(*) FROM gold.fact_order WHERE payment_value IS NOT NULL "
        "AND items_value IS NOT NULL AND abs(payment_value - items_value - freight_value) > 1.0",
        "warn",
        "payment total differs from items + freight by more than 1 currency unit",
    ),
    Check(
        "warn:orders_with_multiple_reviews",
        "SELECT count(*) FROM (SELECT order_id FROM silver.order_reviews GROUP BY order_id "
        "HAVING count(*) > 1)",
        "warn",
        "the most recent review is used for review_score",
    ),
    Check(
        "warn:bronze_duplicate_reviews_removed",
        "SELECT (SELECT count(*) FROM bronze.order_reviews) - (SELECT count(*) FROM silver.order_reviews)",
        "warn",
        "exact (review_id, order_id) duplicates dropped in silver",
    ),
)


def run_checks(
    con: duckdb.DuckDBPyConnection,
    checks: tuple[Check, ...] = CHECKS,
    *,
    raise_on_error: bool = True,
) -> list[CheckResult]:
    results = []
    for check in checks:
        violations = int(con.execute(check.sql).fetchone()[0])
        result = CheckResult(check, violations)
        results.append(result)
        level = (
            logging.INFO
            if result.passed
            else (logging.ERROR if check.severity == "error" else logging.WARNING)
        )
        log.log(level, "[%s] %s: %d violation(s)", check.severity, check.name, violations)
    failed = [r for r in results if not r.passed and r.check.severity == "error"]
    if failed and raise_on_error:
        names = ", ".join(f"{r.check.name} ({r.violations})" for r in failed)
        raise DataQualityError(f"{len(failed)} data-quality check(s) failed: {names}")
    return results
