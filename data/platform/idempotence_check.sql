INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint = 'localhost:9000';
SET s3_access_key_id = 'setubid';
SET s3_secret_access_key = 'setubid-secret';
SET s3_use_ssl = false;
SET s3_url_style = 'path';

SELECT
    count(*) AS row_count,
    sum(hash(concat_ws('|', bill_no, line_no::VARCHAR, product_code,
                       qty::VARCHAR, unit_price::VARCHAR, line_type))) AS checksum
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true);