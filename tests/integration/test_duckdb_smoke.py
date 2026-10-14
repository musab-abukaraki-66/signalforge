"""Smoke test: the analytical engine works and distinguishes order value from revenue.

Uses a tiny in-memory table, not real data, purely to prove the DuckDB toolchain runs.
"""

import duckdb


def test_duckdb_aggregates_in_memory():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE order_items (order_id INT, price DOUBLE, freight DOUBLE)")
    con.execute("INSERT INTO order_items VALUES (1, 10.0, 2.0), (1, 5.0, 1.0), (2, 20.0, 4.0)")
    orders, item_value, freight = con.execute(
        "SELECT count(DISTINCT order_id), sum(price), sum(freight) FROM order_items"
    ).fetchone()
    assert orders == 2
    assert item_value == 35.0
    assert freight == 7.0
    # Item value and freight are separate measures; neither alone is "revenue".
    assert item_value + freight != item_value
