WITH monthly AS (
    SELECT
        DATE_TRUNC('month', d.date)::DATE AS month_start,
        SUM(f.revenue) AS revenue,
        COUNT(DISTINCT f.invoice_no) AS orders,
        SUM(f.quantity)::BIGINT AS units
    FROM fact_sales AS f
    JOIN dim_date AS d ON f.date_key = d.date_key
    GROUP BY DATE_TRUNC('month', d.date)
), lagged AS (
    SELECT
        *,
        LAG(revenue) OVER (ORDER BY month_start) AS previous_month_revenue
    FROM monthly
), bounds AS (
    SELECT MAX(date) AS max_date FROM dim_date
)
SELECT
    month_start,
    ROUND(revenue, 2) AS revenue,
    orders,
    units,
    ROUND(previous_month_revenue, 2) AS previous_month_revenue,
    ROUND(revenue - previous_month_revenue, 2) AS mom_change,
    ROUND(revenue / NULLIF(previous_month_revenue, 0) - 1, 6) AS mom_growth_pct,
    NOT (
        month_start = DATE_TRUNC('month', max_date)::DATE
        AND max_date < LAST_DAY(max_date)
    ) AS complete_month
FROM lagged
CROSS JOIN bounds
ORDER BY month_start;
