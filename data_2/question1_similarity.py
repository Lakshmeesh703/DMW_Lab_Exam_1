"""Question 1: compare labelled notices pulled from MinIO."""

from csv import DictReader
from io import StringIO
from pathlib import Path
import re
from statistics import mean
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
MINIO = "http://localhost:9000/setubid/notices"
LABELS = ROOT / "labelled_pairs.csv"
REPORT = ROOT / "question1_report.md"

WORD_RE = re.compile(r"[a-z0-9]+")
MONEY_RE = re.compile(r"(?:rs\.?|inr|rupees)\s*[0-9][0-9,]*(?:\.[0-9]+)?(?:\s*(?:lakh|cr|crore))?", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}[-/. ](?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/. ]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b", re.I)
REFERENCE_RE = re.compile(r"\b(?:npas|spc|pwd|ref|mc|tn)[-/a-z0-9]*\d[a-z0-9/-]*\b|\b\d{6,}\b", re.I)


def get_object(key: str) -> str:
    with urlopen(Request(f"{MINIO}/{key}"), timeout=30) as response:
        return response.read().decode("utf-8-sig")


def load_notices() -> dict[str, dict[str, str]]:
    notices = {}
    for shard in range(8):
        text = get_object(f"part-{shard:03d}.csv")
        for row in DictReader(StringIO(text)):
            notices[row["notice_id"]] = row
    return notices


def normalize(text: str) -> list[str]:
    text = text.lower()
    text = MONEY_RE.sub(" money ", text)
    text = DATE_RE.sub(" date ", text)
    text = REFERENCE_RE.sub(" reference ", text)
    text = re.sub(r"national procurement aggregation service.*?(?=name of work|tender|scope|$)", " ", text, flags=re.I | re.S)
    text = re.sub(r"state procurement cell.*?(?=name of work|tender|scope|$)", " ", text, flags=re.I | re.S)
    return WORD_RE.findall(text)


def notice_tokens(row: dict[str, str]) -> list[str]:
    body = row["body"]
    markers = [body.lower().find(marker) for marker in ("name of work:", "tender reference number:", "scope of work")]
    first_content = min((position for position in markers if position >= 0), default=0)
    body = body[first_content:]
    body = re.split(r"\n[-=]{10,}\nDisclaimer:", body, maxsplit=1, flags=re.I)[0]
    title_tokens = normalize(row["title"])
    body_tokens = normalize(body)
    return title_tokens * 3 + body_tokens


def shingles(tokens: list[str], width: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[index:index + width]) for index in range(len(tokens) - width + 1)}


def similarity(first: list[str], second: list[str], width: int) -> float:
    left = shingles(first, width)
    right = shingles(second, width)
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def read_labels() -> list[dict[str, str]]:
    return list(DictReader(LABELS.open(encoding="utf-8-sig", newline="")))


def main() -> None:
    notices = load_notices()
    labels = read_labels()
    tokenized = {notice_id: notice_tokens(row) for notice_id, row in notices.items()}
    scored = [
        (pair, similarity(tokenized[pair["notice_id_a"]], tokenized[pair["notice_id_b"]], 1),
         similarity(tokenized[pair["notice_id_a"]], tokenized[pair["notice_id_b"]], 3))
        for pair in labels
    ]
    same_candidates = [item for item in scored if item[0]["label"] == "same"]
    different_candidates = [item for item in scored if item[0]["label"] == "different"]
    same, same_one, same_three = max(same_candidates, key=lambda item: item[2])
    different, different_one, different_three = min(different_candidates, key=lambda item: item[2])

    lines = [
        "# Question 1: similarity definition",
        "",
        "Source: notices were pulled from the MinIO bucket `setubid/notices`, not read from the local notice files.",
        "",
        "## Adopted representation",
        "",
        "Normalize title plus body to lowercase word tokens. Replace monetary amounts, dates, and reference numbers with typed placeholders because their spelling varies across portals and copies. Remove the two known nodal boilerplate blocks; keep tender subject, entity, location, scope, and amount/date placeholders as signal. The score is Jaccard similarity over token 3-shingles: intersection size divided by union size.",
        "",
        "Three-word shingles preserve short phrases such as a work description and location while reducing matches caused by common individual words. One-word Jaccard is retained as the comparison baseline.",
        "",
        "## Corpus examples",
        "",
        "| labelled pair | label | 1-word Jaccard | 3-word Jaccard |",
        "|---|---:|---:|---:|",
    ]
    for pair, one_score, three_score in ((same, same_one, same_three), (different, different_one, different_three)):
        lines.append(f"| `{pair['notice_id_a']}` / `{pair['notice_id_b']}` | {pair['label']} | {one_score:.4f} | {three_score:.4f} |")

    def evaluate(width: int) -> tuple[float, float, int, int]:
        same_scores = [similarity(tokenized[p["notice_id_a"]], tokenized[p["notice_id_b"]], width) for p in labels if p["label"] == "same"]
        different_scores = [similarity(tokenized[p["notice_id_a"]], tokenized[p["notice_id_b"]], width) for p in labels if p["label"] == "different"]
        threshold = max(different_scores)
        false_merges = sum(score > threshold for score in different_scores)
        missed_merges = sum(score <= threshold for score in same_scores)
        return threshold, sum(score > threshold for score in same_scores) / len(same_scores), false_merges, missed_merges

    one = evaluate(1)
    three = evaluate(3)
    average_unigrams = mean(len(shingles(tokens, 1)) for tokens in tokenized.values())
    average_three_shingles = mean(len(shingles(tokens, 3)) for tokens in tokenized.values())
    lines += [
        "",
        "## Choice and cost",
        "",
        f"The examples above are selected mechanically: the highest-scoring labelled same pair and the lowest-scoring labelled different pair under 3-shingles. Their margins are `{same_three - different_three:.4f}` for 3-shingles and `{same_one - different_one:.4f}` for unigrams.",
        "",
        f"Using a strict score greater than the highest different-pair score gives 1-word threshold `{one[0]:.4f}` and 3-word threshold `{three[0]:.4f}`. At those thresholds, the labelled-set same-pair retrieval rates are `{one[1]:.1%}` and `{three[1]:.1%}` respectively; false merges are not accepted by this threshold rule, while the remaining cost is missed duplicate candidates.",
        "",
        f"I adopt 3-word Jaccard. Measured across all 12,000 notices, the representation averages `{average_unigrams:.1f}` unique unigrams versus `{average_three_shingles:.1f}` unique 3-shingles per notice, so the adopted form costs more storage/set work but discounts boilerplate and accidental common words. Because a false merge can cause a missed deadline and legal exposure, the operating threshold is set from the worst labelled different pair rather than maximizing a symmetric accuracy score.",
        "",
        "The full labelled-pair measurements and MinIO pull are reproducible with `py -3 data_2/question1_similarity.py` after starting `data_2/minio/docker-compose.yml`.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()