-- DuckDB analytical query over the partitioned object-store layout.
-- Hive partition predicates prune store and month before reading Parquet rows.
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint = 'localhost:9000';
SET s3_access_key_id = 'setubid';
SET s3_secret_access_key = 'setubid-secret';
SET s3_use_ssl = false;
SET s3_url_style = 'path';

SELECT store_id,
       business_date,
       round(sum(qty * unit_price), 2) AS net_revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true)
WHERE store_id = 'S01'
  AND business_date >= DATE '2024-10-01'
  AND business_date < DATE '2024-11-01'
  AND line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY ALL
ORDER BY business_date;

-- The plan exposes the object-store scan and its pushed-down filters.
EXPLAIN ANALYZE
SELECT sum(qty * unit_price) AS net_revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true)
WHERE store_id = 'S01'
  AND year = 2024
  AND month = '10'
  AND line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');