INSTALL postgres;
LOAD postgres;
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint = 'localhost:9000';
SET s3_access_key_id = 'setubid';
SET s3_secret_access_key = 'setubid-secret';
SET s3_use_ssl = false;
SET s3_url_style = 'path';
ATTACH 'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna'
    AS pg (TYPE POSTGRES, READ_ONLY);

CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(strftime(date_value, '%Y%m%d') AS INTEGER) AS date_key,
    date_value AS calendar_date,
    year(date_value) AS calendar_year,
    month(date_value) AS calendar_month,
    strftime(date_value, '%B') AS month_name,
    date_trunc('week', date_value)::DATE AS week_start,
    strftime(date_value, '%A') AS day_name,
    dayofweek(date_value) AS day_of_week
FROM generate_series(DATE '2024-01-01', DATE '2024-12-31', INTERVAL 1 DAY)
    AS generated(date_value);

CREATE OR REPLACE TABLE dim_store AS
SELECT
    row_number() OVER (ORDER BY store_id)::INTEGER AS store_key,
    store_id,
    store_name,
    address_line,
    city,
    state,
    region,
    floor_area_sqft,
    opened_on
FROM pg.stores;

CREATE OR REPLACE TABLE dim_category AS
SELECT
    row_number() OVER (ORDER BY category_id)::INTEGER AS category_key,
    category_id,
    category_name,
    department,
    gst_rate
FROM pg.product_categories;

CREATE OR REPLACE TABLE dim_product AS
SELECT
    p.product_sk::BIGINT AS product_key,
    p.product_code,
    p.product_name,
    c.category_key,
    p.category_id,
    p.brand,
    p.pack_size,
    p.uom,
    p.valid_from,
    p.valid_to,
    p.is_current
FROM pg.products AS p
JOIN dim_category AS c ON c.category_id = p.category_id;

CREATE OR REPLACE TABLE fact_sales_line AS
WITH landed AS (
    SELECT *
    FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true)
), resolved AS (
    SELECT
        landed.*,
        s.store_key,
        p.product_key,
        p.category_key,
        row_number() OVER (
            PARTITION BY landed.bill_no, landed.line_no
            ORDER BY p.valid_from DESC NULLS LAST
        ) AS product_match_rank
    FROM landed
    JOIN dim_store AS s ON s.store_id = landed.store_id
    LEFT JOIN dim_product AS p
        ON p.product_code = landed.product_code
       AND landed.business_date BETWEEN p.valid_from AND p.valid_to
)
SELECT
    hash(bill_no || ':' || line_no::VARCHAR)::UBIGINT AS sales_line_key,
    bill_no,
    line_no,
    store_key,
    product_key,
    category_key,
    CAST(strftime(business_date, '%Y%m%d') AS INTEGER) AS date_key,
    business_date,
    product_code,
    qty,
    unit_price,
    line_type,
    line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID') AS is_revenue,
    CASE
        WHEN line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
        THEN qty * unit_price
        ELSE 0::DECIMAL(18,2)
    END AS revenue_amount,
    ts
FROM resolved
WHERE product_match_rank = 1 OR product_match_rank IS NULL;

CREATE INDEX IF NOT EXISTS ix_fact_sales_date ON fact_sales_line(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_store ON fact_sales_line(store_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_product ON fact_sales_line(product_key);

SELECT 'dim_date' AS table_name, count(*) AS row_count FROM dim_date
UNION ALL SELECT 'dim_store', count(*) FROM dim_store
UNION ALL SELECT 'dim_category', count(*) FROM dim_category
UNION ALL SELECT 'dim_product', count(*) FROM dim_product
UNION ALL SELECT 'fact_sales_line', count(*) FROM fact_sales_line;