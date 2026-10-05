WITH customer_orders AS (
    SELECT customer_key, COUNT(DISTINCT invoice_no) AS orders
    FROM fact_sales
    WHERE customer_key <> 0
    GROUP BY customer_key
)
SELECT
    COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
    COUNT(*) AS identified_customers,
    ROUND(COUNT(*) FILTER (WHERE orders >= 2)::DOUBLE / COUNT(*), 6) AS repeat_customer_rate
FROM customer_orders;
