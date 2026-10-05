WITH order_values AS (
    SELECT
        YEAR(invoice_timestamp) AS year,
        invoice_no,
        SUM(revenue) AS order_revenue,
        SUM(quantity) AS order_units
    FROM fact_sales
    GROUP BY YEAR(invoice_timestamp), invoice_no
), yearly AS (
    SELECT
        year,
        SUM(order_revenue) AS revenue,
        COUNT(*) AS orders,
        SUM(order_units) AS units,
        AVG(order_revenue) AS average_order_value,
        MEDIAN(order_revenue) AS median_order_value,
        AVG(order_units) AS average_units_per_order
    FROM order_values
    GROUP BY year
), lagged AS (
    SELECT *, LAG(revenue) OVER (ORDER BY year) AS previous_year_revenue
    FROM yearly
)
SELECT
    year,
    ROUND(revenue, 2) AS revenue,
    orders,
    units::BIGINT AS units,
    ROUND(average_order_value, 2) AS average_order_value,
    ROUND(median_order_value, 2) AS median_order_value,
    ROUND(average_units_per_order, 2) AS average_units_per_order,
    ROUND(revenue / NULLIF(previous_year_revenue, 0) - 1, 6) AS yoy_revenue_growth,
    CASE
        WHEN year = 2009 THEN 'PARTIAL: starts December 1'
        WHEN year = 2011 THEN 'PARTIAL: ends December 9'
        ELSE 'COMPLETE'
    END AS coverage
FROM lagged
ORDER BY year;
