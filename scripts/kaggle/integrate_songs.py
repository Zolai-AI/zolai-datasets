#!/usr/bin/env python3
"""Phase 6: Song Collections — parse Tedim Labu .txt files into zolai_songs table."""
import os
import re
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
SONGS_DIR = "/home/peter/Downloads/Kaggle/Linguistics/Zolai/Literature/Tedim Labu"


def parse_song_number(filename: str) -> tuple[int, str]:
    """Extract song number and title from filename like 'A AW KA THEI (TDM - 204).txt'"""
    name = os.path.splitext(filename)[0]
    # Try to find TDM number
    m = re.search(r"TDM\s*-\s*(\d+)", name)
    num = int(m.group(1)) if m else 0
    # Title is everything before the (TDM - ...) part
    title = re.sub(r"\s*\(TDM\s*-\s*\d+\)\s*$", "", name).strip()
    return num, title


def integrate(db_path: str, songs_dir: str) -> None:
    if not os.path.isdir(songs_dir):
        print(f"  Songs directory not found: {songs_dir}")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    # Check existing
    cur.execute("SELECT count(*) FROM zolai_songs")
    before = cur.fetchone()[0]

    files = [f for f in os.listdir(songs_dir) if f.endswith(".txt")]
    print(f"  Found {len(files)} song files")

    inserted = 0
    for filename in sorted(files):
        num, title = parse_song_number(filename)
        filepath = os.path.join(songs_dir, filename)
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()

        if not text:
            continue

        cur.execute(
            """INSERT INTO zolai_songs (collection, song_number, title, text, source)
               VALUES (?, ?, ?, ?, ?)""",
            ("Tedim Labu", num, title, text, "kaggle_tedim_labu"),
        )
        inserted += 1

    cur.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES ('zolai_songs', 0, 'integrate_kaggle', '', ?, datetime('now'), ?)""",
        ("", f"Tedim Labu: {inserted} songs inserted"),
    )
    conn.commit()
    conn.close()
    print(f"Song integration done: {inserted} songs inserted")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    songs = sys.argv[2] if len(sys.argv) > 2 else SONGS_DIR
    integrate(db, songs)
