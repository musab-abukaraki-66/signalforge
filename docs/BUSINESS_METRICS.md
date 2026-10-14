# Business questions and metrics

## Definitions that must not be mixed up

| Term | Meaning | Typical source fields |
|---|---|---|
| **Order value** | What the customer is charged for an order: items plus freight | item price + freight, or total payments |
| **GMV** (gross merchandise value) | Total value of goods sold through the marketplace, before returns, cancellations and fees; definition must state whether freight is included | item price (and optionally freight), filtered by agreed order status |
| **Recognised revenue** | What the marketplace itself earns (for example commission or fees) under its accounting policy | commission and fee data, **not present in a public order dataset** |
| **Profit** | Revenue minus costs | cost data, **not present** |

These are not interchangeable and cannot be derived from the same fields. A public order dataset supports order value and GMV-style measures. It does **not** support revenue or profit unless commission and cost data exist. SIGNALFORGE will say "GMV" or "order value" and never "revenue" or "profit" for these measures.

Also note: payment totals and item totals can differ (vouchers, installments, rounding), so reconcile and document the chosen source per metric.

## Business questions

1. How is order volume trending, and what is seasonal?
2. How does GMV and average order value vary by category, region and seller?
3. How often are orders delivered late versus the estimated date, and where?
4. Which factors are associated with low review scores?
5. How many customers buy again, and how soon?
6. Which sellers or categories drive disproportionate delays or complaints?

## Candidate KPIs

| KPI | Definition (to be validated) | Grain / filter |
|---|---|---|
| Order volume | Count of distinct orders | By purchase date; state which statuses count |
| GMV | Sum of item price (freight shown separately) | Delivered or otherwise agreed statuses |
| Average order value | GMV (or order value) / distinct orders | Same filter as the numerator |
| On-time delivery rate | Delivered orders with delivery date <= estimated date / delivered orders | Delivered orders only |
| Average delivery time | Days from purchase to delivery | Delivered orders only |
| Average review score | Mean score | Rule for multiple reviews per order must be stated |
| Repeat purchase rate | Customers with 2 or more orders / customers | Needs the persistent customer id, not a per-order id |

Every KPI is checked against an independent calculation before it is published (milestone 4).
