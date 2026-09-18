-- One dashboard query can slice by store, product, category, day, week, or month.
SELECT
    s.store_name,
    p.product_name,
    c.category_name,
    d.calendar_date,
    d.week_start,
    d.calendar_year,
    d.calendar_month,
    round(sum(f.revenue_amount), 2) AS revenue
FROM fact_sales_line AS f
JOIN dim_store AS s ON s.store_key = f.store_key
LEFT JOIN dim_product AS p ON p.product_key = f.product_key
LEFT JOIN dim_category AS c ON c.category_key = p.category_key
JOIN dim_date AS d ON d.date_key = f.date_key
WHERE f.is_revenue
  AND s.store_id = 'S01'
  AND d.calendar_date >= DATE '2024-10-01'
  AND d.calendar_date < DATE '2024-11-01'
GROUP BY ALL
ORDER BY d.calendar_date, p.product_name;

-- These counts prove that deduplication and temporal product resolution did
-- not multiply a source line. Reissued codes may have two keys across time.
SELECT
  count(*) AS fact_rows,
  count(DISTINCT bill_no || ':' || line_no::VARCHAR) AS distinct_source_lines,
  count(*) - count(DISTINCT bill_no || ':' || line_no::VARCHAR) AS duplicate_rows,
  count(*) FILTER (WHERE line_type IN ('SALE', 'RETURN', 'VOID')
              AND product_code <> 'DISC'
              AND product_key IS NULL) AS unresolved_item_lines,
  count(*) FILTER (WHERE line_type = 'VOID' AND product_code = 'DISC')
    AS void_discount_control_lines
FROM fact_sales_line;

SELECT count(*) AS reissued_codes_with_two_historical_keys
FROM (
  SELECT product_code
  FROM dim_product
  GROUP BY product_code
  HAVING count(DISTINCT product_key) = 2
) AS reissued;