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

-- One statement: sales stay in Parquet; all three dimensions are read from
-- PostgreSQL. The product validity range handles reissued product codes.
SELECT
    s.store_id,
    s.store_name,
    c.category_name,
    p.product_name,
    round(sum(f.qty * f.unit_price), 2) AS revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true) AS f
JOIN pg.stores AS s
  ON s.store_id = f.store_id
LEFT JOIN pg.products AS p
  ON p.product_code = f.product_code
 AND f.business_date BETWEEN p.valid_from AND p.valid_to
LEFT JOIN pg.product_categories AS c
  ON c.category_id = p.category_id
WHERE f.store_id = 'S01'
  AND f.year = 2024
  AND f.month = '10'
  AND f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY s.store_id, s.store_name, c.category_name, p.product_name
ORDER BY c.category_name, p.product_name;

-- Engine evidence for the same federated query.
EXPLAIN ANALYZE
SELECT
    s.store_id,
    s.store_name,
    c.category_name,
    p.product_name,
    round(sum(f.qty * f.unit_price), 2) AS revenue
FROM read_parquet('s3://annapurna/sales/**/*.parquet', hive_partitioning = true) AS f
JOIN pg.stores AS s ON s.store_id = f.store_id
LEFT JOIN pg.products AS p
  ON p.product_code = f.product_code
 AND f.business_date BETWEEN p.valid_from AND p.valid_to
LEFT JOIN pg.product_categories AS c ON c.category_id = p.category_id
WHERE f.store_id = 'S01'
  AND f.year = 2024
  AND f.month = '10'
  AND f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY s.store_id, s.store_name, c.category_name, p.product_name;