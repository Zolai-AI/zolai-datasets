"""Seed Myanmar translations into the SQLite dictionary table.

Reads data/processed/my/dict_zo_my_v1.jsonl and updates the dictionary
table in data/zolai.db, setting the myanmar column for matching headwords.

Does NOT modify existing english/english_clean fields.

Usage:
    python seed_myanmar_to_db.py
    python seed_myanmar_to_db.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parents[2]  # zolai-ai root

DICT_PATH = WORKSPACE / "data" / "processed" / "my" / "dict_zo_my_v1.jsonl"
DB_PATH = WORKSPACE / "data" / "zolai.db"


def load_my_entries() -> dict[str, str]:
    """Load ZO→MY dictionary, deduplicated by headword."""
    entries: dict[str, str] = {}
    if not DICT_PATH.exists():
        print(f"ERROR: {DICT_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(DICT_PATH, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            zw = entry.get("zolai", "")
            my = entry.get("myanmar", "")
            if zw and my and zw not in entries:
                entries[zw] = my
    return entries


def ensure_myanmar_column(cursor: sqlite3.Cursor) -> None:
    """Add myanmar column to dictionary table if missing."""
    cursor.execute("PRAGMA table_info(dictionary)")
    columns = {row[1] for row in cursor.fetchall()}
    if "myanmar" not in columns:
        print("  Adding 'myanmar' column to dictionary table ...")
        cursor.execute("ALTER TABLE dictionary ADD COLUMN myanmar TEXT")
    else:
        print("  'myanmar' column already exists")


def seed_database(entries: dict[str, str], dry_run: bool = False) -> None:
    """Update dictionary table with Myanmar translations."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Ensure column exists
    ensure_myanmar_column(cursor)

    # Check current state
    cursor.execute(
        "SELECT COUNT(*) FROM dictionary "
        "WHERE myanmar IS NOT NULL AND myanmar != ''"
    )
    before = cursor.fetchone()[0]
    print(f"  Rows with Myanmar before: {before}")

    cursor.execute("SELECT COUNT(*) FROM dictionary")
    total_rows = cursor.fetchone()[0]
    print(f"  Total dictionary rows: {total_rows}")

    updated = 0
    matched = 0
    not_found: list[str] = []

    for zw, my in entries.items():
        cursor.execute(
            "SELECT id FROM dictionary WHERE zolai = ?",
            (zw,),
        )
        row = cursor.fetchone()
        if row:
            matched += 1
            if not dry_run:
                cursor.execute(
                    "UPDATE dictionary SET myanmar = ? WHERE zolai = ?",
                    (my, zw),
                )
                updated += 1
        else:
            not_found.append(zw)

    if not dry_run:
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dictionary WHERE myanmar IS NOT NULL AND myanmar != ''")
    after = cursor.fetchone()[0]
    conn.close()

    print(f"\nResults:")
    print(f"  Entries loaded: {len(entries)}")
    print(f"  Matched in DB:  {matched}")
    print(f"  Updated:        {updated}")
    print(f"  Not found:      {len(not_found)}")
    print(f"  Myanmar rows after: {after}")

    if not_found:
        print(f"\n  First 10 not found:")
        for w in not_found[:10]:
            print(f"    {w}")

    if dry_run:
        print("\n  [DRY RUN — no changes written]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Myanmar to database")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    entries = load_my_entries()
    print(f"Loaded {len(entries)} ZO→MY entries")

    seed_database(entries, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
