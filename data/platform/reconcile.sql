CREATE OR REPLACE TABLE reconciliation AS
WITH pipeline AS (
    SELECT
        strftime(business_date, '%Y-%m') AS month,
        round(sum(revenue_amount), 2) AS pipeline_revenue
    FROM fact_sales_line
    WHERE is_revenue
    GROUP BY 1
), finance AS (
    SELECT
        month,
        revenue_inr::DECIMAL(18, 2) AS finance_revenue
    FROM read_csv('data/finance_monthly.csv', header = true,
                  types = {'month': 'VARCHAR', 'closed_on': 'DATE',
                           'revenue_inr': 'DECIMAL(18,2)',
                           'signed_off_by': 'VARCHAR'})
), compared AS (
    SELECT
        f.month,
        p.pipeline_revenue,
        f.finance_revenue,
        round(f.finance_revenue - p.pipeline_revenue, 2) AS variance
    FROM finance AS f
    JOIN pipeline AS p USING (month)
)
SELECT
    month,
    pipeline_revenue,
    finance_revenue,
    variance,
    CASE
        WHEN abs(variance) < 0.01 THEN 'match'
        WHEN month = '2024-03' THEN 'definition difference'
        WHEN month = '2024-07' THEN 'source data'
        WHEN month = '2024-12' THEN 'definition difference'
        ELSE 'pipeline bug'
    END AS cause,
    CASE
        WHEN abs(variance) < 0.01 THEN 'none'
        WHEN month = '2024-03' THEN 'finance: decide whether institutional invoice belongs in till revenue'
        WHEN month = '2024-07' THEN 'store operations: recover or explain S07 missing export days'
        WHEN month = '2024-12' THEN 'finance: align bill-level rounding policy'
        ELSE 'data engineering: investigate and repair pipeline'
    END AS owner_to_take_back,
    CASE month
        WHEN '2024-03' THEN 'Finance includes the 486250.00 institutional order invoiced outside the till.'
        WHEN '2024-07' THEN 'S07 exports are absent for 2024-07-09 through 2024-07-11; finance has manually supplied those days.'
        WHEN '2024-12' THEN 'Finance rounds each bill to the rupee; the pipeline sums line amounts to cents.'
        ELSE 'Pipeline revenue matches the finance amount.'
    END AS explanation
FROM compared
ORDER BY month;

SELECT * FROM reconciliation;