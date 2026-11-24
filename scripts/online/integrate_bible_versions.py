#!/usr/bin/env python3
"""Phase 3: Standalone Version Files — fill NULL columns from individual version files."""
import json
import sys

# Dual-engine DB access: sqlite by default, ZOLAI_DB_URL switches to postgres.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect, db_path
# sqlite-only: PRAGMA / AUTOINCREMENT / INSERT OR REPLACE / sqlite_master
# / FTS5 have no PostgreSQL equivalent; run this script on the sqlite engine.

DB_PATH = db_path()
BASE = str(Path.home() / 'Downloads/Kaggle/data/zolai_bible_dataset')

VERSION_FILES = [
    ("bible_tedim1932.jsonl", "zo_tedim1932"),
    ("bible_hcl06.jsonl", "zo_hcl06"),
    ("bible_fcl.jsonl", "zo_fcl"),
    ("bible_judson.jsonl", "myanmar_judson"),
]


def verse_id_to_ref(verse_id: str) -> str:
    parts = verse_id.split(".")
    if len(parts) == 3:
        return f"{parts[0]} {parts[1]}:{parts[2]}"
    return verse_id


def integrate_versions(db_path: str) -> None:
    conn = connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    total_filled = 0

    for filename, column in VERSION_FILES:
        filepath = f"{BASE}/{filename}"
        filled = 0

        with open(filepath) as f:
            for line in f:
                row = json.loads(line)
                ref = verse_id_to_ref(row["verse_id"])
                text = row.get("text") or None
                if not text:
                    continue

                # Only fill NULL
                cur.execute(
                    f"UPDATE bible_verses SET {column} = ? WHERE ref = ? AND {column} IS NULL",
                    (text, ref),
                )
                filled += cur.rowcount

        total_filled += filled
        print(f"  {filename} → {column}: filled {filled} NULLs")

    # Audit
    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('bible_verses', 0, 'integrate_versions', '', ?, datetime('now'), ?)""",
        ("", f"Standalone versions: {total_filled} NULLs filled across {len(VERSION_FILES)} files"),
    )
    conn.commit()
    conn.close()
    print(f"Bible versions integration done: {total_filled} total NULLs filled")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    integrate_versions(db)
