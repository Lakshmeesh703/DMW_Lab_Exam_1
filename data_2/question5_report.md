# Question 5: skew, cost, and mitigation

The full retrieval was run from the PostgreSQL LSH structure populated from MinIO. Candidate work is uneven because notices that share a band hash are compared as a bucket; repeated portal wording and short notices make some bands much less selective than others.

## Before mitigation

The LSH table has 715,134 buckets. The largest bucket has 272 notices, p99 bucket size is 5, and only two buckets exceed 100 notices. The full self-join produced 119,164 unique candidate pairs in 376.0 ms. Per-notice candidate distribution: average 19.9, p95 73, maximum 390.
The highest-work portal was `P094` with 28,505 candidate assignments across 1,426 notices (12.0% of all assignments); see `question5_portal_distribution.csv` for every portal. The hottest notice was `N007962` from `P003` with 390 candidates.

Mechanically, a common shingle signature makes a whole band collide. The LSH OR rule then emits every pair in that bucket, so bucket cost grows quadratically with bucket size. This is why a small number of buckets/notices dominates work even though the corpus has 12,000 notices.

The hotspot's portal context matches the scraper notes: P003 is one of the six nodal aggregators, which repeats a long legal preamble, and short notices therefore contain less discriminating content after normalization. P094 is the largest portal, so it dominates total assignments by volume even though its average is not the worst.

## Migration

The mitigation suppresses only buckets larger than 100 notices; these are too common to be useful retrieval evidence and are sent to the later exact-comparison path only when another band survives. The migrated table is `lsh_band_mitigated` with its own covering B-tree index.
After mitigation, the full self-join produced 76,349 unique candidate pairs in 371.5 ms. Per-notice distribution: average 12.7, p95 56, maximum 169. The highest-work portal became `P094` with 17,884 assignments (11.7%); the hottest notice became `N010520` with 169 candidates.
Both retrieval passes are far below the 20-minute (1,200,000 ms) nightly budget: before 376.0 ms and after 371.5 ms for the full candidate graph.
Labelled same-pair survival changed from 229/279 (82.1%) to 229/279 (82.1%); mitigation cost: 0/279 labelled same pairs.

The cap is a targeted migration rather than a global reduction in bands: it removes only demonstrably non-selective buckets, leaves the relational lookup path intact, and measures its recall cost explicitly.
