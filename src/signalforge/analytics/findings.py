"""Reproducible findings report. Every finding states metric definition, period, group sizes,
the supporting calculation and a limitation. Observations are numbers pulled from the data;
interpretation is labelled and never causal."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from signalforge.analytics import kpis


@dataclass(frozen=True)
class Finding:
    title: str
    observation: str
    definition: str
    period: str
    n: str
    calculation: str
    limitation: str
    interpretation: str = ""


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def build_findings(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    opts = kpis.filter_options(con)
    period = f"{opts['date_min']} to {opts['date_max']} (purchase date)"
    out: list[Finding] = []

    cat = kpis.category_breakdown(con, limit=1000)
    total = cat["gmv"].sum()
    top5 = cat.head(5)
    out.append(
        Finding(
            "GMV concentration by category",
            f"The top 5 of {len(cat)} categories hold {_pct(top5['gmv'].sum() / total)} of GMV: "
            + ", ".join(f"{r.category} ({_pct(r.gmv / total)})" for r in top5.itertuples())
            + ".",
            "GMV = sum of item price (freight excluded), orders not canceled/unavailable.",
            period,
            f"{int(cat['orders'].sum())} order-category pairs, {len(cat)} categories",
            "fact_order_item JOIN dim_product, grouped by category (kpis.category_breakdown)",
            "Category is the product's category; an order with several categories counts in each.",
        )
    )

    route = kpis.route_late_rate(con).set_index("route")
    if {"Same state", "Different state"} <= set(route.index):
        s, d = route.loc["Same state"], route.loc["Different state"]
        out.append(
            Finding(
                "Late delivery differs by seller-customer route",
                f"Late rate is {_pct(d.late_rate)} when seller and customer are in different states "
                f"(n={int(d.delivered_scored)}) versus {_pct(s.late_rate)} in the same state "
                f"(n={int(s.delivered_scored)}).",
                "Late = delivered date later than estimated date (day resolution); delivered "
                "orders only; seller = primary item's seller.",
                period,
                f"{int(s.delivered_scored + d.delivered_scored)} delivered orders",
                "kpis.route_late_rate",
                "Route is correlated with distance, carrier and estimate quality; no control for these.",
                "Association only. Cross-state orders travel further, which this analysis cannot separate "
                "from seller or carrier effects.",
            )
        )

    rd = kpis.review_by_delay(con).set_index("delivery_outcome")
    on_time = rd[rd.index.str.startswith(("1", "2"))]
    late = rd[rd.index.str.startswith(("3", "4"))]
    if len(late) and len(on_time):
        w_on = (on_time["avg_review_score"] * on_time["reviewed_orders"]).sum() / on_time[
            "reviewed_orders"
        ].sum()
        w_late = (late["avg_review_score"] * late["reviewed_orders"]).sum() / late[
            "reviewed_orders"
        ].sum()
        out.append(
            Finding(
                "Review scores are lower for late orders",
                f"Mean review score is {w_late:.2f} for late orders (n={int(late['reviewed_orders'].sum())}) "
                f"versus {w_on:.2f} for on-time orders (n={int(on_time['reviewed_orders'].sum())}).",
                "Review score = most recent review per order (1-5); late/on-time as defined above.",
                period,
                f"{int(rd['reviewed_orders'].sum())} reviewed delivered orders",
                "kpis.review_by_delay",
                "Only customers who chose to review are included; product quality is not controlled.",
                "Lateness is associated with lower scores; this does not show that fixing lateness "
                "would raise scores.",
            )
        )

    trend = kpis.monthly_trend(con)
    full = trend.iloc[1:-1] if len(trend) > 2 else trend  # first/last months may be partial
    if len(full):
        peak = full.loc[full["orders"].idxmax()]
        out.append(
            Finding(
                "Order volume trend",
                f"Between {full.iloc[0]['month']} and {full.iloc[-1]['month']} monthly orders moved from "
                f"{int(full.iloc[0]['orders'])} to {int(full.iloc[-1]['orders'])}; the peak month is "
                f"{peak['month']} with {int(peak['orders'])} orders.",
                "Orders = distinct orders not canceled/unavailable, by purchase month.",
                period,
                f"{len(full)} complete months",
                "kpis.monthly_trend (first and last month excluded as possibly partial)",
                "No seasonality adjustment; a single peak does not establish a seasonal pattern.",
            )
        )

    sellers = kpis.seller_breakdown(con, min_orders=30, limit=1000)
    if len(sellers):
        worst = (
            sellers.dropna(subset=["late_rate"]).sort_values("late_rate", ascending=False).head(3)
        )
        out.append(
            Finding(
                "Sellers with the highest late rates (volume-qualified)",
                "Among sellers with at least 30 orders: "
                + "; ".join(
                    f"{r.seller_id} late {_pct(r.late_rate)} (n={int(r.delivered_scored)})"
                    for r in worst.itertuples()
                )
                + ".",
                "Late rate on orders whose primary seller is the listed seller.",
                period,
                f"{len(sellers)} qualifying sellers",
                "kpis.seller_breakdown (min_orders=30)",
                "Small samples per seller give wide uncertainty; ranking extremes of many sellers "
                "overstates differences.",
                "A prompt to investigate, not a verdict on the sellers.",
            )
        )

    coh = kpis.repeat_cohorts(con)
    if len(coh):
        rate = (coh["repeat_rate_90d"] * coh["customers"]).sum() / coh["customers"].sum()
        out.append(
            Finding(
                "Repeat purchasing within 90 days",
                f"{_pct(rate)} of {int(coh['customers'].sum())} customers in fully observed cohorts "
                "placed a second delivered order within 90 days of their first.",
                kpis.KPI_DEFINITIONS["Repeat rate (90d)"],
                f"cohorts {coh['cohort_month'].iloc[0]} to {coh['cohort_month'].iloc[-1]}",
                f"{len(coh)} cohorts",
                "kpis.repeat_cohorts",
                "The observation window is short; customers can buy again later or under a new id.",
            )
        )
    return out


def render_markdown(findings: list[Finding], data_source: str) -> str:
    lines = ["# Findings", ""]
    if data_source != "olist":
        lines += [
            "> **SYNTHETIC DEMO DATA.** These numbers describe a seeded generator, not any real "
            "business. Do not cite them as findings.",
            "",
        ]
    for i, f in enumerate(findings, 1):
        lines += [
            f"## {i}. {f.title}",
            "",
            f"**Observation.** {f.observation}",
            "",
            f"- **Metric definition:** {f.definition}",
            f"- **Period:** {f.period}",
            f"- **Group size:** {f.n}",
            f"- **Calculation:** {f.calculation}",
            f"- **Limitation:** {f.limitation}",
        ]
        if f.interpretation:
            lines.append(f"- **Interpretation (not causal):** {f.interpretation}")
        lines.append("")
    return "\n".join(lines)
