SELECT
    l.country,
    ROUND(SUM(f.revenue), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS orders,
    SUM(f.quantity)::BIGINT AS units,
    ROUND(SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 6) AS revenue_share
FROM fact_sales AS f
JOIN dim_location AS l ON f.location_key = l.location_key
GROUP BY l.country
ORDER BY revenue DESC;
