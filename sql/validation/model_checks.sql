WITH audit AS (
    SELECT
        MAX(CASE WHEN metric = 'starting_row_count' THEN metric_value END)::BIGINT AS starting_rows,
        MAX(CASE WHEN metric = 'duplicate_rows_removed' THEN metric_value END)::BIGINT AS duplicate_rows,
        MAX(CASE WHEN metric = 'cleaned_staging_row_count' THEN metric_value END)::BIGINT AS staging_rows,
        MAX(CASE WHEN metric = 'analytical_sales_row_count' THEN metric_value END)::BIGINT AS sales_rows
    FROM pipeline_audit
), checks AS (
    SELECT
        'raw_to_staging_row_reconciliation' AS check_name,
        ((SELECT COUNT(*) FROM staging_clean) + duplicate_rows)::VARCHAR AS actual_value,
        starting_rows::VARCHAR AS expected_value,
        ((SELECT COUNT(*) FROM staging_clean) + duplicate_rows) = starting_rows AS passed
    FROM audit

    UNION ALL
    SELECT
        'staging_row_count_matches_audit',
        (SELECT COUNT(*) FROM staging_clean)::VARCHAR,
        staging_rows::VARCHAR,
        (SELECT COUNT(*) FROM staging_clean) = staging_rows
    FROM audit

    UNION ALL
    SELECT
        'fact_row_count_matches_audit',
        (SELECT COUNT(*) FROM fact_sales)::VARCHAR,
        sales_rows::VARCHAR,
        (SELECT COUNT(*) FROM fact_sales) = sales_rows
    FROM audit

    UNION ALL
    SELECT
        'fact_rows_match_sale_status_rows',
        (SELECT COUNT(*) FROM fact_sales)::VARCHAR,
        (SELECT COUNT(*) FROM staging_clean WHERE record_status = 'SALE')::VARCHAR,
        (SELECT COUNT(*) FROM fact_sales)
            = (SELECT COUNT(*) FROM staging_clean WHERE record_status = 'SALE')

    UNION ALL
    SELECT
        'staging_source_line_id_is_unique',
        (COUNT(*) - COUNT(DISTINCT source_line_id))::VARCHAR,
        '0',
        COUNT(*) = COUNT(DISTINCT source_line_id)
    FROM staging_clean

    UNION ALL
    SELECT
        'fact_sales_line_id_is_unique',
        (COUNT(*) - COUNT(DISTINCT sales_line_id))::VARCHAR,
        '0',
        COUNT(*) = COUNT(DISTINCT sales_line_id)
    FROM fact_sales

    UNION ALL
    SELECT
        'staging_has_no_exact_business_duplicates',
        COUNT(*)::VARCHAR,
        '0',
        COUNT(*) = 0
    FROM (
        SELECT
            invoice_no, stock_code, description, quantity, invoice_timestamp,
            unit_price, customer_id, country, COUNT(*) AS row_count
        FROM staging_clean
        GROUP BY ALL
        HAVING COUNT(*) > 1
    ) AS duplicates

    UNION ALL
    SELECT
        'staging_dates_are_valid',
        COUNT(*) FILTER (WHERE invoice_timestamp IS NULL)::VARCHAR,
        '0',
        COUNT(*) FILTER (WHERE invoice_timestamp IS NULL) = 0
    FROM staging_clean

    UNION ALL
    SELECT
        'staging_statuses_cover_every_row',
        COUNT(*) FILTER (
            WHERE record_status NOT IN (
                'SALE', 'CANCELLATION', 'RETURN', 'MISSING_REQUIRED',
                'INVALID_QUANTITY', 'INVALID_PRICE'
            ) OR record_status IS NULL
        )::VARCHAR,
        '0',
        COUNT(*) FILTER (
            WHERE record_status NOT IN (
                'SALE', 'CANCELLATION', 'RETURN', 'MISSING_REQUIRED',
                'INVALID_QUANTITY', 'INVALID_PRICE'
            ) OR record_status IS NULL
        ) = 0
    FROM staging_clean

    UNION ALL
    SELECT
        'valid_sale_definition_is_enforced',
        COUNT(*)::VARCHAR,
        '0',
        COUNT(*) = 0
    FROM staging_clean
    WHERE record_status = 'SALE'
      AND (
          cancellation_flag OR return_flag OR invalid_quantity_flag
          OR invalid_price_flag OR missing_required_flag
      )

    UNION ALL
    SELECT
        'cancellations_and_returns_are_excluded_from_fact',
        COUNT(*)::VARCHAR,
        '0',
        COUNT(*) = 0
    FROM fact_sales AS f
    JOIN staging_clean AS s ON f.sales_line_id = s.source_line_id
    WHERE s.cancellation_flag OR s.return_flag

    UNION ALL
    SELECT
        'fact_required_fields_are_not_null',
        COUNT(*) FILTER (
            WHERE sales_line_id IS NULL OR invoice_no IS NULL OR invoice_timestamp IS NULL
               OR date_key IS NULL OR customer_key IS NULL OR product_key IS NULL
               OR location_key IS NULL OR quantity IS NULL OR unit_price IS NULL
               OR revenue IS NULL
        )::VARCHAR,
        '0',
        COUNT(*) FILTER (
            WHERE sales_line_id IS NULL OR invoice_no IS NULL OR invoice_timestamp IS NULL
               OR date_key IS NULL OR customer_key IS NULL OR product_key IS NULL
               OR location_key IS NULL OR quantity IS NULL OR unit_price IS NULL
               OR revenue IS NULL
        ) = 0
    FROM fact_sales

    UNION ALL
    SELECT
        'fact_measures_are_positive',
        COUNT(*) FILTER (WHERE quantity <= 0 OR unit_price <= 0 OR revenue <= 0)::VARCHAR,
        '0',
        COUNT(*) FILTER (WHERE quantity <= 0 OR unit_price <= 0 OR revenue <= 0) = 0
    FROM fact_sales

    UNION ALL
    SELECT
        'fact_revenue_formula_is_valid',
        COUNT(*) FILTER (WHERE ABS(revenue - (quantity * unit_price)) > 0.0001)::VARCHAR,
        '0',
        COUNT(*) FILTER (WHERE ABS(revenue - (quantity * unit_price)) > 0.0001) = 0
    FROM fact_sales

    UNION ALL
    SELECT
        'fact_revenue_reconciles_to_staging_sales',
        ROUND((SELECT SUM(revenue) FROM fact_sales), 2)::VARCHAR,
        ROUND((SELECT SUM(line_revenue) FROM staging_clean WHERE record_status = 'SALE'), 2)::VARCHAR,
        ABS(
            (SELECT SUM(revenue) FROM fact_sales)
            - (SELECT SUM(line_revenue) FROM staging_clean WHERE record_status = 'SALE')
        ) <= 0.01

    UNION ALL
    SELECT
        'dimension_keys_and_natural_keys_are_unique',
        (
            (SELECT COUNT(*) - COUNT(DISTINCT date_key) FROM dim_date)
            + (SELECT COUNT(*) - COUNT(DISTINCT customer_key) FROM dim_customer)
            + (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM dim_customer)
            + (SELECT COUNT(*) - COUNT(DISTINCT product_key) FROM dim_product)
            + (SELECT COUNT(*) - COUNT(DISTINCT stock_code) FROM dim_product)
            + (SELECT COUNT(*) - COUNT(DISTINCT location_key) FROM dim_location)
            + (SELECT COUNT(*) - COUNT(DISTINCT country) FROM dim_location)
        )::VARCHAR,
        '0',
        (
            (SELECT COUNT(*) - COUNT(DISTINCT date_key) FROM dim_date)
            + (SELECT COUNT(*) - COUNT(DISTINCT customer_key) FROM dim_customer)
            + (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM dim_customer)
            + (SELECT COUNT(*) - COUNT(DISTINCT product_key) FROM dim_product)
            + (SELECT COUNT(*) - COUNT(DISTINCT stock_code) FROM dim_product)
            + (SELECT COUNT(*) - COUNT(DISTINCT location_key) FROM dim_location)
            + (SELECT COUNT(*) - COUNT(DISTINCT country) FROM dim_location)
        ) = 0

    UNION ALL
    SELECT
        'fact_foreign_keys_resolve',
        COUNT(*) FILTER (
            WHERE d.date_key IS NULL OR c.customer_key IS NULL
               OR p.product_key IS NULL OR l.location_key IS NULL
        )::VARCHAR,
        '0',
        COUNT(*) FILTER (
            WHERE d.date_key IS NULL OR c.customer_key IS NULL
               OR p.product_key IS NULL OR l.location_key IS NULL
        ) = 0
    FROM fact_sales AS f
    LEFT JOIN dim_date AS d ON f.date_key = d.date_key
    LEFT JOIN dim_customer AS c ON f.customer_key = c.customer_key
    LEFT JOIN dim_product AS p ON f.product_key = p.product_key
    LEFT JOIN dim_location AS l ON f.location_key = l.location_key

    UNION ALL
    SELECT
        'date_dimension_is_continuous',
        COUNT(*)::VARCHAR,
        (DATE_DIFF('day', MIN(date), MAX(date)) + 1)::VARCHAR,
        COUNT(*) = DATE_DIFF('day', MIN(date), MAX(date)) + 1
    FROM dim_date

    UNION ALL
    SELECT
        'fact_date_range_matches_date_dimension_bounds',
        CONCAT(f.min_date, ' to ', f.max_date),
        CONCAT(d.min_date, ' to ', d.max_date),
        f.min_date = d.min_date AND f.max_date = d.max_date
    FROM (
        SELECT MIN(invoice_timestamp)::DATE AS min_date, MAX(invoice_timestamp)::DATE AS max_date
        FROM fact_sales
    ) AS f
    CROSS JOIN (
        SELECT MIN(date) AS min_date, MAX(date) AS max_date
        FROM dim_date
    ) AS d

    UNION ALL
    SELECT
        'anonymous_sales_map_to_unknown_customer',
        (SELECT COUNT(*) FROM fact_sales WHERE customer_key = 0)::VARCHAR,
        (
            SELECT COUNT(*) FROM staging_clean
            WHERE record_status = 'SALE' AND customer_id IS NULL
        )::VARCHAR,
        (SELECT COUNT(*) FROM fact_sales WHERE customer_key = 0)
            = (
                SELECT COUNT(*) FROM staging_clean
                WHERE record_status = 'SALE' AND customer_id IS NULL
            )
)
SELECT
    check_name,
    actual_value,
    expected_value,
    CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks
ORDER BY check_name;
