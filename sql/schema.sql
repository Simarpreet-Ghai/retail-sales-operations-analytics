DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS staging_clean;
DROP TABLE IF EXISTS pipeline_audit;

CREATE TABLE pipeline_audit (
    metric VARCHAR PRIMARY KEY,
    metric_value VARCHAR NOT NULL
);

CREATE TABLE staging_clean (
    source_line_id VARCHAR NOT NULL,
    source_sheet VARCHAR NOT NULL,
    source_row_number BIGINT NOT NULL,
    invoice_no VARCHAR,
    stock_code VARCHAR,
    description VARCHAR,
    quantity BIGINT,
    invoice_timestamp TIMESTAMP,
    unit_price DECIMAL(18, 4),
    customer_id VARCHAR,
    country VARCHAR,
    line_revenue DECIMAL(20, 4),
    cancellation_flag BOOLEAN NOT NULL,
    return_flag BOOLEAN NOT NULL,
    invalid_quantity_flag BOOLEAN NOT NULL,
    invalid_price_flag BOOLEAN NOT NULL,
    missing_required_flag BOOLEAN NOT NULL,
    customer_missing_flag BOOLEAN NOT NULL,
    description_missing_flag BOOLEAN NOT NULL,
    record_status VARCHAR NOT NULL
);

CREATE TABLE dim_date (
    date_key BIGINT PRIMARY KEY,
    date DATE NOT NULL,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR NOT NULL,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    weekday_name VARCHAR NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE dim_customer (
    customer_key BIGINT PRIMARY KEY,
    customer_id VARCHAR NOT NULL UNIQUE,
    customer_type VARCHAR NOT NULL
);

CREATE TABLE dim_product (
    product_key BIGINT PRIMARY KEY,
    stock_code VARCHAR NOT NULL UNIQUE,
    product_description VARCHAR NOT NULL,
    first_sale_date DATE NOT NULL,
    last_sale_date DATE NOT NULL
);

CREATE TABLE dim_location (
    location_key BIGINT PRIMARY KEY,
    country VARCHAR NOT NULL UNIQUE
);

CREATE TABLE fact_sales (
    sales_line_id VARCHAR NOT NULL,
    invoice_no VARCHAR NOT NULL,
    invoice_timestamp TIMESTAMP NOT NULL,
    date_key BIGINT NOT NULL,
    customer_key BIGINT NOT NULL,
    product_key BIGINT NOT NULL,
    location_key BIGINT NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(18, 4) NOT NULL CHECK (unit_price > 0),
    revenue DECIMAL(20, 4) NOT NULL CHECK (revenue > 0)
);
