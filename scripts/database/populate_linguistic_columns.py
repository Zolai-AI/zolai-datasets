#!/usr/bin/env python3
"""Populate linguistic columns in zolai.db from existing data.

Adds: pos, syllables, syllable_count, myanmar across vocabulary, dictionary,
phrases, and proverbs tables using cross-references.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"


def populate(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    results = {}

    # 1. vocabulary.pos from dictionary.pos
    c.execute("""
        UPDATE vocabulary SET pos = (
            SELECT d.pos FROM dictionary d
            WHERE d.zolai = vocabulary.headword
            AND d.pos IS NOT NULL AND d.pos != ''
            LIMIT 1
        ) WHERE pos IS NULL;
    """)
    results["vocabulary.pos"] = c.rowcount

    # 2. vocabulary.syllables + syllable_count from syllable_data
    c.execute("""
        UPDATE vocabulary SET syllables = (
            SELECT s.syllables FROM syllable_data s
            WHERE s.word = vocabulary.headword
            AND s.status = 'active'
            LIMIT 1
        ), syllable_count = (
            SELECT s.syllable_count FROM syllable_data s
            WHERE s.word = vocabulary.headword
            AND s.status = 'active'
            LIMIT 1
        ) WHERE syllables IS NULL;
    """)
    results["vocabulary.syllables"] = c.rowcount

    # 3. dictionary.syllables + syllable_count from syllable_data
    c.execute("""
        UPDATE dictionary SET syllables = (
            SELECT s.syllables FROM syllable_data s
            WHERE s.word = dictionary.zolai
            AND s.status = 'active'
            LIMIT 1
        ), syllable_count = (
            SELECT s.syllable_count FROM syllable_data s
            WHERE s.word = dictionary.zolai
            AND s.status = 'active'
            LIMIT 1
        ) WHERE syllables IS NULL;
    """)
    results["dictionary.syllables"] = c.rowcount

    # 4. phrases.myanmar from dictionary.myanmar
    c.execute("""
        UPDATE phrases SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = phrases.zolai
            AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        ) WHERE myanmar IS NULL;
    """)
    results["phrases.myanmar"] = c.rowcount

    # 5. proverbs.myanmar from dictionary.myanmar
    c.execute("""
        UPDATE proverbs SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = proverbs.zolai
            AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        ) WHERE myanmar IS NULL;
    """)
    results["proverbs.myanmar"] = c.rowcount

    # 6. Print summary
    print("\n═══ Linguistic Column Population Summary ═══\n")
    for col, count in results.items():
        print(f"  {col:35s} → {count:>6,} rows updated")
    print()

    # Show current fill rates
    print("═══ Fill Rate Summary ═══\n")
    checks = [
        ("vocabulary.pos", "vocabulary", "pos"),
        ("vocabulary.syllables", "vocabulary", "syllables"),
        ("dictionary.syllables", "dictionary", "syllables"),
        ("phrases.myanmar", "phrases", "myanmar"),
        ("proverbs.myanmar", "proverbs", "myanmar"),
    ]
    for label, table, col in checks:
        c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''")
        filled = c.fetchone()[0]
        c.execute(f"SELECT COUNT(*) FROM {table}")
        total = c.fetchone()[0]
        pct = (filled / total * 100) if total > 0 else 0
        print(f"  {label:35s} {filled:>6,}/{total:>6,} ({pct:.1f}%)")
    print()

    conn.commit()


def main() -> None:
    db = DB_PATH
    if not db.exists():
        print(f"Error: database not found at {db}", file=sys.stderr)
        sys.exit(1)

    print(f"Database: {db}")
    conn = sqlite3.connect(str(db))
    try:
        populate(conn)
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
