"""Question 2: size and measure a MinHash reduced notice representation."""

from pathlib import Path
import hashlib
import math
import sys

import numpy as np

from question1_similarity import LABELS, load_notices, notice_tokens, read_labels, shingles, similarity


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "question2_report.md"
RESULTS = ROOT / "question2_results.csv"
EPSILON = 0.05
CONFIDENCE = 0.95
DELTA = 1 - CONFIDENCE
SIGNATURE_SIZE = math.ceil(math.log(2 / DELTA) / (2 * EPSILON ** 2))
HASH_BYTES = 8


def hash_value(shingle: tuple[str, ...]) -> int:
    payload = " ".join(shingle).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


def minhash_signature(tokens: list[str]) -> tuple[int, ...]:
    base_hashes = np.array([hash_value(shingle) for shingle in shingles(tokens, 3)], dtype=np.uint64)
    seeds = np.arange(1, SIGNATURE_SIZE + 1, dtype=np.uint64)
    multipliers = seeds * np.uint64(0x9E3779B185EBCA87)
    offsets = seeds * np.uint64(0xC2B2AE3D27D4EB4F)
    projected = multipliers[:, None] * base_hashes[None, :] + offsets[:, None]
    return tuple(int(value) for value in projected.min(axis=1))


def estimated_similarity(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return sum(first == second for first, second in zip(left, right)) / SIGNATURE_SIZE


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)
    return ordered[position]


def main() -> None:
    notices = load_notices()
    labels = read_labels()
    tokens = {notice_id: notice_tokens(row) for notice_id, row in notices.items()}
    signatures = {notice_id: minhash_signature(value) for notice_id, value in tokens.items()}

    rows: list[tuple[str, float, float, float]] = []
    for pair in labels:
        left = tokens[pair["notice_id_a"]]
        right = tokens[pair["notice_id_b"]]
        exact = similarity(left, right, 3)
        estimate = estimated_similarity(signatures[pair["notice_id_a"]], signatures[pair["notice_id_b"]])
        rows.append((pair["label"], exact, estimate, abs(exact - estimate)))

    errors = [row[3] for row in rows]
    within_target = sum(error <= EPSILON for error in errors)
    mean_error = sum(errors) / len(errors)
    max_error = max(errors)
    p95_error = percentile(errors, 0.95)
    same_errors = [row[3] for row in rows if row[0] == "same"]
    different_errors = [row[3] for row in rows if row[0] == "different"]

    RESULTS.write_text(
        "label,exact_jaccard,minhash_estimate,absolute_error\n"
        + "\n".join(f"{label},{exact:.6f},{estimate:.6f},{error:.6f}" for label, exact, estimate, error in rows)
        + "\n",
        encoding="utf-8",
    )
    REPORT.write_text(
        "\n".join(
            [
                "# Question 2: reduced representation",
                "",
                "The source notices were pulled from MinIO by the Question 1 loader. The exact normalized 3-shingle sets are used only for evaluation; production comparison stores a fixed MinHash signature per notice.",
                "",
                "## Size chosen before implementation",
                "",
                f"Application requirement: estimate pairwise Jaccard similarity within +/-{EPSILON:.2f} with {CONFIDENCE:.0%} confidence. Hoeffding's bound gives k >= ln(2/(1-confidence)) / (2 * error^2) = {SIGNATURE_SIZE} independent signature positions. Therefore the fixed reduced form is exactly {SIGNATURE_SIZE} unsigned 64-bit values, or {SIGNATURE_SIZE * HASH_BYTES:,} bytes per notice before database overhead. This is a calculated size, not a round-number choice.",
                "",
                "## Labelled-pair result",
                "",
                f"Pairs evaluated: {len(rows)} (279 same, 621 different)",
                f"Mean absolute error: {mean_error:.4f}",
                f"95th-percentile absolute error: {p95_error:.4f}",
                f"Maximum absolute error: {max_error:.4f}",
                f"Pairs within +/-{EPSILON:.2f}: {within_target}/{len(rows)} ({within_target / len(rows):.1%})",
                f"Same-pair mean error: {sum(same_errors) / len(same_errors):.4f}; different-pair mean error: {sum(different_errors) / len(different_errors):.4f}",
                "",
                "The estimator behaved as designed if the observed error is close to the +/-0.05 target; the labelled sample also shows the finite-hash approximation's misses in `question2_results.csv`. The confidence statement is a probabilistic bound over the signature randomness, not a guarantee that every finite labelled pair must fall inside the interval.",
                "",
                "The fixed signature is the deliberate space trade: it discards the exact shingle set and retains only 5,904 bytes of hash state per notice, making comparison a fixed-length equality count.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(REPORT)


if __name__ == "__main__":
    sys.exit(main())