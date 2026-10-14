-- GOLD dimensions. Only gold tables are exposed to BI, analytics and models.

-- grain: one row per calendar day between first and last purchase
CREATE OR REPLACE TABLE gold.dim_date AS
SELECT d::DATE AS date_key, year(d) AS year, month(d) AS month,
       strftime(d, '%Y-%m') AS year_month, dayofweek(d) AS day_of_week
FROM generate_series(
    (SELECT min(purchased_at)::DATE FROM silver.orders),
    (SELECT max(purchased_at)::DATE FROM silver.orders),
    INTERVAL 1 DAY) AS t(d);

-- grain: one row per customer_id (per-order id); customer_unique_id identifies the person
CREATE OR REPLACE TABLE gold.dim_customer AS
SELECT customer_id, customer_unique_id, zip_prefix, city, state FROM silver.customers;

-- grain: one row per seller_id
CREATE OR REPLACE TABLE gold.dim_seller AS
SELECT seller_id, zip_prefix, city, state FROM silver.sellers;

-- grain: one row per product_id. Category falls back to Portuguese, then 'unknown'.
CREATE OR REPLACE TABLE gold.dim_product AS
SELECT p.product_id,
       coalesce(t.category_en, p.category_pt, 'unknown') AS category,
       p.weight_g, p.length_cm * p.height_cm * p.width_cm AS volume_cm3
FROM silver.products p
LEFT JOIN silver.category_translation t USING (category_pt);
