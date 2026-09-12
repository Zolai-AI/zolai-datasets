#!/usr/bin/env python3
"""Phase 4: Dictionary Merge — add new words from Zolai AI online unified vocabulary."""
import json
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
VOCAB_PATH = "/home/peter/Downloads/Kaggle/data/processed/zolai_unified_vocabulary_pure.json"


def merge(db_path: str, vocab_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    # Get existing headwords
    cur.execute("SELECT zolai FROM dictionary")
    existing = {r[0].lower() for r in cur.fetchall()}
    print(f"Existing dictionary headwords: {len(existing)}")

    with open(vocab_path) as f:
        vocab = json.load(f)
    print(f"Zolai AI online unified vocabulary: {len(vocab)} entries")

    inserted = 0
    skipped = 0

    for word, info in vocab.items():
        headword = word.strip().lower()
        if not headword or len(headword) < 2:
            skipped += 1
            continue
        if headword in existing:
            skipped += 1
            continue

        # Extract English definition if available
        english = ""
        if isinstance(info, dict):
            # Try to find an English definition
            for key in ("definition", "english", "meaning", "gloss"):
                if info.get(key):
                    english = str(info[key])
                    break
            if not english:
                english = str(info.get("frequency", ""))
        elif isinstance(info, str):
            english = info

        cur.execute(
            """INSERT INTO dictionary (zolai, english, source, pos, entry_version, updated_at)
               VALUES (?, ?, 'online_unified', '', 'online_v1', datetime('now'))""",
            (headword, english[:500] if english else ""),
        )
        existing.add(headword)
        inserted += 1

        if inserted % 5000 == 0:
            print(f"  Inserted {inserted}... (skipped={skipped})")

    # Audit
    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('dictionary', 0, 'merge_online', '', ?, datetime('now'), ?)""",
        ("", f"Zolai AI online vocab: {inserted} inserted, {skipped} skipped (existing/invalid)"),
    )
    conn.commit()
    conn.close()
    print(f"Dictionary merge done: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    vocab = sys.argv[2] if len(sys.argv) > 2 else VOCAB_PATH
    merge(db, vocab)
