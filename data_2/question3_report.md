# Question 3: sublinear candidate retrieval

Notices were pulled from MinIO and represented by the 738-position MinHash signatures from Question 2. LSH divides each signature into bands; a pair becomes a candidate when one complete band agrees. This avoids all 71,994,000 pair comparisons.

## Cost/risk setting

The explicit product-risk ratio is 100:1: one false merge is priced at 100 missed-duplicate costs because it can cause a missed deadline and legal exposure. The operating point is `r=9` rows and `b=82` bands (`b*r=738`), with a design target of at least 99% candidate survival at true similarity 0.80. The theoretical survival curve is `1 - (1 - s^r)^b`; at s=0.80 it is 100.0%.

## Candidate-work tradeoff

- rows=3, bands=246: 401,638,952 bucket pair hits, average bucket work 66939.8, p95 102128, max 139280
- rows=6, bands=123: 5,721,124 bucket pair hits, average bucket work 953.5, p95 2284, max 4839
- rows=9, bands=82: 560,513 bucket pair hits, average bucket work 93.4, p95 301, max 663
- rows=18, bands=41: 129,022 bucket pair hits, average bucket work 21.5, p95 80, max 180

Chosen operating point on all 12,000 notices: 119,164 candidate pairs, average candidate list 19.9, p95 73, maximum 390.

## Survival by true similarity

- 0.1-0.2: 16 labelled pairs, observed survival 0.0%
- 0.2-0.3: 372 labelled pairs, observed survival 0.0%
- 0.3-0.4: 256 labelled pairs, observed survival 0.4%
- 0.4-0.5: 18 labelled pairs, observed survival 0.0%
- 0.5-0.6: 15 labelled pairs, observed survival 46.7%
- 0.6-0.7: 14 labelled pairs, observed survival 100.0%
- 0.7-0.8: 13 labelled pairs, observed survival 92.3%
- 0.8-0.9: 62 labelled pairs, observed survival 100.0%
- 0.9-1.0: 134 labelled pairs, observed survival 100.0%

On the 900 labelled pairs, same-pair candidate survival was 82.1%; different-pair survival was 0.2%. The latter is candidate work, not a final merge: exact similarity and the conservative threshold still decide merging. The plot is `question3_survival.png`, with the chosen s=0.80 point marked.

The configuration is tunable: fewer rows per band increases recall and candidate work; more rows reduces work but risks missing true duplicates. The selected point makes the asymmetric risk explicit by protecting retrieval at moderate similarity, while the final merge gate remains conservative.
