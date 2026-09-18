# Question 4: durable retrieval structure

MinIO remains the source object store. PostgreSQL is the durable lookup home; the Python process only builds/load data and is not required at application lookup time.

## Schema and access path

- `notice(notice_id PRIMARY KEY, portal_id, published_at, signature BYTEA)` stores one stable row per notice and its fixed 738-value signature.
- `lsh_band(notice_id, band_no, band_hash)` stores 82 rows per notice, with a primary key preventing duplicate band rows.
- `lsh_band_lookup_idx` is a covering B-tree on `(band_no, band_hash) INCLUDE (notice_id)`.

The application looks up the probe's 82 band hashes and joins on the indexed pair. A B-tree locates the matching contiguous key ranges; it does not scan unrelated band rows. I rejected a sequential scan because it must inspect the whole 984,000-row band table for every lookup.

## Measured lookup

Probe notice: `N002685`; candidate rows returned: `18`.
B-tree lookup: `0.493 ms`; planner scan nodes: `[('Seq Scan', 'probe_band', 82), ('Index Only Scan', 'lsh_band', 2)]`.
Forced sequential lookup: `100.401 ms`; planner scan nodes: `[('Seq Scan', 'lsh_band', 983918), ('Seq Scan', 'probe_band', 82)]`.

The saved measurement CSV contains the planner scan evidence. The indexed plan should show an Index Only Scan or Bitmap Index Scan on `lsh_band_lookup_idx`; the forced alternative shows a Seq Scan on `lsh_band` and examines the full relation. The tables persist in PostgreSQL across Python process restarts.
