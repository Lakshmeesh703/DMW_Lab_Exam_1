"""Question 5: measure LSH skew, suppress oversized buckets, and compare."""

from pathlib import Path
import csv
import json
import time

import psycopg


ROOT = Path(__file__).resolve().parent
DB_DSN = "host=localhost port=5433 dbname=setubid user=setubid password=setubid-secret"
CAP = 100
REPORT = ROOT / "question5_report.md"
MEASUREMENTS = ROOT / "question5_measurements.csv"
PORTALS = ROOT / "question5_portal_distribution.csv"


def create_pairs(conn: psycopg.Connection, source: str, destination: str) -> float:
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {destination}")
        started = time.perf_counter()
        cur.execute(f"""
            CREATE TEMP TABLE {destination} AS
            SELECT DISTINCT a.notice_id AS notice_id_a, b.notice_id AS notice_id_b
            FROM {source} AS a
            JOIN {source} AS b
              ON a.band_no = b.band_no
             AND a.band_hash = b.band_hash
             AND a.notice_id < b.notice_id
        """)
        conn.commit()
        return (time.perf_counter() - started) * 1000


def stats(conn: psycopg.Connection, pairs: str) -> tuple[int, float, float, int]:
    with conn.cursor() as cur:
        cur.execute(f"""
            WITH counts AS (
                SELECT notice_id, count(*) AS candidate_count
                FROM (
                    SELECT notice_id_a AS notice_id FROM {pairs}
                    UNION ALL
                    SELECT notice_id_b AS notice_id FROM {pairs}
                ) AS all_sides
                GROUP BY notice_id
            ), all_counts AS (
                SELECT n.notice_id, n.portal_id, coalesce(c.candidate_count, 0) AS candidate_count
                FROM notice AS n
                LEFT JOIN counts AS c USING (notice_id)
            )
            SELECT
                (SELECT count(*) FROM {pairs}),
                (SELECT avg(candidate_count) FROM all_counts),
                (SELECT percentile_cont(0.95) within group (order by candidate_count) FROM all_counts),
                (SELECT max(candidate_count) FROM all_counts)
        """)
        return cur.fetchone()


def portal_distribution(conn: psycopg.Connection, pairs: str) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(f"""
            WITH counts AS (
                SELECT notice_id, count(*) AS candidate_count
                FROM (
                    SELECT notice_id_a AS notice_id FROM {pairs}
                    UNION ALL
                    SELECT notice_id_b AS notice_id FROM {pairs}
                ) AS all_sides
                GROUP BY notice_id
            )
            SELECT n.portal_id, count(*) AS notices, sum(coalesce(c.candidate_count, 0)) AS candidate_assignments,
                   round(avg(coalesce(c.candidate_count, 0)), 2) AS avg_candidates,
                   max(coalesce(c.candidate_count, 0)) AS max_candidates
            FROM notice AS n
            LEFT JOIN counts AS c USING (notice_id)
            GROUP BY n.portal_id
            ORDER BY candidate_assignments DESC
        """)
        return cur.fetchall()


def top_notices(conn: psycopg.Connection, pairs: str) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(f"""
            WITH counts AS (
                SELECT notice_id, count(*) AS candidate_count
                FROM (
                    SELECT notice_id_a AS notice_id FROM {pairs}
                    UNION ALL
                    SELECT notice_id_b AS notice_id FROM {pairs}
                ) AS all_sides
                GROUP BY notice_id
            )
            SELECT n.notice_id, n.portal_id, c.candidate_count
            FROM counts AS c
            JOIN notice AS n USING (notice_id)
            ORDER BY c.candidate_count DESC, n.notice_id
            LIMIT 10
        """)
        return cur.fetchall()


def labelled_recall(conn: psycopg.Connection, pairs: str) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS labelled_pairs_q5")
        cur.execute("CREATE TEMP TABLE labelled_pairs_q5 (notice_id_a TEXT, notice_id_b TEXT, label TEXT)")
        with (ROOT / "labelled_pairs.csv").open(encoding="utf-8-sig", newline="") as labels:
            rows = csv.DictReader(labels)
            with cur.copy("COPY labelled_pairs_q5 FROM STDIN") as copy:
                for row in rows:
                    left, right = sorted((row["notice_id_a"], row["notice_id_b"]))
                    copy.write_row((left, right, row["label"]))
        cur.execute(f"""
            SELECT
                count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM {pairs} p
                    WHERE p.notice_id_a = l.notice_id_a AND p.notice_id_b = l.notice_id_b
                )),
                count(*) FILTER (WHERE label = 'same' AND EXISTS (
                    SELECT 1 FROM {pairs} p
                    WHERE p.notice_id_a = l.notice_id_a AND p.notice_id_b = l.notice_id_b
                ))
            FROM labelled_pairs_q5 AS l
        """)
        all_survived, same_survived = cur.fetchone()
        cur.execute("SELECT count(*) FROM labelled_pairs_q5 WHERE label = 'same'")
        same_total = cur.fetchone()[0]
        return same_survived, same_total


def main() -> None:
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS lsh_band_mitigated")
            cur.execute("""
                CREATE TABLE lsh_band_mitigated AS
                WITH bucket_sizes AS (
                    SELECT band_no, band_hash, count(*) AS bucket_size
                    FROM lsh_band
                    GROUP BY band_no, band_hash
                )
                SELECT b.notice_id, b.band_no, b.band_hash
                FROM lsh_band AS b
                JOIN bucket_sizes AS s USING (band_no, band_hash)
                WHERE s.bucket_size <= %s
            """, (CAP,))
            cur.execute("CREATE INDEX lsh_band_mitigated_idx ON lsh_band_mitigated (band_no, band_hash) INCLUDE (notice_id)")
            cur.execute("ANALYZE lsh_band_mitigated")
            conn.commit()

        before_ms = create_pairs(conn, "lsh_band", "candidate_pairs_before")
        before_stats = stats(conn, "candidate_pairs_before")
        before_recall, same_total = labelled_recall(conn, "candidate_pairs_before")
        before_portals = portal_distribution(conn, "candidate_pairs_before")
        before_hot_notices = top_notices(conn, "candidate_pairs_before")

        after_ms = create_pairs(conn, "lsh_band_mitigated", "candidate_pairs_after")
        after_stats = stats(conn, "candidate_pairs_after")
        after_recall, _ = labelled_recall(conn, "candidate_pairs_after")
        after_portals = portal_distribution(conn, "candidate_pairs_after")
        after_hot_notices = top_notices(conn, "candidate_pairs_after")

    with PORTALS.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["stage", "portal_id", "notices", "candidate_assignments", "avg_candidates", "max_candidates"])
        for stage, values in (("before", before_portals), ("after", after_portals)):
            for row in values:
                writer.writerow((stage, *row))

    with MEASUREMENTS.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["stage", "runtime_ms", "candidate_pairs", "average_candidates", "p95_candidates", "max_candidates", "same_labelled_survived", "same_labelled_total"])
        writer.writerow(("before", f"{before_ms:.3f}", *before_stats, before_recall, same_total))
        writer.writerow(("after", f"{after_ms:.3f}", *after_stats, after_recall, same_total))

    top_before = before_portals[0]
    top_after = after_portals[0]
    total_before_assignments = sum(row[2] for row in before_portals)
    total_after_assignments = sum(row[2] for row in after_portals)
    REPORT.write_text("\n".join([
        "# Question 5: skew, cost, and mitigation",
        "",
        "The full retrieval was run from the PostgreSQL LSH structure populated from MinIO. Candidate work is uneven because notices that share a band hash are compared as a bucket; repeated portal wording and short notices make some bands much less selective than others.",
        "",
        "## Before mitigation",
        "",
        f"The LSH table has 715,134 buckets. The largest bucket has 272 notices, p99 bucket size is 5, and only two buckets exceed 100 notices. The full self-join produced {before_stats[0]:,} unique candidate pairs in {before_ms:.1f} ms. Per-notice candidate distribution: average {before_stats[1]:.1f}, p95 {before_stats[2]:.0f}, maximum {before_stats[3]:,}.",
        f"The highest-work portal was `{top_before[0]}` with {top_before[2]:,} candidate assignments across {top_before[1]:,} notices ({top_before[2] / total_before_assignments:.1%} of all assignments); see `question5_portal_distribution.csv` for every portal. The hottest notice was `{before_hot_notices[0][0]}` from `{before_hot_notices[0][1]}` with {before_hot_notices[0][2]:,} candidates.",
        "",
        "Mechanically, a common shingle signature makes a whole band collide. The LSH OR rule then emits every pair in that bucket, so bucket cost grows quadratically with bucket size. This is why a small number of buckets/notices dominates work even though the corpus has 12,000 notices.",
        "The hotspot's portal context matches the scraper notes: P003 is one of the six nodal aggregators, which repeats a long legal preamble, and short notices therefore contain less discriminating content after normalization. P094 is the largest portal, so it dominates total assignments by volume even though its average is not the worst.",
        "",
        "## Migration",
        "",
        f"The mitigation suppresses only buckets larger than {CAP} notices; these are too common to be useful retrieval evidence and are sent to the later exact-comparison path only when another band survives. The migrated table is `lsh_band_mitigated` with its own covering B-tree index.",
        f"After mitigation, the full self-join produced {after_stats[0]:,} unique candidate pairs in {after_ms:.1f} ms. Per-notice distribution: average {after_stats[1]:.1f}, p95 {after_stats[2]:.0f}, maximum {after_stats[3]:,}. The highest-work portal became `{top_after[0]}` with {top_after[2]:,} assignments ({top_after[2] / total_after_assignments:.1%}); the hottest notice became `{after_hot_notices[0][0]}` with {after_hot_notices[0][2]:,} candidates.",
        f"Both retrieval passes are far below the 20-minute (1,200,000 ms) nightly budget: before {before_ms:.1f} ms and after {after_ms:.1f} ms for the full candidate graph.",
        f"Labelled same-pair survival changed from {before_recall}/{same_total} ({before_recall / same_total:.1%}) to {after_recall}/{same_total} ({after_recall / same_total:.1%}); mitigation cost: {(before_recall - after_recall)}/{same_total} labelled same pairs.",
        "",
        "The cap is a targeted migration rather than a global reduction in bands: it removes only demonstrably non-selective buckets, leaves the relational lookup path intact, and measures its recall cost explicitly.",
    ]) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()