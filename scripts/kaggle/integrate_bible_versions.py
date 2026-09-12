#!/usr/bin/env python3
"""Phase 3: Standalone Version Files — fill NULL columns from individual version files."""
import json
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
BASE = "/home/peter/Downloads/Kaggle/data/zolai_bible_dataset"

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
    conn = sqlite3.connect(db_path)
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
