#!/usr/bin/env python3
"""Phase 1: Schema Migration — add new columns and tables for Zolai AI online data."""
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"

MIGRATIONS = [
    # New columns on bible_verses
    ("ALTER TABLE bible_verses ADD COLUMN zo_tedim1932 TEXT", "bible_verses zo_tedim1932"),
    ("ALTER TABLE bible_verses ADD COLUMN zo_hcl06 TEXT", "bible_verses zo_hcl06"),
    ("ALTER TABLE bible_verses ADD COLUMN zo_fcl TEXT", "bible_verses zo_fcl"),
    ("ALTER TABLE bible_verses ADD COLUMN myanmar_judson TEXT", "bible_verses myanmar_judson"),
    ("ALTER TABLE bible_verses ADD COLUMN book_name TEXT", "bible_verses book_name"),
    # New tables
    ("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY,
        title TEXT,
        content TEXT,
        excerpt TEXT,
        categories TEXT,
        date TEXT,
        link TEXT,
        language TEXT DEFAULT 'zolai'
    )""", "articles table"),
    ("""CREATE TABLE IF NOT EXISTS zolai_songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection TEXT,
        song_number INTEGER,
        title TEXT,
        text TEXT,
        source TEXT
    )""", "zolai_songs table"),
]


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(bible_verses)")
    existing_cols = {r[1] for r in cur.fetchall()}

    applied = 0
    for sql, label in MIGRATIONS:
        if sql.startswith("ALTER TABLE"):
            col_name = sql.split("ADD COLUMN")[1].strip().split()[0]
            if col_name in existing_cols:
                print(f"  SKIP (already exists): {label}")
                continue
        try:
            cur.execute(sql)
            applied += 1
            print(f"  APPLIED: {label}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"  SKIP (already exists): {label}")
            else:
                raise

    # Log to audit
    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('schema', 0, 'migrate', '', ?, datetime('now'), ?)""",
        ("", f"Applied {applied} migrations for Zolai AI online integration"),
    )
    conn.commit()
    conn.close()
    print(f"Schema migration done: {applied} changes applied")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(db)
