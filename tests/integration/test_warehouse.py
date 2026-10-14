"""Gold-layer correctness: grain, keys, reconciliation with an independent calculation."""

from signalforge.analytics import kpis
from signalforge.analytics.findings import build_findings, render_markdown
from signalforge.analytics.reconcile import reconcile


def test_build_summary(warehouse):
    _, summary = warehouse
    assert summary["data_source"] == "synthetic-demo"
    assert summary["checks_failed_error"] == 0
    assert summary["gold_rows"]["fact_order"] == 2500


def test_fact_order_grain_and_no_fan_out(con):
    n, distinct = con.execute(
        "SELECT count(*), count(DISTINCT order_id) FROM gold.fact_order"
    ).fetchone()
    assert n == distinct
    # item value on fact_order equals the sum over items: no duplication through joins
    gap = con.execute(
        "SELECT abs((SELECT sum(items_value) FROM gold.fact_order) - (SELECT sum(price) FROM gold.fact_order_item))"
    ).fetchone()[0]
    assert gap < 1e-6


def test_split_payments_are_not_double_counted(con):
    gap = con.execute(
        "SELECT abs((SELECT sum(payment_value) FROM gold.fact_order) - (SELECT sum(payment_value) FROM gold.fact_payment))"
    ).fetchone()[0]
    assert gap < 1e-6


def test_is_late_only_defined_for_delivered(con):
    bad = con.execute(
        "SELECT count(*) FROM gold.fact_order WHERE is_late IS NOT NULL AND order_status <> 'delivered'"
    ).fetchone()[0]
    assert bad == 0


def test_kpis_reconcile_with_independent_calculation(warehouse, con):
    config, _ = warehouse
    for r in reconcile(con, config.raw_dir):
        assert r.ok, r


def test_filters_narrow_results(con):
    total = kpis.overview(con)["orders"]
    sp = kpis.overview(con, kpis.Filters(states=("SP",)))["orders"]
    assert 0 < sp < total
    assert kpis.overview(con, kpis.Filters(states=("ZZ",)))["orders"] == 0


def test_findings_render_with_required_fields_and_synthetic_warning(con):
    findings = build_findings(con)
    assert len(findings) >= 4
    text = render_markdown(findings, "synthetic-demo")
    assert "SYNTHETIC DEMO DATA" in text
    for f in findings:
        assert f.definition and f.period and f.n and f.limitation
