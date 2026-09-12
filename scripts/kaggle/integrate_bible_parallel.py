#!/usr/bin/env python3
"""Phase 2: Bible Parallel Integration — merge 6-version parallel Bible into bible_verses."""
import json
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
PARALLEL_PATH = "/home/peter/Downloads/Kaggle/data/zolai_bible_dataset/bible_parallel.jsonl"


def verse_id_to_ref(verse_id: str) -> str:
    """GEN.1.1 → GEN 1:1"""
    parts = verse_id.split(".")
    if len(parts) == 3:
        return f"{parts[0]} {parts[1]}:{parts[2]}"
    return verse_id


def integrate(db_path: str, parallel_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    # Get existing refs
    cur.execute("SELECT ref FROM bible_verses")
    existing_refs = {r[0] for r in cur.fetchall()}
    print(f"Existing bible_verses: {len(existing_refs)} rows")

    updated = 0
    inserted = 0
    skipped = 0

    with open(parallel_path) as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            ref = verse_id_to_ref(row["verse_id"])
            book = row["book"]
            chapter = int(row["chapter"])
            verse = int(row["verse"])

            tedim1932 = row.get("tedim1932") or None
            kjv = row.get("kjv") or None
            judson = row.get("judson") or None
            hcl06 = row.get("hcl06") or None
            fcl = row.get("fcl") or None

            if ref in existing_refs:
                # UPDATE — only fill NULL columns
                cur.execute(
                    """UPDATE bible_verses SET
                       zo_tedim1932 = COALESCE(zo_tedim1932, ?),
                       en_kJV = COALESCE(en_kJV, ?),
                       myanmar_judson = COALESCE(myanmar_judson, ?),
                       zo_hcl06 = COALESCE(zo_hcl06, ?),
                       zo_fcl = COALESCE(zo_fcl, ?)
                       WHERE ref = ?""",
                    (tedim1932, kjv, judson, hcl06, fcl, ref),
                )
                if cur.rowcount > 0:
                    updated += 1
            else:
                # INSERT new row
                cur.execute(
                    """INSERT INTO bible_verses
                       (ref, book, chapter, verse, zo_tdb77, zo_tedim2010,
                        en_kJV, myanmar, zo_tedim1932, zo_hcl06, zo_fcl, myanmar_judson)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ref, book, chapter, verse,
                     row.get("tdb77"), None,
                     kjv, None,
                     tedim1932, hcl06, fcl, judson),
                )
                existing_refs.add(ref)
                inserted += 1

            if (i + 1) % 5000 == 0:
                print(f"  Processed {i + 1}... (updated={updated}, inserted={inserted})")

    # Audit log
    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('bible_verses', 0, 'integrate_parallel', '', ?, datetime('now'), ?)""",
        ("", f"Parallel Bible: {updated} updated, {inserted} inserted, {skipped} skipped"),
    )
    conn.commit()
    conn.close()
    print(f"Bible parallel integration done: {updated} updated, {inserted} inserted")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    parallel = sys.argv[2] if len(sys.argv) > 2 else PARALLEL_PATH
    integrate(db, parallel)
