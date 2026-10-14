-- SILVER: typed, de-duplicated copies of bronze. Values are never altered beyond casting;
-- TRY_CAST turns unparseable values into NULL and the quality checks count those failures.
-- Grain of each table is stated in its comment.

-- grain: one row per order_id
CREATE OR REPLACE TABLE silver.orders AS
SELECT order_id, customer_id, order_status,
       TRY_CAST(order_purchase_timestamp      AS TIMESTAMP) AS purchased_at,
       TRY_CAST(order_approved_at             AS TIMESTAMP) AS approved_at,
       TRY_CAST(order_delivered_carrier_date  AS TIMESTAMP) AS carrier_at,
       TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_at,
       TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_delivery_at
FROM bronze.orders;

-- grain: one row per (order_id, order_item_id)
CREATE OR REPLACE TABLE silver.order_items AS
SELECT order_id, TRY_CAST(order_item_id AS INTEGER) AS order_item_id, product_id, seller_id,
       TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_at,
       TRY_CAST(price AS DOUBLE) AS price,
       TRY_CAST(freight_value AS DOUBLE) AS freight_value
FROM bronze.order_items;

-- grain: one row per (order_id, payment_sequential)
CREATE OR REPLACE TABLE silver.order_payments AS
SELECT order_id, TRY_CAST(payment_sequential AS INTEGER) AS payment_sequential, payment_type,
       TRY_CAST(payment_installments AS INTEGER) AS payment_installments,
       TRY_CAST(payment_value AS DOUBLE) AS payment_value
FROM bronze.order_payments;

-- grain: one row per (review_id, order_id). Exact duplicates on that key keep the latest answer.
CREATE OR REPLACE TABLE silver.order_reviews AS
SELECT review_id, order_id, review_score, review_created_at, review_answered_at
FROM (
    SELECT review_id, order_id,
           TRY_CAST(review_score AS INTEGER) AS review_score,
           TRY_CAST(review_creation_date AS TIMESTAMP) AS review_created_at,
           TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answered_at,
           row_number() OVER (PARTITION BY review_id, order_id
                              ORDER BY TRY_CAST(review_answer_timestamp AS TIMESTAMP) DESC NULLS LAST) AS rn
    FROM bronze.order_reviews
) WHERE rn = 1;

-- grain: one row per customer_id (a per-order id; customer_unique_id is the person)
CREATE OR REPLACE TABLE silver.customers AS
SELECT customer_id, customer_unique_id, customer_zip_code_prefix AS zip_prefix,
       customer_city AS city, upper(customer_state) AS state
FROM bronze.customers;

-- grain: one row per seller_id
CREATE OR REPLACE TABLE silver.sellers AS
SELECT seller_id, seller_zip_code_prefix AS zip_prefix, seller_city AS city,
       upper(seller_state) AS state
FROM bronze.sellers;

-- grain: one row per product_id
CREATE OR REPLACE TABLE silver.products AS
SELECT product_id, product_category_name AS category_pt,
       TRY_CAST(product_weight_g AS DOUBLE) AS weight_g,
       TRY_CAST(product_length_cm AS DOUBLE) AS length_cm,
       TRY_CAST(product_height_cm AS DOUBLE) AS height_cm,
       TRY_CAST(product_width_cm AS DOUBLE) AS width_cm
FROM bronze.products;

-- grain: one row per Portuguese category name
CREATE OR REPLACE TABLE silver.category_translation AS
SELECT product_category_name AS category_pt, product_category_name_english AS category_en
FROM bronze.category_translation;
