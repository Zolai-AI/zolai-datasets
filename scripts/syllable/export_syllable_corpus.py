#!/usr/bin/env python3
"""Export syllable_data table to JSONL corpus.

Usage:
    python export_syllable_corpus.py
    python export_syllable_corpus.py --output data/syllable/corpus.jsonl
    python export_syllable_corpus.py --engine rule
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = str(
    Path(__file__).resolve().parents[3] / "data" / "zolai.db"
)
DEFAULT_OUTPUT = str(
    Path(__file__).resolve().parents[3] / "data" / "syllable" / "corpus.jsonl"
)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def export(
    db_path: str = DB_PATH,
    output: str = DEFAULT_OUTPUT,
    engine: str = "",
) -> int:
    """Export syllable_data to JSONL.

    Args:
        db_path: SQLite database path.
        output: Output JSONL file path.
        engine: Filter by engine (empty = all).

    Returns:
        Number of rows exported.
    """
    conn = _connect(db_path)

    # Check table exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='syllable_data';"
    )
    if cur.fetchone() is None:
        print("No syllable_data table found. Run segment_all_words.py first.")
        conn.close()
        return 0

    # Build query
    if engine:
        query = (
            "SELECT word, syllables, confidence, source_table "
            "FROM syllable_data WHERE engine = ? "
            "ORDER BY word;"
        )
        params: tuple = (engine,)
    else:
        query = (
            "SELECT word, syllables, confidence, source_table "
            "FROM syllable_data ORDER BY word;"
        )
        params = ()

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        cur = conn.execute(query, params)
        for row in cur:
            word, syls_json, confidence, source = row
            record = {
                "word": word,
                "syllables": json.loads(syls_json),
                "confidence": confidence,
                "source_table": source,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    conn.close()

    size_kb = out_path.stat().st_size / 1024
    print(f"Exported {count:,} entries to {out_path}")
    print(f"File size: {size_kb:.1f} KB")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export syllable corpus to JSONL."
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"SQLite DB path (default: {DB_PATH})",
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--engine", default="",
        help="Filter by engine (empty = all)",
    )
    args = parser.parse_args()
    export(args.db, args.output, args.engine)


if __name__ == "__main__":
    main()
