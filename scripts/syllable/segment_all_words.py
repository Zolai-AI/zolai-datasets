#!/usr/bin/env python3
"""Segment ALL unique Zolai words into syllables and save to DB.

Creates the syllable_data table and bulk-segments every unique word
from the dictionary (primary) and optionally vocab tables.

Usage:
    python segment_all_words.py --dry-run --limit 10
    python segment_all_words.py --source dictionary
    python segment_all_words.py --source all
    python segment_all_words.py --engine rule
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── zolai-core import ──────────────────────────────────────────────
sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "zolai-core")
)
from zolai.syllable import ZolaiSyllabifier

# ── Constants ──────────────────────────────────────────────────────
DB_PATH = str(
    Path(__file__).resolve().parents[3] / "data" / "zolai.db"
)
BATCH_SIZE = 1000

CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS syllable_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    syllables TEXT NOT NULL,
    syllable_count INTEGER NOT NULL,
    engine TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_table TEXT,
    source_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_syllable_word
    ON syllable_data(word, engine);
CREATE INDEX IF NOT EXISTS idx_syllable_source
    ON syllable_data(source_table, source_id);
"""

AUDIT_SQL = """\
INSERT INTO data_audit_log
    (table_name, row_id, field, old_value, new_value, changed_at, reason)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""


# ── Helpers ────────────────────────────────────────────────────────
def _connect(db_path: str) -> sqlite3.Connection:
    """Open DB with WAL mode + busy_timeout."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create syllable_data table if it does not exist."""
    conn.executescript(CREATE_TABLE_SQL)


def _existing_words(
    conn: sqlite3.Connection, engine: str
) -> set[str]:
    """Return set of words already segmented for this engine."""
    cur = conn.execute(
        "SELECT word FROM syllable_data WHERE engine = ?;", (engine,)
    )
    return {row[0] for row in cur.fetchall()}


def _fetch_words(
    conn: sqlite3.Connection, source: str
) -> list[tuple[str, str, int]]:
    """Fetch unique words from the requested source(s).

    Returns list of (word, source_table, source_id).
    """
    words: list[tuple[str, str, int]] = []
    seen: set[str] = set()

    if source in ("dictionary", "all"):
        cur = conn.execute(
            "SELECT DISTINCT zolai, id FROM dictionary;"
        )
        for word, rid in cur.fetchall():
            w = (word or "").strip()
            if w and w not in seen:
                words.append((w, "dictionary", rid))
                seen.add(w)

    if source in ("vocab", "all"):
        cur = conn.execute(
            "SELECT DISTINCT headword, id FROM vocab;"
        )
        for word, rid in cur.fetchall():
            w = (word or "").strip()
            if w and w not in seen:
                words.append((w, "vocab", rid))
                seen.add(w)

    return words


def _log_audit(
    conn: sqlite3.Connection,
    source_table: str,
    source_id: int,
    count: int,
) -> None:
    """Write a single audit entry for the batch."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        AUDIT_SQL,
        (
            "syllable_data",
            source_id,
            "bulk_segment",
            "",
            json.dumps({"count": count}),
            now,
            f"bulk segment {count} words ({source_table})",
        ),
    )


# ── Core ───────────────────────────────────────────────────────────
def segment_words(
    db_path: str = DB_PATH,
    engine: str = "rule",
    source: str = "dictionary",
    limit: int = 0,
    dry_run: bool = False,
) -> dict:
    """Segment words and save to DB.

    Args:
        db_path: Path to SQLite database.
        engine: Segmentation engine ("rule" or "crf").
        source: Word source ("dictionary", "vocab", "all").
        limit: Max words to process (0 = unlimited).
        dry_run: If True, do not write to DB.

    Returns:
        Summary dict with counts.
    """
    conn = _connect(db_path)
    _ensure_table(conn)

    syllabifier = ZolaiSyllabifier(mode=engine)
    existing = _existing_words(conn, engine)
    all_words = _fetch_words(conn, source)

    total = len(all_words)
    processed = 0
    inserted = 0
    skipped_existing = 0
    errors = 0
    rows_to_insert: list[tuple] = []
    audit_rows: list[tuple] = []

    print(f"Source: {source} | Engine: {engine}")
    print(f"Unique words found: {total}")
    print(f"Already segmented ({engine}): {len(existing)}")
    if limit > 0:
        print(f"Limit: {limit}")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    t0 = time.monotonic()

    for word, src_table, src_id in all_words:
        if limit > 0 and processed >= limit:
            break
        processed += 1

        # Skip already-segmented words
        if word in existing:
            skipped_existing += 1
            continue

        try:
            syls = syllabifier.segment(word)
        except Exception as exc:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {word!r} — {exc}")
            continue

        syllables_json = json.dumps(syls)
        count = len(syls)
        now = datetime.now(timezone.utc).isoformat()

        rows_to_insert.append((
            word, syllables_json, count, engine, 1.0,
            src_table, src_id, now, now,
        ))

        # Batch commit
        if len(rows_to_insert) >= BATCH_SIZE:
            if not dry_run:
                conn.executemany(
                    "INSERT OR IGNORE INTO syllable_data "
                    "(word, syllables, syllable_count, engine, "
                    " confidence, source_table, source_id, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    rows_to_insert,
                )
                _log_audit(conn, src_table, src_id, len(rows_to_insert))
                conn.commit()
            inserted += len(rows_to_insert)
            rows_to_insert.clear()

        # Progress indicator
        if processed % 5000 == 0:
            elapsed = time.monotonic() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            print(
                f"  {processed:,} processed | "
                f"{inserted:,} queued | "
                f"{rate:,.0f} words/sec"
            )

    # Flush remaining
    if rows_to_insert:
        if not dry_run:
            conn.executemany(
                "INSERT OR IGNORE INTO syllable_data "
                "(word, syllables, syllable_count, engine, "
                " confidence, source_table, source_id, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                rows_to_insert,
            )
            conn.commit()
        inserted += len(rows_to_insert)

    elapsed = time.monotonic() - t0
    conn.close()

    summary = {
        "total_unique_words": total,
        "processed": processed,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "errors": errors,
        "engine": engine,
        "source": source,
        "elapsed_sec": round(elapsed, 2),
        "dry_run": dry_run,
    }

    print("-" * 50)
    print(f"Done in {elapsed:.1f}s")
    print(f"  Processed:   {processed:,}")
    print(f"  Inserted:    {inserted:,}")
    print(f"  Skipped:     {skipped_existing:,}")
    print(f"  Errors:      {errors}")
    print(f"  Dry run:     {dry_run}")

    return summary


# ── CLI ────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Segment all Zolai words into syllables."
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"SQLite DB path (default: {DB_PATH})",
    )
    parser.add_argument(
        "--engine", choices=["rule", "crf"], default="rule",
        help="Segmentation engine (default: rule)",
    )
    parser.add_argument(
        "--source", choices=["dictionary", "vocab", "all"],
        default="dictionary",
        help="Word source (default: dictionary)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max words to process (0 = unlimited)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without writing",
    )
    args = parser.parse_args()

    segment_words(
        db_path=args.db,
        engine=args.engine,
        source=args.source,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
