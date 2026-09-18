# Question 1: similarity definition

Source: notices were pulled from the MinIO bucket `setubid/notices`, not read from the local notice files.

## Adopted representation

Normalize title plus body to lowercase word tokens. Replace monetary amounts, dates, and reference numbers with typed placeholders because their spelling varies across portals and copies. Remove the two known nodal boilerplate blocks; keep tender subject, entity, location, scope, and amount/date placeholders as signal. The score is Jaccard similarity over token 3-shingles: intersection size divided by union size.

Three-word shingles preserve short phrases such as a work description and location while reducing matches caused by common individual words. One-word Jaccard is retained as the comparison baseline.

## Corpus examples

| labelled pair | label | 1-word Jaccard | 3-word Jaccard |
|---|---:|---:|---:|
| `N002685` / `N002686` | same | 1.0000 | 1.0000 |
| `N002149` / `N003382` | different | 0.3150 | 0.1662 |

## Choice and cost

The examples above are selected mechanically: the highest-scoring labelled same pair and the lowest-scoring labelled different pair under 3-shingles. Their margins are `0.8338` for 3-shingles and `0.6850` for unigrams.

Using a strict score greater than the highest different-pair score gives 1-word threshold `0.6315` and 3-word threshold `0.4202`. At those thresholds, the labelled-set same-pair retrieval rates are `81.0%` and `90.0%` respectively; false merges are not accepted by this threshold rule, while the remaining cost is missed duplicate candidates.

I adopt 3-word Jaccard. Measured across all 12,000 notices, the representation averages `292.6` unique unigrams versus `509.7` unique 3-shingles per notice, so the adopted form costs more storage/set work but discounts boilerplate and accidental common words. Because a false merge can cause a missed deadline and legal exposure, the operating threshold is set from the worst labelled different pair rather than maximizing a symmetric accuracy score.

The full labelled-pair measurements and MinIO pull are reproducible with `py -3 data_2/question1_similarity.py` after starting `data_2/minio/docker-compose.yml`.
