# Question 2: reduced representation

The source notices were pulled from MinIO by the Question 1 loader. The exact normalized 3-shingle sets are used only for evaluation; production comparison stores a fixed MinHash signature per notice.

## Size chosen before implementation

Application requirement: estimate pairwise Jaccard similarity within ±0.05 with 95% confidence. Hoeffding's bound gives k >= ln(2/(1-confidence)) / (2 * error^2) = 738 independent signature positions. Therefore the fixed reduced form is exactly 738 unsigned 64-bit values, or 5,904 bytes per notice before database overhead. This is a calculated size, not a round-number choice.

## Labelled-pair result

Pairs evaluated: 900 (279 same, 621 different)
Mean absolute error: 0.0183
95th-percentile absolute error: 0.0491
Maximum absolute error: 0.1634
Pairs within +/-0.05: 856/900 (95.1%)
Same-pair mean error: 0.0145; different-pair mean error: 0.0201

The estimator behaved as designed if the observed error is close to the +/-0.05 target; the labelled sample also shows the finite-hash approximation's misses in `question2_results.csv`. The confidence statement is a probabilistic bound over the signature randomness, not a guarantee that every finite labelled pair must fall inside the interval.

The fixed signature is the deliberate space trade: it discards the exact shingle set and retains only 5,904 bytes of hash state per notice, making comparison a fixed-length equality count.
