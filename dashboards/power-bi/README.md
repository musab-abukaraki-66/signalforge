# Power BI handoff

**Status: handoff material only. No `.pbix` or `.pbip` file exists** (Power BI Desktop is not available in this environment). The working dashboard is the Streamlit app (`signalforge dashboard`). Everything below lets someone build the Power BI report on the same gold layer with identical definitions.

## 1. Data source

Run `signalforge build`. Gold tables are written as Parquet to `data/processed/gold/` (and live in the DuckDB file). In Power BI Desktop use *Get data > Parquet* on each file below (or the DuckDB ODBC driver).

## 2. Data model (star schema)

| Table | Grain | Key |
|---|---|---|
| `fact_order` | one row per order | `order_id` |
| `fact_order_item` | one row per order item | `order_id` + `order_item_id` |
| `fact_payment` | one row per payment record | `order_id` + `payment_sequential` |
| `fact_review` | one row per review | `review_id` + `order_id` |
| `dim_date` | one row per day | `date_key` |
| `dim_customer` | one row per `customer_id` (per-order id) | `customer_id` |
| `dim_seller` | one row per seller | `seller_id` |
| `dim_product` | one row per product | `product_id` |
| `mart_customer_rfm` | one row per person (`customer_unique_id`) | `customer_unique_id` |

Relationships (all many-to-one, single direction from dimension to fact):

- `dim_date[date_key]` -> `fact_order[purchase_date]` (active), `fact_order_item[purchase_date]`
- `dim_customer[customer_id]` -> `fact_order[customer_id]`
- `fact_order[order_id]` -> `fact_order_item`, `fact_payment`, `fact_review` (one-to-many, single direction)
- `dim_product[product_id]` -> `fact_order_item[product_id]`
- `dim_seller[seller_id]` -> `fact_order_item[seller_id]`

Do **not** sum `fact_order[items_value]` after filtering through `fact_order_item` relationships (it repeats per item). Use the measures below.

## 3. Measures (DAX), matching `KPI_DEFINITIONS` in `src/signalforge/analytics/kpis.py`

```dax
Sales Orders = CALCULATE ( DISTINCTCOUNT ( fact_order[order_id] ),
    NOT ( fact_order[order_status] IN { "canceled", "unavailable" } ) )

GMV = CALCULATE ( SUM ( fact_order[items_value] ),
    NOT ( fact_order[order_status] IN { "canceled", "unavailable" } ) )

Avg Order Value = DIVIDE ( [GMV],
    CALCULATE ( COUNTROWS ( fact_order ), NOT ( fact_order[order_status] IN { "canceled", "unavailable" } ),
                NOT ( ISBLANK ( fact_order[items_value] ) ) ) )

Freight Share = DIVIDE (
    CALCULATE ( SUM ( fact_order[freight_value] ), NOT ( fact_order[order_status] IN { "canceled", "unavailable" } ) ),
    [GMV] )

Late Rate = DIVIDE ( CALCULATE ( COUNTROWS ( fact_order ), fact_order[is_late] = TRUE () ),
    CALCULATE ( COUNTROWS ( fact_order ), NOT ( ISBLANK ( fact_order[is_late] ) ) ) )

On-time Rate = 1 - [Late Rate]

Avg Delivery Days = AVERAGE ( fact_order[delivery_days] )

Avg Review Score = AVERAGE ( fact_order[review_score] )

Cancellation Rate = DIVIDE ( CALCULATE ( COUNTROWS ( fact_order ), fact_order[order_status] = "canceled" ),
    COUNTROWS ( fact_order ) )
```

Validation: with no filters, each measure must equal the values printed by `signalforge reconcile`.

## 4. Page plan

1. **Overview** - KPI cards (Sales Orders, GMV, Avg Order Value, On-time Rate, Avg Review Score, Cancellation Rate); GMV by `purchase_month`; Late Rate by `purchase_month`. Slicers: date, customer state, primary category.
2. **Products and sellers** - GMV by category (from `fact_order_item` + `dim_product`); GMV by customer state; seller table (filter to sellers with 30+ orders).
3. **Delivery and experience** - late rate same-state vs cross-state; review score by delivery outcome; state scatter (delivery days vs late rate). Footnote: association, not causation.
4. **Customers** - 90-day repeat rate by cohort (needs a calculated table or compute in the Parquet layer), segment counts from `mart_customer_rfm`.
5. **Definitions** - one text box per KPI, copied from this file.

The model output (late-delivery risk) and the Decision Room are in the Streamlit app only; `data/processed/models/late_delivery_scored_test.parquet` can be loaded as an extra table if a risk page is wanted.

## 5. Rules

- Say "GMV" or "order value", never "revenue" or "profit".
- Show group sizes next to every rate.
- If the data source is the synthetic generator, put a visible banner on every page.
