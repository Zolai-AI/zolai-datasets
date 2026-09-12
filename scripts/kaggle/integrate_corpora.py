#!/usr/bin/env python3
"""Phase 5: Corpus Ingestion — load tongsan articles and simbu dataset."""
import json
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
TONGSAN_PATH = "/home/peter/Downloads/Kaggle/data/processed/tongsan_articles_standardized.jsonl"
SIMBU_PATH = "/home/peter/Downloads/Kaggle/data/processed/zolai_simbu_dataset_clean.jsonl"


def integrate_tongsan(conn: sqlite3.Connection, path: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM tongsan_articles")
    existing_ids = {r[0] for r in cur.fetchall()}
    print(f"  Existing tongsan articles: {len(existing_ids)}")

    inserted = 0
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            aid = row.get("id")
            if aid in existing_ids:
                continue

            categories = row.get("category_names") or row.get("categories") or ""
            if isinstance(categories, list):
                categories = ", ".join(str(c) for c in categories)

            cur.execute(
                """INSERT INTO tongsan_articles
                   (id, title, content, excerpt, categories, date, link, language)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'zolai')""",
                (
                    aid,
                    row.get("title", ""),
                    row.get("content", ""),
                    row.get("excerpt", ""),
                    str(categories)[:500],
                    row.get("date", ""),
                    row.get("link", ""),
                ),
            )
            inserted += 1

    print(f"  Tongsan articles: {inserted} inserted")
    return inserted


def integrate_simbu(conn: sqlite3.Connection, path: str) -> int:
    """Add simbu dataset entries as educational articles in tongsan_articles."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM tongsan_articles")
    existing_ids = {r[0] for r in cur.fetchall()}

    inserted = 0
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            text = row.get("text", "").strip()
            if not text or len(text) < 5:
                continue

            # Use hash of text as ID to avoid collisions
            aid = hash(text) % (2**31)
            if aid in existing_ids:
                continue

            cur.execute(
                """INSERT INTO tongsan_articles
                   (id, title, content, excerpt, categories, date, link, language)
                   VALUES (?, ?, ?, ?, ?, '', '', 'zolai_simbu')""",
                (aid, row.get("source", "simbu"), text, text[:200], "educational"),
            )
            existing_ids.add(aid)
            inserted += 1

    print(f"  Simbu dataset: {inserted} inserted into tongsan_articles")
    return inserted


def integrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    tongsan_count = integrate_tongsan(conn, TONGSAN_PATH)
    simbu_count = integrate_simbu(conn, SIMBU_PATH)

    # Audit
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('corpora', 0, 'integrate_kaggle', '', ?, datetime('now'), ?)""",
        ("", f"Tongsan: {tongsan_count}, Simbu: {simbu_count}"),
    )
    conn.commit()
    conn.close()
    print(f"Corpus integration done: tongsan={tongsan_count}, simbu={simbu_count}")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    integrate(db)
