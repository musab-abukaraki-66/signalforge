"""SIGNALFORGE dashboard (Streamlit). Run with ``signalforge dashboard``.

Every number comes from the gold layer through ``signalforge.analytics.kpis`` (one definition
per KPI) or from the saved model artifacts. Nothing is hard-coded.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from signalforge.analytics import forecast, kpis
from signalforge.decision_engine import scenarios
from signalforge.quality.checks import run_checks

INK, MUTED, ACCENT, ALERT, GRID = "#14161a", "#4b5563", "#0b7a6b", "#b45309", "#e4ddd2"
SIGNAL, PAPER = "#2de2c0", "#f6f3ee"
DB_PATH = Path(os.environ.get("SIGNALFORGE_DB", "data/processed/signalforge.duckdb"))
PROCESSED = Path(os.environ.get("SIGNALFORGE_PROCESSED", DB_PATH.parent))

CSS = f"""
<style>
.stApp {{ background: {PAPER}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
h1, h2, h3, h4 {{ letter-spacing: -0.01em; color: {INK}; }}
.sf-hero {{ background: {INK}; color: #f4f1ea; border-radius: 10px; padding: 1.4rem 1.6rem; margin-bottom: 1rem;
            display: flex; flex-wrap: wrap; gap: 1rem; justify-content: space-between; align-items: flex-end; }}
.sf-brand {{ font-size: 2rem; font-weight: 800; letter-spacing: .04em; margin: 0; line-height: 1.1; }}
.sf-brand span {{ color: {SIGNAL}; }}
.sf-tag {{ color: #c9c4b8; margin: .3rem 0 0 0; }}
.sf-pills {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
.sf-pill {{ font-size: .78rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
            padding: .3rem .7rem; border-radius: 999px; border: 1px solid #5b6068; color: #e8e4da; }}
.sf-pill.real {{ background: {SIGNAL}; color: {INK}; border-color: {SIGNAL}; }}
.sf-pill.synth {{ background: #f6c453; color: {INK}; border-color: #f6c453; }}
.sf-banner {{ border-left: 4px solid {ALERT}; background: #fff7e6; color: #78350f;
              padding: .6rem .9rem; border-radius: 4px; margin-bottom: 1rem; font-size: .92rem; }}
.sf-label {{ display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.04em;
             text-transform:uppercase; padding:.15rem .5rem; border-radius:3px; margin-bottom:.3rem; }}
.sf-fact {{ background:#d7efe9; color:#0b4f45; }}
.sf-pred {{ background:#e0e7ff; color:#312e81; }}
.sf-scen {{ background:#fde9b8; color:#7a3e07; }}
[data-testid="stMetric"] {{ background: #fffdf9; border: 1px solid {GRID}; border-radius: 8px; padding: .7rem .9rem; }}
[data-testid="stMetricValue"] {{ font-size: 1.55rem; color: {INK}; }}
button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, a:focus-visible
  {{ outline: 3px solid {ACCENT} !important; outline-offset: 2px; }}
@media (max-width: 640px) {{ .sf-brand {{ font-size: 1.5rem; }} [data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def label(kind: str) -> None:
    text, cls = {
        "fact": ("Observed historical fact", "sf-fact"),
        "pred": ("Model prediction", "sf-pred"),
        "scen": ("Scenario - assumption-based, not a forecast", "sf-scen"),
    }[kind]
    st.markdown(f'<span class="sf-label {cls}">{text}</span>', unsafe_allow_html=True)


def style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=30, b=8),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color=INK, size=13),
        legend=dict(orientation="h", y=-0.2, x=0),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def money(x: float | None) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:,.0f}"


def pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:.{digits}f}%"


@st.cache_resource
def get_con(path: str, mtime: float):  # mtime busts the cache when the database is rebuilt
    return duckdb.connect(path, read_only=True)


def empty_state(
    message: str = "No orders match the current filters. Widen the date range or clear a filter.",
) -> None:
    st.info(message)


def render_overview(con, f: kpis.Filters) -> None:
    o = kpis.overview(con, f)
    if not o["orders"]:
        return empty_state()
    cols = st.columns(6)
    items = [
        ("Orders", f"{o['orders']:,}", "Orders"),
        ("GMV", money(o["gmv"]), "GMV"),
        ("Avg order value", money(o["aov"]), "Average order value"),
        ("On-time rate", pct(o["on_time_rate"]), "On-time rate"),
        (
            "Avg review score",
            "n/a" if o["avg_review_score"] is None else f"{o['avg_review_score']:.2f}",
            "Average review score",
        ),
        ("Cancellation rate", pct(o["cancellation_rate"]), "Cancellation rate"),
    ]
    for col, (name, value, key) in zip(cols, items, strict=True):
        col.metric(name, value, help=kpis.KPI_DEFINITIONS[key])
    st.caption(
        f"Delivery KPIs use {o['delivered_scored']:,} delivered orders; review score uses {o['reviewed_orders']:,} reviewed orders."
    )
    trend = kpis.monthly_trend(con, f)
    left, right = st.columns(2)
    fig = px.bar(
        trend,
        x="month",
        y="gmv",
        labels={"gmv": "GMV", "month": ""},
        color_discrete_sequence=[ACCENT],
    )
    fig.update_layout(title="GMV by purchase month")
    left.plotly_chart(style(fig), use_container_width=True)
    fig = px.line(
        trend,
        x="month",
        y="late_rate",
        markers=True,
        labels={"late_rate": "Late rate", "month": ""},
        color_discrete_sequence=[ALERT],
    )
    fig.update_layout(title="Late-delivery rate by purchase month", yaxis_tickformat=".0%")
    right.plotly_chart(style(fig), use_container_width=True)
    st.caption(
        "Recent months can be incomplete: orders still in transit have no delivery outcome yet."
    )


def render_products(con, f: kpis.Filters) -> None:
    cat, states = kpis.category_breakdown(con, f), kpis.state_breakdown(con, f)
    if cat.empty:
        return empty_state()
    left, right = st.columns(2)
    fig = px.bar(
        cat.sort_values("gmv"),
        x="gmv",
        y="category",
        orientation="h",
        color_discrete_sequence=[ACCENT],
        labels={"gmv": "GMV", "category": ""},
    )
    fig.update_layout(title="Top categories by GMV")
    left.plotly_chart(style(fig, 420), use_container_width=True)
    fig = px.bar(
        states.sort_values("gmv"),
        x="gmv",
        y="state",
        orientation="h",
        color_discrete_sequence=["#374151"],
        labels={"gmv": "GMV", "state": "Customer state"},
    )
    fig.update_layout(title="GMV by customer state")
    right.plotly_chart(style(fig, 420), use_container_width=True)
    st.subheader("Sellers with at least 30 orders")
    sellers = kpis.seller_breakdown(con, f)
    if sellers.empty:
        st.info("No seller has 30+ orders under these filters.")
    else:
        st.dataframe(
            sellers.rename(columns={"delivered_scored": "delivered (n)"}),
            hide_index=True,
            use_container_width=True,
            column_config={
                "gmv": st.column_config.NumberColumn("GMV", format="%.0f"),
                "late_rate": st.column_config.NumberColumn("Late rate", format="percent"),
                "avg_review_score": st.column_config.NumberColumn("Avg review", format="%.2f"),
            },
        )
        st.caption(
            "Small per-seller samples are noisy; treat extremes as prompts to investigate, not verdicts."
        )


def render_delivery(con, f: kpis.Filters) -> None:
    route, rbd, states = (
        kpis.route_late_rate(con, f),
        kpis.review_by_delay(con, f),
        kpis.state_breakdown(con, f),
    )
    if route.empty:
        return empty_state()
    left, right = st.columns(2)
    fig = px.bar(
        route,
        x="route",
        y="late_rate",
        text=route["late_rate"].map(pct),
        color_discrete_sequence=[ALERT],
        labels={"late_rate": "Late rate", "route": ""},
    )
    fig.update_layout(title="Late rate: same-state vs cross-state", yaxis_tickformat=".0%")
    left.plotly_chart(style(fig), use_container_width=True)
    fig = px.bar(
        rbd,
        x="delivery_outcome",
        y="avg_review_score",
        text=rbd["avg_review_score"].round(2),
        color_discrete_sequence=[ACCENT],
        labels={"avg_review_score": "Avg review score", "delivery_outcome": ""},
    )
    fig.update_layout(title="Review score by delivery outcome", yaxis_range=[1, 5])
    right.plotly_chart(style(fig), use_container_width=True)
    st.caption(
        "Association, not causation: only customers who chose to review are counted, and product quality is not controlled."
    )
    fig = px.scatter(
        states,
        x="avg_delivery_days",
        y="late_rate",
        size="delivered_scored",
        hover_name="state",
        labels={"avg_delivery_days": "Avg delivery days", "late_rate": "Late rate"},
        color_discrete_sequence=["#374151"],
    )
    fig.update_layout(
        title="States: delivery time vs late rate (bubble = delivered orders)",
        yaxis_tickformat=".0%",
    )
    st.plotly_chart(style(fig, 380), use_container_width=True)


def render_customers(con, f: kpis.Filters) -> None:
    coh = kpis.repeat_cohorts(con, f)
    if coh.empty:
        return empty_state("No cohort has been observed for 90 days under these filters.")
    fig = px.bar(
        coh,
        x="cohort_month",
        y="repeat_rate_90d",
        hover_data=["customers"],
        color_discrete_sequence=[ACCENT],
        labels={"repeat_rate_90d": "Repeat within 90 days", "cohort_month": "First-order month"},
    )
    fig.update_layout(title="90-day repeat rate by first-order cohort", yaxis_tickformat=".1%")
    st.plotly_chart(style(fig), use_container_width=True)
    st.caption(
        kpis.KPI_DEFINITIONS["Repeat rate (90d)"]
        + " Cohorts with under 90 days of observation are omitted."
    )
    st.subheader("Customer segments (rule-based, whole dataset)")
    st.dataframe(kpis.customer_segments(con), hide_index=True, use_container_width=True)


def render_decision_room() -> None:
    meta_path, scored_path = (
        PROCESSED / "models" / "late_delivery_metadata.json",
        PROCESSED / "models" / "late_delivery_scored_test.parquet",
    )
    if not (meta_path.exists() and scored_path.exists()):
        return st.info(
            "No trained model found. Run `signalforge train` to enable the Decision Room."
        )
    meta, scored = json.loads(meta_path.read_text()), pd.read_parquet(scored_path)
    rep, chosen = meta["report"], meta["report"]["chosen_model"]
    st.markdown(
        "**Question:** which orders should operations review first to catch late deliveries, given limited capacity?"
    )
    label("pred")
    t, b = rep["test"][chosen], rep["test"]["baseline_prior"]
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Model PR-AUC (held-out later window)",
        f"{t['pr_auc']:.3f}",
        help="Average precision on the final, chronologically latest 20% of orders.",
    )
    c2.metric("Baseline PR-AUC (always predict the base rate)", f"{b['pr_auc']:.3f}")
    c3.metric(
        "Cross-state rule recall / precision",
        f"{pct(rep['test']['rule_cross_state']['recall'], 0)} / {pct(rep['test']['rule_cross_state']['precision'], 0)}",
    )
    st.caption(
        f"Model: {chosen}. Trained on {rep['split']['train']['n']:,} orders up to {rep['split']['train']['to'][:10]}; tested on {rep['split']['test']['n']:,} orders from {rep['split']['test']['from'][:10]}. Data source: {meta['data_source']}."
    )
    if t["pr_auc"] < 1.5 * rep["test"]["baseline_prior"]["pr_auc"]:
        st.warning(
            "On this held-out window the model ranks late orders only modestly better than the base rate "
            f"(PR-AUC {t['pr_auc']:.3f} vs {b['pr_auc']:.3f}). Treat prioritization as weak evidence and "
            "compare it with the simple cross-state rule above before acting."
        )
    share = st.slider(
        "Share of orders operations can review (highest risk first)",
        0.05,
        0.5,
        0.2,
        0.05,
        format="%.2f",
    )
    ev = scenarios.holdout_outcome(scored, share)
    label("fact")
    st.markdown(
        f"On the held-out window, reviewing the top **{share:.0%}** of orders by model risk means **{ev['orders_flagged']:,}** orders, of which **{ev['late_orders_caught']:,}** were actually late - **{ev['recall']:.0%}** of the **{ev['late_orders_in_holdout']:,}** late orders. Precision {ev['precision']:.0%} vs {ev['base_late_rate']:.0%} base rate (lift {ev['lift_vs_random']:.2f}x)."
    )
    table = scenarios.threshold_table(scored)
    fig = px.line(
        table,
        x="review_share",
        y=["precision", "recall"],
        markers=True,
        labels={"value": "", "review_share": "Share of orders reviewed", "variable": ""},
        color_discrete_sequence=[ACCENT, ALERT],
    )
    fig.update_layout(
        title="Precision and recall by share of orders reviewed (held-out window)",
        yaxis_tickformat=".0%",
        xaxis_tickformat=".0%",
    )
    st.plotly_chart(style(fig, 300), use_container_width=True)
    st.markdown("#### What-if (you supply the assumptions)")
    label("scen")
    c1, c2, c3 = st.columns(3)
    succ = c1.number_input(
        "Share of flagged late orders an intervention rescues (0-1; 0 = unknown)",
        0.0,
        1.0,
        0.0,
        0.05,
    )
    cost = c2.number_input("Cost per intervention (0 = unknown)", 0.0, value=0.0)
    val = c3.number_input("Value of avoiding one late order (0 = unknown)", 0.0, value=0.0)
    a = scenarios.Assumptions(succ or None, cost or None, val or None)
    res = scenarios.scenario(scored, share, a)
    if "late_orders_avoided" in res:
        st.write(
            f"If the intervention rescues {succ:.0%} of caught late orders, about **{res['late_orders_avoided']:.1f}** late deliveries are avoided in a window of this size."
        )
    if "net_value" in res:
        st.write(
            f"Under your inputs, net value = **{res['net_value']:,.0f}** (avoided x value - cost)."
        )
    if res["missing_inputs"]:
        st.caption(
            "Not computed because not provided: "
            + "; ".join(res["missing_inputs"])
            + ". The dataset contains no cost or benefit data, so none is assumed."
        )
    with st.expander("Model limitations and segment errors"):
        st.markdown(
            "- Only delivered orders carry a label; orders still in transit at extract time are missing, which biases the latest period.\n- The model estimates association-based risk and says nothing about what *causes* lateness.\n- Performance is for the held-out window shown above and may not hold for other periods."
        )
        for col, rows in rep["segments_test"].items():
            st.markdown(f"**By {col}** (segments with enough orders)")
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_forecast(con) -> None:
    st.markdown(
        "**Question:** how many sales orders should we expect in the coming weeks, and is the model better than a naive guess?"
    )
    measure = st.radio(
        "Series",
        ["orders", "gmv"],
        horizontal=True,
        format_func=lambda m: {"orders": "Weekly orders", "gmv": "Weekly GMV"}[m],
    )
    series = forecast.weekly_series(con, measure)
    try:
        res = forecast.evaluate(series)
    except ValueError as exc:
        return st.info(f"Forecast unavailable: {exc}.")
    label("fact")
    st.caption(
        f"{res['weeks_total']} complete weeks ({series['week_start'].min():%Y-%m-%d} to {series['week_start'].max():%Y-%m-%d}); partial first/last weeks dropped."
    )
    fig = go.Figure()
    fig.add_scatter(
        x=series["week_start"], y=series["value"], name="Observed", line=dict(color=INK, width=2)
    )
    st.plotly_chart(
        style(fig.update_layout(title="Observed weekly series")), use_container_width=True
    )
    label("pred")
    m, bt, fut = res["metrics"], res["backtest"], res["future"]
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Model MAE (held-out weeks)",
        f"{m['holt']['mae']:,.1f}",
        help="Damped-trend smoothing fitted on earlier weeks only.",
    )
    base = res["best_baseline"]
    c2.metric(f"Best baseline MAE ({base.replace('_', ' ')})", f"{m[base]['mae']:,.1f}")
    c3.metric(
        "80% interval coverage (backtest)",
        pct(m["holt"]["coverage_80"], 0),
        help="Share of held-out weeks inside the interval; tiny sample, nominal 80%.",
    )
    gain = 1 - m["holt"]["mae"] / m[base]["mae"] if m[base]["mae"] else 0.0
    bname, hz = base.replace("_", " "), res["horizon"]
    mae_pair = f"MAE {m['holt']['mae']:,.1f} vs {m[base]['mae']:,.1f}"
    if gain >= 0.05:
        st.success(
            f"On the last {hz} weeks the model beat the best baseline by {gain:.0%} ({mae_pair}). "
            f"That is {hz} data points; treat it as modest evidence."
        )
    elif gain > -0.05:
        st.info(
            f"The model and the {bname} baseline are effectively tied on the held-out weeks "
            f"({mae_pair}). The simpler baseline is as good a guide."
        )
    else:
        st.warning(
            f"The model did NOT beat the {bname} baseline on the held-out weeks ({mae_pair}). "
            "Prefer the simpler baseline."
        )
    fig = go.Figure()
    fig.add_scatter(
        x=bt["week_start"], y=bt["actual"], name="Actual", line=dict(color=INK, width=2)
    )
    for col, name, color in (
        ("holt", "Model", ACCENT),
        ("naive", "Naive", "#9ca3af"),
        ("moving_average", "4-wk average", ALERT),
    ):
        fig.add_scatter(
            x=bt["week_start"],
            y=bt[col],
            name=name,
            line=dict(color=color, dash="dot" if col != "holt" else "solid"),
        )
    st.plotly_chart(
        style(
            fig.update_layout(
                title="Backtest: held-out weeks, forecasts made from earlier data only"
            )
        ),
        use_container_width=True,
    )
    fig = go.Figure()
    fig.add_scatter(
        x=series["week_start"].tail(26),
        y=series["value"].tail(26),
        name="Observed",
        line=dict(color=INK, width=2),
    )
    fig.add_scatter(
        x=fut["week_start"], y=fut["hi80"], line=dict(width=0), showlegend=False, hoverinfo="skip"
    )
    fig.add_scatter(
        x=fut["week_start"],
        y=fut["lo80"],
        fill="tonexty",
        fillcolor="rgba(11,122,107,.18)",
        line=dict(width=0),
        name="80% interval (approx.)",
    )
    fig.add_scatter(
        x=fut["week_start"], y=fut["forecast"], name="Forecast", line=dict(color=ACCENT, width=3)
    )
    st.plotly_chart(
        style(fig.update_layout(title=f"Forecast: next {res['horizon']} weeks")),
        use_container_width=True,
    )
    st.caption(
        "Interval is approximate: normal errors scaled from in-sample one-step residuals. A forecast extrapolates the past; it is not a promise and says nothing about causes. In demo mode the series comes from a generator."
    )


def render_quality(con, source: str) -> None:
    summary_path = PROCESSED / "run_summary.json"
    manifest_path = PROCESSED.parent / "interim" / "bronze_manifest.json"
    prov_path = PROCESSED.parent / "interim" / "raw_provenance.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Data mode", "Real" if source == "olist" else "Synthetic demo")
    c2.metric(
        "Last successful build",
        datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
    )
    c3.metric("Blocking checks failed", summary.get("checks_failed_error", "n/a"))
    if source == "olist":
        if prov_path.exists():
            prov = json.loads(prov_path.read_text())
            st.markdown(
                f"**Source:** {prov['dataset']} - <{prov['url']}> - licence {prov['license']}. Verified {prov['verified_at']}."
            )
        else:
            st.warning(
                "Real-data mode but no `raw_provenance.json`. Run `signalforge verify-raw` to record hashes and row counts."
            )
    else:
        st.info(
            "Synthetic data from `signalforge.demo.synthetic`. No real source, licence or attribution applies."
        )
    st.markdown("#### Lineage")
    st.code(
        "raw CSV -> bronze (text, hashed) -> silver (typed, de-duplicated) -> gold (facts, dimensions, marts) -> KPIs / dashboard / model",
        language="text",
    )
    left, right = st.columns(2)
    if manifest_path.exists():
        man = json.loads(manifest_path.read_text())
        left.markdown("**Bronze load (rows, SHA-256 prefix)**")
        left.dataframe(
            pd.DataFrame(
                [
                    {"table": k, "rows": v["rows"], "sha256": v["sha256"][:12]}
                    for k, v in man.items()
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    if summary.get("gold_rows"):
        right.markdown("**Gold tables (rows)**")
        right.dataframe(
            pd.DataFrame([{"table": k, "rows": v} for k, v in summary["gold_rows"].items()]),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown("#### Quality checks (re-run live against the warehouse)")
    results = run_checks(con, raise_on_error=False)
    frame = pd.DataFrame(
        [
            {
                "status": "PASS" if r.passed else "FAIL",
                "severity": r.check.severity,
                "check": r.check.name,
                "violations": r.violations,
                "note": r.check.description,
            }
            for r in results
        ]
    )
    failed_blocking = int(((frame["status"] == "FAIL") & (frame["severity"] == "error")).sum())
    (st.error if failed_blocking else st.success)(
        f"{len(frame) - int((frame['status'] == 'FAIL').sum())} of {len(frame)} checks pass; {failed_blocking} blocking failure(s)."
    )
    st.dataframe(
        frame.sort_values(["status", "severity"], ascending=[False, True]),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "Warnings are informative (for example orders without a category) and do not stop the build."
    )


def render_definitions() -> None:
    st.markdown("#### KPI definitions")
    for k, v in kpis.KPI_DEFINITIONS.items():
        st.markdown(f"**{k}.** {v}")
    st.markdown("#### How outputs are labelled")
    st.markdown(
        "- **Observed historical fact:** computed directly from validated data.\n- **Model prediction / forecast:** a score or projection with a baseline and a held-out later time window.\n- **Scenario:** a what-if that depends on assumptions you enter; never a forecast.\n- **Causal claims** are not made anywhere in this app."
    )
    st.markdown("#### Model cards")
    meta_path = PROCESSED / "models" / "late_delivery_metadata.json"
    st.markdown(
        "**Late-delivery risk (classification).** Target: delivered after the estimated date. Prediction time: order placement. Excluded as post-outcome: delivery timestamps, review score, approval time, status. Split: chronological 60/20/20, preprocessing fitted on train only, threshold chosen on validation. Baselines: base rate and a cross-state rule."
    )
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        st.caption(
            f"Features: {', '.join(meta['features'])}. Seed {meta['settings']['seed']}. sklearn {meta['versions']['sklearn']}. Data source: {meta['data_source']}."
        )
    st.markdown(
        "**Weekly demand forecast.** Damped-trend exponential smoothing, parameters by one-step in-sample error, last 8 complete weeks held out, compared with naive and 4-week-average baselines. Approximate normal intervals."
    )
    st.markdown("#### Reproducibility")
    st.markdown(
        "`signalforge demo-data && signalforge build && signalforge reconcile && signalforge train && signalforge dashboard`. Seeds are fixed; the build is atomic."
    )


def main() -> None:
    st.set_page_config(page_title="SIGNALFORGE", page_icon=":hammer_and_wrench:", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    if not DB_PATH.exists():
        st.markdown(
            '<div class="sf-hero"><div><p class="sf-brand">SIGNAL<span>FORGE</span></p><p class="sf-tag">From Raw Data to Better Decisions.</p></div></div>',
            unsafe_allow_html=True,
        )
        st.error(
            f"Warehouse not found at `{DB_PATH}`. Run `signalforge demo-data` (synthetic) or add the Olist CSVs, then `signalforge build`."
        )
        st.stop()
    try:
        con = get_con(str(DB_PATH), DB_PATH.stat().st_mtime)
        source = con.execute("SELECT data_source FROM gold.meta").fetchone()[0]
        opts = kpis.filter_options(con)
    except Exception as exc:  # surface a readable state instead of a stack trace
        st.error(f"Could not read the warehouse: {exc}")
        st.stop()
    real = source == "olist"
    built = datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f'<div class="sf-hero"><div><p class="sf-brand">SIGNAL<span>FORGE</span></p><p class="sf-tag">From Raw Data to Better Decisions.</p></div>'
        f'<div class="sf-pills"><span class="sf-pill {"real" if real else "synth"}">{"Real data" if real else "Synthetic demo"}</span>'
        f'<span class="sf-pill">Built {built}</span><span class="sf-pill">{opts["date_min"]} to {opts["date_max"]}</span></div></div>',
        unsafe_allow_html=True,
    )
    if not real:
        st.markdown(
            '<div class="sf-banner"><b>Synthetic demo data.</b> Every number here describes a seeded generator, not a real business.</div>',
            unsafe_allow_html=True,
        )
    with st.sidebar:
        st.header("Filters")
        rng = st.date_input(
            "Purchase date",
            (opts["date_min"], opts["date_max"]),
            min_value=opts["date_min"],
            max_value=opts["date_max"],
        )
        states = st.multiselect("Customer state", opts["states"])
        cats = st.multiselect("Primary category", opts["categories"])
        st.caption(
            "Filters apply to the Overview, Products, Delivery and Customers tabs. Forecast, Decision Room and Data views use fixed scopes."
        )
    d_from, d_to = (
        (rng[0], rng[1])
        if isinstance(rng, tuple) and len(rng) == 2
        else (opts["date_min"], opts["date_max"])
    )
    f = kpis.Filters(d_from, d_to, tuple(states), tuple(cats))
    names = [
        "Overview",
        "Products & sellers",
        "Delivery & experience",
        "Customers",
        "Trends & forecast",
        "Decision Room",
        "Data & quality",
        "Definitions & methods",
    ]
    tabs = st.tabs(names)
    for tab, fn in zip(
        tabs[:4], (render_overview, render_products, render_delivery, render_customers), strict=True
    ):
        with tab:
            fn(con, f)
    with tabs[4]:
        render_forecast(con)
    with tabs[5]:
        render_decision_room()
    with tabs[6]:
        render_quality(con, source)
    with tabs[7]:
        render_definitions()


main()
