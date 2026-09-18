# Annapurna platform

This setup uses PostgreSQL for the relational master data and DuckDB for
analytical queries over local object storage. The source files remain under
`data/sales`; `land.sql` normalizes the three file dialects, deduplicates
resends by `(bill_no, line_no)`, and writes compressed Parquet partitions.

The retained local copy has this partition layout:

```text
data/object_store/sales/store_id=S01/year=2024/month=10/data_0.parquet
```

Store and month are the first pruning keys because the requested workload
frequently filters by both. Day remains a column, avoiding hundreds of tiny
objects while still supporting daily grouping. The local `data/object_store/`
folder is retained, but active analytical queries read the MinIO bucket only.

The Parquet landing is also available in MinIO at
`s3://annapurna/sales/`. DuckDB reads this bucket through its S3/httpfs
connector using the local MinIO service at `http://localhost:9000`.

For a standalone `data/` submission, MinIO can be started with
`minio-compose.yml` using the same credentials as the query file:

```text
docker compose -f data/platform/minio-compose.yml up -d
```

Run from the repository root:

```text
python data/platform/platform_setup.py
```

The Python entry-point starts MinIO when it is not already running, starts
PostgreSQL, lands the data, uploads the fresh Parquet objects to MinIO, and
then runs the DuckDB query. The individual commands are also shown below:

```text
docker compose -f data/platform/docker-compose.yml up -d
New-Item -ItemType Directory -Force data/object_store/manifest | Out-Null
duckdb data/platform/annapurna.duckdb -init data/platform/land.sql
duckdb data/platform/annapurna.duckdb -c ".read data/platform/query_demo.sql"
```

Upload the landed objects to MinIO and run the S3-backed checks:

```text
data/platform/upload_minio.sh
```

On Git Bash, WSL, or Linux, the Bash uploader mirrors the local landing into
MinIO and removes stale objects first. The PowerShell equivalent is
`upload_minio.ps1`.

```text
docker volume create setubid-mc-config
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc alias set local http://127.0.0.1:9000 setubid setubid-secret
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc mb --ignore-existing local/annapurna
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc rm --recursive --force local/annapurna/sales/
docker run --rm --network host -v setubid-mc-config:/root/.mc -v "${PWD}/data/object_store/sales:/src:ro" quay.io/minio/mc cp --recursive /src/ local/annapurna/sales/
duckdb data/platform/annapurna.duckdb -c ".read data/platform/minio_query_demo.sql"
```

The MinIO-backed checks were run successfully:

```text
rows_from_minio:             1,120,924
s01_october_net_revenue:     6,435,443.95
HTTPFS GET requests:         1
Parquet files read:          1
Selected object:             s3://annapurna/sales/store_id=S01/year=2024/month=10/data_0.parquet
```

The selected plan evidence is preserved in `query_plan_evidence.txt`, including
the HTTPFS GET count, file filters, selected object, and rows scanned.

For repeatable ingestion, run the wrapper three times:

```text
1..3 | ForEach-Object { powershell -ExecutionPolicy Bypass -File data/platform/run_land.ps1 }
Get-Content data/platform/idempotence_runs.csv
```

The wrapper replaces the generated landing only after the new run succeeds,
uploads that fresh landing to MinIO, and then checks the MinIO objects. It
deduplicates resend rows by `(bill_no, line_no)` inside `land.sql`; the proof
file records the stable count and checksum after each invocation.

Build the dashboard star schema after PostgreSQL is running and the landing is
complete:

```text
duckdb data/platform/annapurna.duckdb -c ".read data/platform/build_star_schema.sql"
duckdb data/platform/annapurna.duckdb -c ".read data/platform/dashboard_queries.sql"
```

`fact_sales_line` keeps one row per deduplicated source line and does not repeat
store addresses or product/category attributes. `dim_product` retains each
historical product version; the build joins on `product_code` plus the sale's
business-date validity range, not on code alone. `is_revenue` excludes TAX and
TENDER from dashboard sums while preserving those lines for audit. The source
also contains 117 `VOID` rows with product code `DISC`; they are retained as
control lines with a null product key rather than being forced into a product.

Historical-price reporting uses the same query body for both periods:

```text
duckdb data/platform/annapurna.duckdb -c ".read data/platform/historical_price_report.sql"
```

The query joins `fact_sales_line.product_key` to PostgreSQL
`price_revisions.product_sk` and applies the revision whose effective date
contains the sale's business date. The December 2024 call is the dataset's
last month; changing the two date arguments is the only difference from the
March call. Lines without a product revision, such as discount/control lines,
fall back to their printed amount.

Recorded results are in `historical_price_results.csv`: March's
revision-priced revenue is `41,971,885.88`, while December's is
`50,736,426.71`. The printed till totals would be `41,971,649.09` and
`50,745,259.48`, respectively, proving the report uses the period's effective
prices rather than today's price list.

Monthly reconciliation is in `reconcile.sql` and the recorded output is in
`reconciliation_results.csv`:

```text
duckdb data/platform/annapurna.duckdb -c ".read data/platform/reconcile.sql"
```

The pipeline measure is the fact-table sum of `revenue_amount`, which includes
SALE, RETURN, DISCOUNT, and VOID and excludes TAX and TENDER. Three differences
are intentional: March is a finance-definition difference because finance adds
the ₹486,250 institutional invoice; July is a source-data gap because S07 has
three missing export days; December is a finance-definition difference because
finance rounds each bill. There are no pipeline bugs in the comparison. Take
March and December to Finance to agree definitions, and July to store
operations/data supply to resolve the missing source files.

The direct cross-system query is in `federated_query.sql`:

```text
duckdb data/platform/annapurna.duckdb -c ".read data/platform/federated_query.sql"
```

It reads the filtered S01 October Parquet partition from object storage and
joins directly to PostgreSQL's `stores`, `products`, and `product_categories`.
The product and category joins are left joins so the 117 source `VOID/DISC`
control lines are not silently dropped. The query does not copy either side. Its `EXPLAIN ANALYZE` output is the
evidence: `READ_PARQUET` shows the object-store scan and file filter, while
`POSTGRES_SCAN` nodes show the three PostgreSQL dimension scans; DuckDB's join,
filter, and aggregation nodes run in the analytical engine.

Recorded proof in `idempotence_runs.csv`:

```text
run,row_count,checksum
1,1120924,10347768371481403255548875
2,1120924,10347768371481403255548875
3,1120924,10347768371481403255548875
```

For the S01 October example, the raw folder contains 4,457 files and
68,706,877 bytes; the source slice contains 31 files and 846,899 bytes. The
landed S01/2024/10 partition is one Parquet file of 135,385 bytes. The full
landed sales area is 148 Parquet files and 11,565,536 bytes. In the executed
query, DuckDB reported `Scanning Files: 1/1` and `Total Files Read: 1`, with
file filters for `store_id=S01` and `month=10`. A single-folder raw query
would have to discover all 4,457 files (and potentially inspect all
68,706,877 bytes); the partitioned query opens only the one selected object.

## Final outputs

### a) Platform and landing

```text
PostgreSQL: running
DuckDB: running
Rows landed: 1,120,924
S01 October: 1 Parquet file, 135,385 bytes
Raw folder: 4,457 files, 68,706,877 bytes
```

The store/year/month partitions let the S01 October query read one object
instead of the whole raw folder.

### b) Repeatable loading

```text
Run 1: 1,120,924 rows, checksum 10347768371481403255548875
Run 2: 1,120,924 rows, checksum 10347768371481403255548875
Run 3: 1,120,924 rows, checksum 10347768371481403255548875
```

Identical counts and checksums prove that rerunning the loader does not
duplicate resend rows.

### c) Dashboard tables

```text
dim_date: 366 rows
dim_store: 12 rows
dim_category: 14 rows
dim_product: 1,224 rows
fact_sales_line: 1,120,924 rows
Duplicate fact rows: 0
```

The fact table stores keys instead of repeated store and product descriptions.
Product versions use product code plus sale date; TAX and TENDER are retained
but excluded from revenue.

### d) Historical prices

```text
March 2024 revision-price revenue:    41,971,885.88
December 2024 revision-price revenue: 50,736,426.71
```

The same query uses the price revision valid on each sale date.

### e) Cross-system query

```text
S01 October result groups: 720
Sales lines joined: 9,564
Revenue: 6,435,443.95
Parquet files read: 1
```

DuckDB reads sales from Parquet and dimensions from PostgreSQL. The plan shows
`READ_PARQUET`, three `POSTGRES_SCAN` nodes, and DuckDB joins and aggregation.

### f) Finance reconciliation

```text
Months compared: 12
Mismatches: 3
Pipeline bugs: 0
```

March differs by ₹486,250 because Finance includes an outside institutional
invoice. July differs because S07's three export days are missing. December
differs by ₹50.48 because Finance rounds each bill. March and December go to
Finance for definition agreement; July goes to store operations for the
missing source data.