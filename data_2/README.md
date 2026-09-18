# SetuBid Answers

Dataset: 12,000 notices, 260 portals, 5,776 opportunities, and 900 labelled
pairs. MinIO is the object store; PostgreSQL stores the retrieval index.

## 1. Similarity

Normalize title/body text, remove portal boilerplate, and replace references,
dates, and money with placeholders. Use Jaccard similarity on three-word
shingles.

Measured labelled result: same-pair retrieval `90.0%`; false merges at the
conservative threshold `0` in 621 different pairs.

Output: [question1_report.md](question1_report.md).

## 2. Reduced Form

Use a 738-value MinHash signature, calculated from the target of `+/-0.05`
Jaccard error at `95%` confidence. Size: `5,904` bytes per notice.

Measured on 900 pairs: mean error `0.0183`, 95th percentile `0.0491`, and
`95.1%` within the target.

Outputs: [question2_report.md](question2_report.md),
[question2_results.csv](question2_results.csv).

## 3. Candidate Retrieval

Use MinHash LSH with `82` bands and `9` rows per band. False merges are priced
at `100:1` against missed duplicates.

Measured: `119,164` candidate pairs, average list `19.9`, and labelled same-pair
survival `82.1%`. The survival curve and operating point are in
[question3_survival.png](question3_survival.png).

## 4. Database Access

Store notices and LSH bands in PostgreSQL. Use a covering B-tree index on
`(band_no, band_hash)`.

Measured for one lookup: indexed scan `0.493 ms`, 2 rows examined; forced
sequential scan `100.401 ms`, 983,918 rows examined.

Outputs: [question4_report.md](question4_report.md),
[question4_measurements.csv](question4_measurements.csv).

## 5. Skew and Mitigation

The hotspot was caused by oversized collision buckets from repeated nodal
portal boilerplate. Suppress buckets larger than 100 notices.

Before: `119,164` candidates, `376.0 ms`, same-pair survival `82.1%`.
After: `76,349` candidates, `371.5 ms`, same-pair survival `82.1%`.
Recall loss: `0` labelled same pairs.

Outputs: [question5_report.md](question5_report.md),
[question5_measurements.csv](question5_measurements.csv),
[question5_portal_distribution.csv](question5_portal_distribution.csv).

## Run

```text
docker compose -f data_2/minio/docker-compose.yml up -d
docker compose -f data_2/database/docker-compose.yml up -d
py -3 data_2/question1_similarity.py
py -3 data_2/question2_reduced_form.py
py -3 data_2/question3_lsh.py
py -3 data_2/question4_database.py
py -3 data_2/question5_mitigation.py
```

Upload the notices to MinIO from Git Bash, WSL, or Linux:

```bash
bash data_2/upload_minio.sh
```

The script mirrors the local shards to `s3://setubid/notices/` and removes old
objects first.