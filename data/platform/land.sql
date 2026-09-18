INSTALL httpfs;
LOAD httpfs;

CREATE OR REPLACE TEMP TABLE normalized_sales AS
WITH source_rows AS (
    SELECT
        regexp_extract(filename, 'SALES_([^_]+)_([0-9]{8})', 1) AS store_id,
        strptime(regexp_extract(filename, 'SALES_[^_]+_([0-9]{8})', 1), '%Y%m%d')::DATE AS business_date,
        filename,
        bill_no,
        line_no::INTEGER AS line_no,
        product_code,
        qty::DECIMAL(18,3) AS qty,
        unit_price::DECIMAL(18,2) AS unit_price,
        line_type,
        ts
    FROM read_csv('data/sales/SALES_S0[1-5]_*.csv',
        header = true, filename = true, union_by_name = true,
        columns = {bill_no: 'VARCHAR', line_no: 'INTEGER', product_code: 'VARCHAR',
                   qty: 'DECIMAL(18,3)', unit_price: 'DECIMAL(18,2)',
                   line_type: 'VARCHAR', ts: 'VARCHAR'})
    UNION ALL
    SELECT
        regexp_extract(filename, 'SALES_([^_]+)_([0-9]{8})', 1),
        strptime(regexp_extract(filename, 'SALES_[^_]+_([0-9]{8})', 1), '%Y%m%d')::DATE,
        filename, bill_no, line_no::INTEGER, item_code, quantity::DECIMAL(18,3),
        rate::DECIMAL(18,2), type, txn_time
    FROM read_csv('data/sales/SALES_S0[6-9]_*.csv',
        header = true, filename = true, union_by_name = true,
        delim = ';', columns = {bill_no: 'VARCHAR', line_no: 'INTEGER', item_code: 'VARCHAR',
                                quantity: 'DECIMAL(18,3)', rate: 'DECIMAL(18,2)',
                                type: 'VARCHAR', txn_time: 'VARCHAR'})
    UNION ALL
    SELECT
        regexp_extract(filename, 'SALES_([^_]+)_([0-9]{8})', 1),
        strptime(regexp_extract(filename, 'SALES_[^_]+_([0-9]{8})', 1), '%Y%m%d')::DATE,
        filename, bill_no, line_no::INTEGER, product_code, qty::DECIMAL(18,3),
        unit_price::DECIMAL(18,2), line_type, ts
    FROM read_csv('data/sales/SALES_S1[0-2]_*.csv',
        header = true, filename = true, union_by_name = true,
        columns = {ts: 'VARCHAR', bill_no: 'VARCHAR', line_no: 'INTEGER',
                   line_type: 'VARCHAR', product_code: 'VARCHAR',
                   unit_price: 'DECIMAL(18,2)', qty: 'DECIMAL(18,3)'})
), deduplicated AS (
    SELECT *, row_number() OVER (PARTITION BY bill_no, line_no ORDER BY filename) AS rn
    FROM source_rows
)
SELECT
    store_id, business_date, bill_no, line_no, product_code, qty, unit_price,
    line_type, ts,
    year(business_date) AS year,
    lpad(month(business_date)::VARCHAR, 2, '0') AS month
FROM deduplicated
WHERE rn = 1;

COPY normalized_sales
TO 'data/object_store/sales'
(FORMAT PARQUET, PARTITION_BY (store_id, year, month), COMPRESSION ZSTD, OVERWRITE_OR_IGNORE);

COPY (SELECT * FROM normalized_sales)
TO 'data/object_store/manifest/normalized_sales.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE);

SELECT count(*) AS landed_rows,
       count(DISTINCT bill_no || ':' || line_no::VARCHAR) AS distinct_lines
FROM normalized_sales;