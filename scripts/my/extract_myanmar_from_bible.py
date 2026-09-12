#!/usr/bin/env python3
"""Extract Myanmar translations from Bible verses into dictionary table.

For each dictionary word missing a Myanmar translation, searches the
Bible verses for the word in word_alignments, then extracts the
corresponding Myanmar word from the same verse.

Usage:
    python extract_myanmar_from_bible.py              # fill Myanmar
    python extract_myanmar_from_bible.py --dry-run    # show matches only
    python extract_myanmar_from_bible.py --stats      # show coverage
    python extract_myanmar_from_bible.py --limit 100  # process max 100 words
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parents[3]
DB_PATH = WORKSPACE / "data" / "zolai.db"

MYANMAR_RE = re.compile(r"[\u1000-\u109F]+")

INSERT_AUDIT = """
INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value,
                           changed_at, reason)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_myanmar(text: str | None) -> bool:
    if not text:
        return False
    return bool(MYANMAR_RE.search(text))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show matches without updating")
    parser.add_argument("--stats", action="store_true",
                        help="Print coverage stats and exit")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max words to process (0 = unlimited)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Coverage stats
    total_dict = conn.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0]
    has_my = conn.execute(
        "SELECT COUNT(*) FROM dictionary "
        "WHERE myanmar IS NOT NULL AND myanmar != ''"
    ).fetchone()[0]
    missing_my = total_dict - has_my
    bible_my = conn.execute(
        "SELECT COUNT(*) FROM bible_verses "
        "WHERE myanmar_judson IS NOT NULL AND myanmar_judson != ''"
    ).fetchone()[0]
    align_count = conn.execute(
        "SELECT COUNT(*) FROM word_alignments"
    ).fetchone()[0]

    print("\n=== Myanmar extraction stats ===")
    print(f"  Dictionary total:        {total_dict:,}")
    print(f"  Dictionary with Myanmar: {has_my:,}")
    print(f"  Dictionary missing MY:   {missing_my:,}")
    print(f"  Bible verses with MY:    {bible_my:,}")
    print(f"  Word alignments:         {align_count:,}")

    if args.stats:
        conn.close()
        return

    # Get dictionary words missing Myanmar
    dict_rows = conn.execute(
        "SELECT id, zolai FROM dictionary "
        "WHERE myanmar IS NULL OR myanmar = '' "
        "ORDER BY id"
    ).fetchall()

    if args.limit:
        dict_rows = dict_rows[:args.limit]

    print(f"\nProcessing {len(dict_rows)} dictionary entries...")

    updated = 0
    no_match = 0
    errors = 0

    for dict_id, zolai_word in dict_rows:
        if not zolai_word or not zolai_word.strip():
            no_match += 1
            continue

        zolai_lower = zolai_word.strip().lower()

        # Strategy 1: word_alignments → find verse refs → get Myanmar
        refs = conn.execute(
            "SELECT ref FROM word_alignments "
            "WHERE LOWER(zolai_word) = ? LIMIT 5",
            (zolai_lower,),
        ).fetchall()

        my_word = None

        for (ref,) in refs:
            # Get Myanmar from verse at matching position
            verse = conn.execute(
                "SELECT myanmar_judson FROM bible_verses WHERE ref = ?",
                (ref,),
            ).fetchone()
            if verse and verse[0] and has_myanmar(verse[0]):
                # Get position of this word in the verse
                pos_row = conn.execute(
                    "SELECT position FROM word_alignments "
                    "WHERE ref = ? AND LOWER(zolai_word) = ? LIMIT 1",
                    (ref, zolai_lower),
                ).fetchone()
                if pos_row:
                    pos = pos_row[0]
                    # Extract Myanmar word at same position
                    my_words = MYANMAR_RE.findall(verse[0])
                    if 0 < pos <= len(my_words):
                        my_word = my_words[pos - 1]
                        break

        # Strategy 2: Search Bible Myanmar directly for word pattern
        if not my_word:
            verse = conn.execute(
                "SELECT myanmar_judson FROM bible_verses "
                "WHERE myanmar_judson LIKE ? "
                "AND myanmar_judson IS NOT NULL LIMIT 1",
                (f"%{zolai_lower}%",),
            ).fetchone()
            if verse and verse[0] and has_myanmar(verse[0]):
                matches = MYANMAR_RE.findall(verse[0])
                if matches:
                    my_word = matches[0]

        if my_word:
            if args.dry_run:
                print(f"  MATCH: {zolai_word} → {my_word}")
                updated += 1
            else:
                try:
                    conn.execute(
                        "UPDATE dictionary SET myanmar = ? WHERE id = ?",
                        (my_word, dict_id),
                    )
                    conn.execute(
                        INSERT_AUDIT,
                        ("dictionary", dict_id, "myanmar",
                         "", my_word, now_iso(),
                         f"extract_myanmar_from_bible: {zolai_word}"),
                    )
                    updated += 1
                except Exception as e:
                    print(f"  ERROR updating {zolai_word}: {e}")
                    errors += 1
        else:
            no_match += 1

    if not args.dry_run:
        conn.commit()
        print(f"\nUpdated: {updated}, No match: {no_match}, Errors: {errors}")
        # Show new coverage
        new_has = conn.execute(
            "SELECT COUNT(*) FROM dictionary "
            "WHERE myanmar IS NOT NULL AND myanmar != ''"
        ).fetchone()[0]
        print(f"  Myanmar coverage: {has_my:,} → {new_has:,} "
              f"(+{new_has - has_my:,})")
    else:
        print(f"\nDry run: {updated} matches, {no_match} no match")

    conn.close()


if __name__ == "__main__":
    main()
