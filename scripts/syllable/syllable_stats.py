#!/usr/bin/env python3
"""Report syllable segmentation statistics from syllable_data table.

Usage:
    python syllable_stats.py
    python syllable_stats.py --db /path/to/zolai.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB_PATH = str(
    Path(__file__).resolve().parents[3] / "data" / "zolai.db"
)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def report(db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)

    # Check if table exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='syllable_data';"
    )
    if cur.fetchone() is None:
        print("No syllable_data table found. Run segment_all_words.py first.")
        conn.close()
        return

    # Total count
    total = conn.execute(
        "SELECT COUNT(*) FROM syllable_data;"
    ).fetchone()[0]
    unique_words = conn.execute(
        "SELECT COUNT(DISTINCT word) FROM syllable_data;"
    ).fetchone()[0]

    print("=" * 60)
    print("SYLLABLE SEGMENTATION REPORT")
    print("=" * 60)
    print(f"Total rows:           {total:,}")
    print(f"Unique words:         {unique_words:,}")
    print()

    # Distribution by syllable count
    print("Distribution by syllable count:")
    print("-" * 40)
    buckets = {1: [], 2: [], 3: [], 4: []}
    for count, examples in conn.execute(
        "SELECT syllable_count, GROUP_CONCAT(word, ', ') "
        "FROM ("
        "  SELECT word, syllable_count, "
        "    ROW_NUMBER() OVER ("
        "      PARTITION BY syllable_count ORDER BY word"
        "    ) AS rn "
        "  FROM syllable_data"
        ") sub WHERE rn <= 5 "
        "GROUP BY syllable_count "
        "ORDER BY syllable_count;"
    ).fetchall():
        bucket_label = f"{count}-syl" if count <= 3 else "4+-syl"
        key = min(count, 4)
        buckets[key] = examples.split(", ") if examples else []

    for bucket in [1, 2, 3, 4]:
        label = f"{bucket}-syl" if bucket <= 3 else "4+-syl"
        count_row = conn.execute(
            "SELECT COUNT(*) FROM syllable_data "
            "WHERE syllable_count = ?;" if bucket < 4
            else "SELECT COUNT(*) FROM syllable_data "
            "WHERE syllable_count >= ?;",
            (bucket,),
        ).fetchone()[0]
        pct = (count_row / total * 100) if total > 0 else 0
        samples = ", ".join(buckets[bucket][:5])
        print(f"  {label:>6}: {count_row:>6,} ({pct:5.1f}%)  "
              f"e.g. {samples}")

    print()

    # Average confidence
    avg_conf = conn.execute(
        "SELECT AVG(confidence) FROM syllable_data;"
    ).fetchone()[0]
    print(f"Average confidence:   {avg_conf:.4f}" if avg_conf else
          "Average confidence:   N/A")
    print()

    # Coverage by source table
    print("Coverage by source table:")
    print("-" * 40)
    for src, cnt in conn.execute(
        "SELECT source_table, COUNT(*) "
        "FROM syllable_data "
        "GROUP BY source_table "
        "ORDER BY COUNT(*) DESC;"
    ).fetchall():
        label = src or "(unknown)"
        print(f"  {label:>15}: {cnt:>6,}")

    print()

    # Engine breakdown
    print("By engine:")
    print("-" * 40)
    for eng, cnt in conn.execute(
        "SELECT engine, COUNT(*) "
        "FROM syllable_data "
        "GROUP BY engine "
        "ORDER BY COUNT(*) DESC;"
    ).fetchall():
        print(f"  {eng:>10}: {cnt:>6,}")

    print()
    print("=" * 60)
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Syllable segmentation statistics."
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"SQLite DB path (default: {DB_PATH})",
    )
    args = parser.parse_args()
    report(args.db)


if __name__ == "__main__":
    main()
