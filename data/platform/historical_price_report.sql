INSTALL postgres;
LOAD postgres;
ATTACH 'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna'
    AS pg (TYPE POSTGRES, READ_ONLY);

CREATE OR REPLACE MACRO historical_price_report(report_start, report_end) AS TABLE
WITH priced_lines AS (
    SELECT
        f.*,
        pr.selling_price AS historical_unit_price
    FROM fact_sales_line AS f
    LEFT JOIN pg.price_revisions AS pr
        ON pr.product_sk = f.product_key
       AND f.business_date BETWEEN pr.effective_from AND pr.effective_to
    WHERE f.is_revenue
      AND f.business_date >= report_start
      AND f.business_date < report_end
)
SELECT
    report_start AS period_start,
    report_end - INTERVAL 1 DAY AS period_end,
    count(*) AS revenue_lines,
    count(*) FILTER (WHERE historical_unit_price IS NOT NULL) AS lines_using_revision_price,
    count(*) FILTER (WHERE historical_unit_price IS NULL) AS lines_using_printed_price,
    round(sum(revenue_amount), 2) AS printed_till_revenue,
    round(sum(qty * COALESCE(historical_unit_price, unit_price)), 2)
        AS historical_price_revenue,
    round(sum(qty * COALESCE(historical_unit_price, unit_price)) - sum(revenue_amount), 2)
        AS historical_minus_printed
FROM priced_lines;

-- Same query body, differing only in the reporting-period arguments.
SELECT * FROM historical_price_report(DATE '2024-03-01', DATE '2024-04-01');
SELECT * FROM historical_price_report(DATE '2024-12-01', DATE '2025-01-01');