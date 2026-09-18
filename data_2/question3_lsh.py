"""Question 3: MinHash LSH candidate retrieval from MinIO notices."""

from collections import defaultdict
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import math

import matplotlib.pyplot as plt

from question1_similarity import load_notices, notice_tokens, read_labels, shingles, similarity
from question2_reduced_form import SIGNATURE_SIZE, minhash_signature


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "question3_report.md"
SURVIVAL = ROOT / "question3_survival.csv"
PLOT = ROOT / "question3_survival.png"
RISK_FALSE_MERGE = 100
RISK_MISSED_DUPLICATE = 1
OPERATING_ROWS = 9
OPERATING_BANDS = SIGNATURE_SIZE // OPERATING_ROWS


def band_key(values: tuple[int, ...]) -> bytes:
    return b"".join(value.to_bytes(8, "little") for value in values)


def lsh_buckets(signatures: dict[str, tuple[int, ...]], rows: int, bands: int) -> dict[tuple[int, bytes], list[str]]:
    buckets: dict[tuple[int, bytes], list[str]] = defaultdict(list)
    for notice_id, signature in signatures.items():
        for band in range(bands):
            start = band * rows
            buckets[(band, band_key(signature[start:start + rows]))].append(notice_id)
    return buckets


def candidate_sets(signatures: dict[str, tuple[int, ...]], rows: int, bands: int) -> dict[str, set[str]]:
    buckets = lsh_buckets(signatures, rows, bands)
    candidates = {notice_id: set() for notice_id in signatures}
    for notice_ids in buckets.values():
        for left, right in combinations(notice_ids, 2):
            candidates[left].add(right)
            candidates[right].add(left)
    return candidates


def pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def bucket_metrics(buckets: dict[tuple[int, bytes], list[str]], notice_ids: list[str]) -> tuple[int, float, float, int]:
    raw_pairs = sum(len(notice_ids) * (len(notice_ids) - 1) // 2 for notice_ids in buckets.values())
    raw_counts = {notice_id: 0 for notice_id in notice_ids}
    for bucket_notice_ids in buckets.values():
        for notice_id in bucket_notice_ids:
            raw_counts[notice_id] += len(bucket_notice_ids) - 1
    counts = list(raw_counts.values())
    return raw_pairs, sum(counts) / len(counts), sorted(counts)[math.ceil(.95 * len(counts)) - 1], max(counts)


def metrics(candidates: dict[str, set[str]]) -> tuple[int, float, float, int]:
    sizes = [len(values) for values in candidates.values()]
    pairs = sum(sizes) // 2
    return pairs, sum(sizes) / len(sizes), sorted(sizes)[math.ceil(.95 * len(sizes)) - 1], max(sizes)


def main() -> None:
    notices = load_notices()
    labels = read_labels()
    tokens = {notice_id: notice_tokens(row) for notice_id, row in notices.items()}
    signatures = {notice_id: minhash_signature(value) for notice_id, value in tokens.items()}
    operating_candidates = candidate_sets(signatures, OPERATING_ROWS, OPERATING_BANDS)

    configs = [(3, 246), (6, 123), (9, 82), (18, 41)]
    config_rows = []
    for rows, bands in configs:
        buckets = lsh_buckets(signatures, rows, bands)
        config_rows.append((rows, bands, *bucket_metrics(buckets, list(signatures))))

    labelled = []
    for pair in labels:
        left = pair["notice_id_a"]
        right = pair["notice_id_b"]
        exact = similarity(tokens[left], tokens[right], 3)
        survived = right in operating_candidates[left]
        labelled.append((pair["label"], exact, survived))

    bins = [(index / 10, (index + 1) / 10) for index in range(10)]
    survival_rows = []
    for low, high in bins:
        values = [row for row in labelled if low <= row[1] < high or (low == 0.9 and low <= row[1] <= high)]
        if values:
            survival_rows.append((low, high, len(values), sum(row[2] for row in values) / len(values)))
    with SURVIVAL.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["similarity_low", "similarity_high", "labelled_pairs", "observed_survival_probability"])
        writer.writerows(survival_rows)

    pair_count, average, p95, maximum = metrics(operating_candidates)
    same_recall = sum(row[2] for row in labelled if row[0] == "same") / sum(row[0] == "same" for row in labelled)
    different_survival = sum(row[2] for row in labelled if row[0] == "different") / sum(row[0] == "different" for row in labelled)

    x = [index / 100 for index in range(101)]
    theoretical = [1 - (1 - value ** OPERATING_ROWS) ** OPERATING_BANDS for value in x]
    plt.figure(figsize=(8, 5))
    plt.plot(x, theoretical, label=f"theory: b={OPERATING_BANDS}, r={OPERATING_ROWS}")
    plt.scatter([(low + high) / 2 for low, high, count, observed in survival_rows], [observed for low, high, count, observed in survival_rows], label="labelled pairs", zorder=3)
    operating_similarity = .80
    operating_probability = 1 - (1 - operating_similarity ** OPERATING_ROWS) ** OPERATING_BANDS
    plt.scatter([operating_similarity], [operating_probability], marker="x", s=90, label=f"operating point s={operating_similarity:.2f}")
    plt.xlabel("true 3-shingle Jaccard similarity")
    plt.ylabel("probability pair reaches candidate stage")
    plt.ylim(0, 1.05)
    plt.grid(alpha=.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT, dpi=160)
    plt.close()

    config_text = "\n".join(f"- rows={rows}, bands={bands}: {pairs:,} bucket pair hits, average bucket work {avg:.1f}, p95 {p95}, max {maximum}" for rows, bands, pairs, avg, p95, maximum in config_rows)
    survival_text = "\n".join(f"- {low:.1f}-{high:.1f}: {count} labelled pairs, observed survival {observed:.1%}" for low, high, count, observed in survival_rows)
    REPORT.write_text(
        "\n".join([
            "# Question 3: sublinear candidate retrieval",
            "",
            "Notices were pulled from MinIO and represented by the 738-position MinHash signatures from Question 2. LSH divides each signature into bands; a pair becomes a candidate when one complete band agrees. This avoids all 71,994,000 pair comparisons.",
            "",
            "## Cost/risk setting",
            "",
            f"The explicit product-risk ratio is {RISK_FALSE_MERGE}:1: one false merge is priced at {RISK_FALSE_MERGE} missed-duplicate costs because it can cause a missed deadline and legal exposure. The operating point is `r={OPERATING_ROWS}` rows and `b={OPERATING_BANDS}` bands (`b*r={SIGNATURE_SIZE}`), with a design target of at least 99% candidate survival at true similarity 0.80. The theoretical survival curve is `1 - (1 - s^r)^b`; at s=0.80 it is {operating_probability:.1%}.",
            "",
            "## Candidate-work tradeoff",
            "",
            config_text,
            "",
            f"Chosen operating point on all 12,000 notices: {pair_count:,} candidate pairs, average candidate list {average:.1f}, p95 {p95}, maximum {maximum}.",
            "",
            "## Survival by true similarity",
            "",
            survival_text,
            "",
            f"On the 900 labelled pairs, same-pair candidate survival was {same_recall:.1%}; different-pair survival was {different_survival:.1%}. The latter is candidate work, not a final merge: exact similarity and the conservative threshold still decide merging. The plot is `question3_survival.png`, with the chosen s=0.80 point marked.",
            "",
            "The configuration is tunable: fewer rows per band increases recall and candidate work; more rows reduces work but risks missing true duplicates. The selected point makes the asymmetric risk explicit by protecting retrieval at moderate similarity, while the final merge gate remains conservative.",
        ]) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()