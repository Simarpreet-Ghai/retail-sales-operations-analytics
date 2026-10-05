SELECT
    p.stock_code,
    p.product_description,
    ROUND(SUM(f.revenue), 2) AS revenue,
    SUM(f.quantity)::BIGINT AS units,
    COUNT(DISTINCT f.invoice_no) AS orders,
    DENSE_RANK() OVER (ORDER BY SUM(f.revenue) DESC) AS revenue_rank
FROM fact_sales AS f
JOIN dim_product AS p ON f.product_key = p.product_key
GROUP BY p.stock_code, p.product_description
QUALIFY revenue_rank <= 25
ORDER BY revenue_rank, p.stock_code;
