"""SIGNALFORGE dashboard (Streamlit). Run with ``signalforge dashboard``.

Every number comes from the gold layer through ``signalforge.analytics.kpis`` (one definition
per KPI) or from the saved model artifacts. Nothing is hard-coded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from signalforge.analytics import kpis
from signalforge.decision_engine import scenarios

INK, MUTED, ACCENT, ALERT, GRID = "#16213e", "#5b6578", "#0f766e", "#b45309", "#e5e7eb"
DB_PATH = Path(os.environ.get("SIGNALFORGE_DB", "data/processed/signalforge.duckdb"))
PROCESSED = Path(os.environ.get("SIGNALFORGE_PROCESSED", DB_PATH.parent))

CSS = f"""
<style>
.block-container {{ padding-top: 4rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; color: {INK}; }}
.sf-brand {{ font-size: 1.9rem; font-weight: 700; color: {INK}; margin: 0; }}
.sf-brand span {{ color: {ACCENT}; }}
.sf-tag {{ color: {MUTED}; margin: 0 0 .8rem 0; }}
.sf-banner {{ border-left: 4px solid {ALERT}; background: #fffbeb; color: #78350f;
              padding: .6rem .9rem; border-radius: 4px; margin-bottom: 1rem; font-size: .92rem; }}
.sf-label {{ display:inline-block; font-size:.72rem; font-weight:600; letter-spacing:.04em;
             text-transform:uppercase; padding:.15rem .5rem; border-radius:3px; margin-bottom:.3rem; }}
.sf-fact {{ background:#e6f4f1; color:#115e59; }}
.sf-pred {{ background:#e0e7ff; color:#3730a3; }}
.sf-scen {{ background:#fef3c7; color:#92400e; }}
[data-testid="stMetricValue"] {{ font-size: 1.6rem; color: {INK}; }}
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
        color_discrete_sequence=[INK],
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
        color_discrete_sequence=[INK],
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


def render_definitions() -> None:
    st.markdown("#### KPI definitions")
    for k, v in kpis.KPI_DEFINITIONS.items():
        st.markdown(f"**{k}.** {v}")
    st.markdown("#### How outputs are labelled")
    st.markdown(
        "- **Observed historical fact:** computed directly from validated data.\n- **Model prediction:** a risk score with a baseline and a held-out later time window.\n- **Scenario:** a what-if that depends on assumptions you enter; never a forecast.\n- **Causal claims** are not made anywhere in this app."
    )


def main() -> None:
    st.set_page_config(page_title="SIGNALFORGE", page_icon=":hammer_and_wrench:", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<p class="sf-brand">SIGNAL<span>FORGE</span></p><p class="sf-tag">From Raw Data to Better Decisions.</p>',
        unsafe_allow_html=True,
    )
    if not DB_PATH.exists():
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
    if source != "olist":
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
            "Filters apply to orders. The Decision Room uses the fixed held-out test window."
        )
    d_from, d_to = (
        (rng[0], rng[1])
        if isinstance(rng, tuple) and len(rng) == 2
        else (opts["date_min"], opts["date_max"])
    )
    f = kpis.Filters(d_from, d_to, tuple(states), tuple(cats))
    tabs = st.tabs(
        [
            "Overview",
            "Products & sellers",
            "Delivery & experience",
            "Customers",
            "Decision Room",
            "Definitions",
        ]
    )
    for tab, fn in zip(
        tabs[:4], (render_overview, render_products, render_delivery, render_customers), strict=True
    ):
        with tab:
            fn(con, f)
    with tabs[4]:
        render_decision_room()
    with tabs[5]:
        render_definitions()


main()
