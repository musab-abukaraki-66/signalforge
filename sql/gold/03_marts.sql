-- GOLD marts for analysis.

-- grain: one row per customer_unique_id. Delivered orders only; as-of date is the last purchase
-- date in the extract (so recency is relative to the data, not today).
CREATE OR REPLACE TABLE gold.mart_customer_rfm AS
WITH as_of AS (SELECT max(purchase_date) AS d FROM gold.fact_order),
agg AS (
    SELECT customer_unique_id,
           count(*) AS frequency,
           sum(coalesce(items_value, 0)) AS monetary,
           max(purchase_date) AS last_purchase_date,
           min(purchase_date) AS first_purchase_date
    FROM gold.fact_order WHERE order_status = 'delivered' GROUP BY customer_unique_id
)
SELECT agg.*, date_diff('day', last_purchase_date, (SELECT d FROM as_of)) AS recency_days,
       strftime(first_purchase_date, '%Y-%m') AS cohort_month
FROM agg;
