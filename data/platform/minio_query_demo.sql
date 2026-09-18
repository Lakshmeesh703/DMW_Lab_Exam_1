INSTALL httpfs;
LOAD httpfs;

SET s3_endpoint = 'localhost:9000';
SET s3_access_key_id = 'setubid';
SET s3_secret_access_key = 'setubid-secret';
SET s3_use_ssl = false;
SET s3_url_style = 'path';

-- Query 1: count the landed rows directly from MinIO.
SELECT count(*) AS rows_from_minio
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true);

-- Query 2: S01 October revenue directly from the MinIO bucket.
SELECT round(sum(qty * unit_price), 2) AS s01_october_net_revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true)
WHERE store_id = 'S01'
  AND year = 2024
  AND month = '10'
  AND line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');

-- Query 3: prove MinIO partition pruning and the selected object.
EXPLAIN ANALYZE
SELECT round(sum(qty * unit_price), 2) AS s01_october_net_revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true)
WHERE store_id = 'S01'
  AND year = 2024
  AND month = '10'
  AND line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');