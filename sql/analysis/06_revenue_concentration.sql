WITH customer_revenue AS (
    SELECT customer_key, SUM(revenue) AS revenue
    FROM fact_sales
    WHERE customer_key <> 0
    GROUP BY customer_key
), ranked_customers AS (
    SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS revenue_rank
    FROM customer_revenue
), product_revenue AS (
    SELECT product_key, SUM(revenue) AS revenue
    FROM fact_sales
    GROUP BY product_key
), ranked_products AS (
    SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS revenue_rank
    FROM product_revenue
), totals AS (
    SELECT SUM(revenue) AS total_revenue FROM fact_sales
)
SELECT
    ROUND(
        (SELECT SUM(revenue) FROM ranked_customers WHERE revenue_rank <= 10),
        2
    ) AS top_10_customer_revenue,
    ROUND(
        (SELECT SUM(revenue) FROM ranked_customers WHERE revenue_rank <= 10)
        / total_revenue,
        6
    ) AS top_10_customer_share,
    ROUND(
        (SELECT SUM(revenue) FROM ranked_products WHERE revenue_rank <= 10),
        2
    ) AS top_10_product_revenue,
    ROUND(
        (SELECT SUM(revenue) FROM ranked_products WHERE revenue_rank <= 10)
        / total_revenue,
        6
    ) AS top_10_product_share
FROM totals;
