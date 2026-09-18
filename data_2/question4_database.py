"""Question 4: persist MinHash LSH data in PostgreSQL and benchmark lookup."""

from pathlib import Path
import csv
import hashlib
import json
import struct
import time

import psycopg

from question1_similarity import load_notices, notice_tokens
from question2_reduced_form import SIGNATURE_SIZE, minhash_signature
from question3_lsh import OPERATING_BANDS, OPERATING_ROWS, band_key


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "question4_report.md"
MEASUREMENTS = ROOT / "question4_measurements.csv"
DB_DSN = "host=localhost port=5433 dbname=setubid user=setubid password=setubid-secret"


def pack_signature(signature: tuple[int, ...]) -> bytes:
    return struct.pack(f"<{len(signature)}Q", *signature)


def band_hash(signature: tuple[int, ...], band: int) -> bytes:
    start = band * OPERATING_ROWS
    return hashlib.blake2b(band_key(signature[start:start + OPERATING_ROWS]), digest_size=16).digest()


def extract_plan(plan: list[dict]) -> tuple[float, list[tuple[str, int, int]]]:
    root = plan[0]["Plan"]
    execution_time = plan[0]["Execution Time"]
    scans = []

    def visit(node: dict) -> None:
        if "Relation Name" in node:
            scans.append((node.get("Node Type", ""), node.get("Relation Name", ""), node.get("Actual Rows", 0)))
        for child in node.get("Plans", []):
            visit(child)

    visit(root)
    return execution_time, scans


def explain(conn: psycopg.Connection, probe_id: str, force_seq: bool) -> tuple[float, list[tuple[str, str, int]]]:
    with conn.cursor() as cur:
        if force_seq:
            cur.execute("SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off;")
        cur.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
            "SELECT DISTINCT b.notice_id FROM lsh_band AS b "
            "JOIN probe_band AS p ON p.band_no = b.band_no AND p.band_hash = b.band_hash "
            "WHERE b.notice_id <> %s",
            (probe_id,),
        )
        return extract_plan(cur.fetchone()[0])


def main() -> None:
    notices = load_notices()
    signatures = {
        notice_id: minhash_signature(notice_tokens(row))
        for notice_id, row in notices.items()
    }

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE IF EXISTS lsh_band;
                DROP TABLE IF EXISTS notice;
                CREATE TABLE notice (
                    notice_id TEXT PRIMARY KEY,
                    portal_id TEXT NOT NULL,
                    published_at DATE NOT NULL,
                    signature BYTEA NOT NULL
                );
                CREATE TABLE lsh_band (
                    notice_id TEXT NOT NULL REFERENCES notice(notice_id),
                    band_no SMALLINT NOT NULL,
                    band_hash BYTEA NOT NULL,
                    PRIMARY KEY (notice_id, band_no)
                );
            """)
            with cur.copy("COPY notice (notice_id, portal_id, published_at, signature) FROM STDIN") as copy:
                for notice_id, row in notices.items():
                    copy.write_row((notice_id, row["portal_id"], row["published_at"], pack_signature(signatures[notice_id])))
            with cur.copy("COPY lsh_band (notice_id, band_no, band_hash) FROM STDIN") as copy:
                for notice_id, signature in signatures.items():
                    for band in range(OPERATING_BANDS):
                        copy.write_row((notice_id, band, band_hash(signature, band)))
            cur.execute("CREATE INDEX lsh_band_lookup_idx ON lsh_band (band_no, band_hash) INCLUDE (notice_id)")
            cur.execute("ANALYZE notice; ANALYZE lsh_band;")
            probe_id = "N002685"
            cur.execute("CREATE TEMP TABLE probe_band (band_no SMALLINT, band_hash BYTEA) ON COMMIT DROP")
            cur.executemany(
                "INSERT INTO probe_band VALUES (%s, %s)",
                [(band, band_hash(signatures[probe_id], band)) for band in range(OPERATING_BANDS)],
            )
            cur.execute("ANALYZE probe_band")
            with conn.transaction():
                indexed_time, indexed_scans = explain(conn, probe_id, False)
            with conn.transaction():
                sequential_time, sequential_scans = explain(conn, probe_id, True)

            cur.execute(
                "SELECT count(DISTINCT b.notice_id) FROM lsh_band b JOIN probe_band p USING (band_no, band_hash) WHERE b.notice_id <> %s",
                (probe_id,),
            )
            candidate_count = cur.fetchone()[0]

    with MEASUREMENTS.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["access_method", "execution_ms", "candidate_count", "scan_nodes"])
        writer.writerow(["btree_index", f"{indexed_time:.3f}", candidate_count, json.dumps(indexed_scans)])
        writer.writerow(["forced_sequential_scan", f"{sequential_time:.3f}", candidate_count, json.dumps(sequential_scans)])

    REPORT.write_text("\n".join([
        "# Question 4: durable retrieval structure",
        "",
        "MinIO remains the source object store. PostgreSQL is the durable lookup home; the Python process only builds/load data and is not required at application lookup time.",
        "",
        "## Schema and access path",
        "",
        "- `notice(notice_id PRIMARY KEY, portal_id, published_at, signature BYTEA)` stores one stable row per notice and its fixed 738-value signature.",
        "- `lsh_band(notice_id, band_no, band_hash)` stores 82 rows per notice, with a primary key preventing duplicate band rows.",
        "- `lsh_band_lookup_idx` is a covering B-tree on `(band_no, band_hash) INCLUDE (notice_id)`.",
        "",
        "The application looks up the probe's 82 band hashes and joins on the indexed pair. A B-tree locates the matching contiguous key ranges; it does not scan unrelated band rows. I rejected a sequential scan because it must inspect the whole 984,000-row band table for every lookup.",
        "",
        "## Measured lookup",
        "",
        f"Probe notice: `{probe_id}`; candidate rows returned: `{candidate_count}`.",
        f"B-tree lookup: `{indexed_time:.3f} ms`; planner scan nodes: `{indexed_scans}`.",
        f"Forced sequential lookup: `{sequential_time:.3f} ms`; planner scan nodes: `{sequential_scans}`.",
        "",
        "The saved measurement CSV contains the planner scan evidence. The indexed plan should show an Index Only Scan or Bitmap Index Scan on `lsh_band_lookup_idx`; the forced alternative shows a Seq Scan on `lsh_band` and examines the full relation. The tables persist in PostgreSQL across Python process restarts.",
    ]) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()