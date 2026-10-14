-- GOLD facts. Aggregates are computed per order BEFORE joining so measures never fan out.

-- grain: one row per (order_id, order_item_id)
CREATE OR REPLACE TABLE gold.fact_order_item AS
SELECT i.order_id, i.order_item_id, i.product_id, i.seller_id,
       o.purchased_at::DATE AS purchase_date, i.price, i.freight_value
FROM silver.order_items i
JOIN silver.orders o USING (order_id);

-- grain: one row per (order_id, payment_sequential)
CREATE OR REPLACE TABLE gold.fact_payment AS
SELECT order_id, payment_sequential, payment_type, payment_installments, payment_value
FROM silver.order_payments;

-- grain: one row per (review_id, order_id)
CREATE OR REPLACE TABLE gold.fact_review AS
SELECT review_id, order_id, review_score, review_created_at, review_answered_at
FROM silver.order_reviews;

-- grain: one row per order_id. "Primary" item = order_item_id 1 (its seller/category/state).
-- Review rule: the most recently created review per order.
-- is_late is defined only for delivered orders with both dates: delivered_at > estimated date
-- (compared at day resolution, so delivery on the estimated day counts as on time).
CREATE OR REPLACE TABLE gold.fact_order AS
WITH items AS (
    SELECT i.order_id,
           count(*) AS n_items,
           count(DISTINCT i.seller_id) AS n_sellers,
           sum(i.price) AS items_value,
           sum(i.freight_value) AS freight_value,
           sum(p.weight_g) AS total_weight_g,
           sum(p.volume_cm3) AS total_volume_cm3,
           max(CASE WHEN i.order_item_id = 1 THEN i.seller_id END) AS primary_seller_id,
           max(CASE WHEN i.order_item_id = 1 THEN p.category END) AS primary_category
    FROM silver.order_items i
    LEFT JOIN gold.dim_product p USING (product_id)
    GROUP BY i.order_id
), pays AS (
    SELECT order_id,
           sum(payment_value) AS payment_value,
           max(payment_installments) AS max_installments,
           arg_max(payment_type, payment_value) AS main_payment_type
    FROM silver.order_payments GROUP BY order_id
), rev AS (
    SELECT order_id, arg_max(review_score, review_created_at) AS review_score
    FROM silver.order_reviews GROUP BY order_id
)
SELECT o.order_id, o.customer_id, c.customer_unique_id, c.state AS customer_state,
       o.order_status, o.purchased_at, o.purchased_at::DATE AS purchase_date,
       strftime(o.purchased_at, '%Y-%m') AS purchase_month,
       o.approved_at, o.carrier_at, o.delivered_at, o.estimated_delivery_at,
       coalesce(i.n_items, 0) AS n_items, coalesce(i.n_sellers, 0) AS n_sellers,
       i.items_value, i.freight_value, i.total_weight_g, i.total_volume_cm3,
       i.primary_seller_id, s.state AS primary_seller_state, i.primary_category,
       p.payment_value, p.max_installments, p.main_payment_type,
       r.review_score,
       date_diff('day', o.purchased_at::DATE, o.estimated_delivery_at::DATE) AS estimated_days,
       CASE WHEN o.order_status = 'delivered' AND o.delivered_at IS NOT NULL
            THEN date_diff('day', o.purchased_at::DATE, o.delivered_at::DATE) END AS delivery_days,
       CASE WHEN o.order_status = 'delivered' AND o.delivered_at IS NOT NULL
                 AND o.estimated_delivery_at IS NOT NULL
            THEN date_diff('day', o.estimated_delivery_at::DATE, o.delivered_at::DATE) END AS delay_days,
       CASE WHEN o.order_status = 'delivered' AND o.delivered_at IS NOT NULL
                 AND o.estimated_delivery_at IS NOT NULL
            THEN o.delivered_at::DATE > o.estimated_delivery_at::DATE END AS is_late
FROM silver.orders o
LEFT JOIN silver.customers c USING (customer_id)
LEFT JOIN items i USING (order_id)
LEFT JOIN silver.sellers s ON s.seller_id = i.primary_seller_id
LEFT JOIN pays p USING (order_id)
LEFT JOIN rev r USING (order_id);
