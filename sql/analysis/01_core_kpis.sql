WITH customer_orders AS (
    SELECT customer_key, COUNT(DISTINCT invoice_no) AS orders
    FROM fact_sales
    WHERE customer_key <> 0
    GROUP BY customer_key
)
SELECT
    ROUND(SUM(revenue), 2) AS total_revenue_gbp,
    COUNT(DISTINCT invoice_no) AS total_orders,
    SUM(quantity)::BIGINT AS units_sold,
    COUNT(DISTINCT customer_key) FILTER (WHERE customer_key <> 0) AS unique_identified_customers,
    ROUND(SUM(revenue) / COUNT(DISTINCT invoice_no), 2) AS average_order_value_gbp,
    ROUND(
        SUM(revenue) FILTER (WHERE customer_key <> 0)
        / COUNT(DISTINCT customer_key) FILTER (WHERE customer_key <> 0),
        2
    ) AS revenue_per_identified_customer_gbp,
    ROUND(
        (SELECT COUNT(*) FILTER (WHERE orders >= 2)::DOUBLE / COUNT(*) FROM customer_orders),
        6
    ) AS repeat_customer_rate,
    ROUND(
        SUM(revenue) FILTER (WHERE customer_key = 0) / SUM(revenue),
        6
    ) AS anonymous_revenue_share,
    MIN(invoice_timestamp)::DATE AS sales_date_min,
    MAX(invoice_timestamp)::DATE AS sales_date_max
FROM fact_sales;
