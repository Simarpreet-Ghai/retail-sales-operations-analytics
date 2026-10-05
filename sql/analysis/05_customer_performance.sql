SELECT
    c.customer_id,
    ROUND(SUM(f.revenue), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS orders,
    SUM(f.quantity)::BIGINT AS units,
    DENSE_RANK() OVER (ORDER BY SUM(f.revenue) DESC) AS revenue_rank
FROM fact_sales AS f
JOIN dim_customer AS c ON f.customer_key = c.customer_key
WHERE f.customer_key <> 0
GROUP BY c.customer_id
QUALIFY revenue_rank <= 25
ORDER BY revenue_rank, c.customer_id;
