#!/usr/bin/env python3
"""Clean vocabulary headwords and cross-fill translations.

Bible-extracted tokens often contain stray punctuation (quotes, commas,
apitheses, question marks, etc.) that prevents dictionary joins.  This
script:

  1. Strips punctuation from headwords.
  2. Merges collisions (same cleaned headword) — keeps higher frequency.
  3. Cross-fills english, myanmar, pos from dictionary where missing.

Usage:
    python fix_vocab_headwords.py              # dry-run (default)
    python fix_vocab_headwords.py --fix        # apply changes
    python fix_vocab_headwords.py --verbose    # show per-row details
"""

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"

# Characters to strip from headwords (ASCII + Unicode smart quotes)
CLEAN_RE = re.compile(
    r"[\"',?!.;:()\[\]"
    r"\u2018\u2019\u201c\u201d"  # smart quotes: '' ""
    r"\u2013\u2014"              # en/em dash
    r"\u2026"                    # ellipsis
    r"]"
)

# SQL fragment: expression that cleans a headword in-place.
# Built once to avoid triple-quote / single-quote escaping issues.
_CHARS = [
    ('"', '"'),       # double quote
    ("'", "'"),       # apostrophe / single quote
    (",", ","),       # comma
    ("?", "?"),       # question mark
    ("!", "!"),       # exclamation
    (".", "."),       # period
    (";", ";"),       # semicolon
    (":", ":"),       # colon
    ("(", "("),       # open paren
    (")", ")"),       # close paren
    ("[", "["),       # open bracket
    ("]", "]"),       # close bracket
    ("\u2018", "\u2018"),  # left single quotation mark
    ("\u2019", "\u2019"),  # right single quotation mark
    ("\u201c", "\u201c"),  # left double quotation mark
    ("\u201d", "\u201d"),  # right double quotation mark
    ("\u2013", "\u2013"),  # en dash
    ("\u2014", "\u2014"),  # em dash
    ("\u2026", "\u2026"),  # horizontal ellipsis
]


def _build_replace_expr(col: str = "headword") -> str:
    """Build a nested REPLACE(TRIM(col), char, '') expression for all punctuation."""
    expr = f"TRIM({col})"
    for char_sql, _ in _CHARS:
        # char_sql is the literal character we want SQLite to replace.
        # In SQL, embed it as a string literal: 'char_sql'
        # Single quotes inside SQL string literals are doubled: ''
        escaped = char_sql.replace("'", "''")
        expr = f"REPLACE({expr}, '{escaped}', '')"
    return expr


CLEAN_EXPR = _build_replace_expr("headword")
# Alias for use in subqueries / CTEs
CLEAN_EXPR_A = _build_replace_expr("a.headword")
CLEAN_EXPR_C = _build_replace_expr("c.headword")


def clean_headword(hw: str) -> str:
    """Strip punctuation from a headword (Python-side)."""
    return CLEAN_RE.sub("", hw).strip()


def run_dry(conn: sqlite3.Connection, verbose: bool) -> None:
    """Report what --fix would do without touching the DB."""
    cur = conn.cursor()

    # ── Step 1: Count dirty headwords ─────────────────────────────────────
    cur.execute(f"""
        SELECT COUNT(*) FROM vocabulary
        WHERE headword != {CLEAN_EXPR}
    """)
    dirty_count = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print("DRY RUN — no changes will be written")
    print(f"{'='*60}")
    print(f"\nHeadwords with punctuation:  {dirty_count:,}")

    # Show sample
    if verbose and dirty_count > 0:
        cur.execute(f"""
            SELECT headword, english, frequency FROM vocabulary
            WHERE headword != {CLEAN_EXPR}
            ORDER BY frequency DESC LIMIT 20
        """)
        print("\n  Sample dirty headwords (top 20 by frequency):")
        for hw, en, freq in cur.fetchall():
            cleaned = clean_headword(hw)
            print(f"    '{hw}' -> '{cleaned}'  eng='{en}'  freq={freq}")

    # ── Step 2: Count potential collisions ────────────────────────────────
    cur.execute(f"""
        SELECT cleaned, COUNT(*) as cnt
        FROM (
            SELECT {CLEAN_EXPR} as cleaned
            FROM vocabulary
        )
        GROUP BY cleaned
        HAVING cnt > 1
    """)
    collisions = cur.fetchall()
    print(f"\nPotential collisions (same cleaned headword):  {len(collisions):,}")
    if verbose and collisions:
        print("\n  Top 20 collision groups:")
        for cleaned, cnt in collisions[:20]:
            cur.execute(f"""
                SELECT headword, frequency FROM vocabulary
                WHERE {CLEAN_EXPR} = ?
                ORDER BY frequency DESC
            """, (cleaned,))
            rows = cur.fetchall()
            print(f"    '{cleaned}' ({cnt} rows): {rows}")

    # ── Step 3: Cross-fill counts ─────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*) FROM vocabulary v
        WHERE (v.english IS NULL OR v.english = '' OR v.english = '-')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = v.headword
                AND d.english IS NOT NULL AND d.english != ''
          )
    """)
    eng_fillable = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM vocabulary v
        WHERE (v.myanmar IS NULL OR v.myanmar = '')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = v.headword
                AND d.myanmar IS NOT NULL AND d.myanmar != ''
          )
    """)
    myan_fillable = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM vocabulary v
        WHERE (v.pos IS NULL OR v.pos = '')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = v.headword
                AND d.pos IS NOT NULL AND d.pos != ''
          )
    """)
    pos_fillable = cur.fetchone()[0]

    print("\nCross-fill candidates (current headword):")
    print(f"  English fillable:  {eng_fillable:,}")
    print(f"  Myanmar fillable:  {myan_fillable:,}")
    print(f"  POS fillable:      {pos_fillable:,}")

    # ── Step 4: After-cleaning fill counts ────────────────────────────────
    # Simulate cleaned headwords and check if MORE joins become possible
    cur.execute(f"""
        WITH cleaned AS (
            SELECT id,
                   headword,
                   {CLEAN_EXPR_A} as cleaned_hw,
                   english, myanmar, pos
            FROM vocabulary a
        )
        SELECT COUNT(*) FROM cleaned c
        WHERE (c.english IS NULL OR c.english = '' OR c.english = '-')
          AND c.cleaned_hw != c.headword
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = c.cleaned_hw
                AND d.english IS NOT NULL AND d.english != ''
          )
    """)
    eng_after_clean = cur.fetchone()[0]

    cur.execute(f"""
        WITH cleaned AS (
            SELECT id,
                   headword,
                   {CLEAN_EXPR_A} as cleaned_hw,
                   english, myanmar, pos
            FROM vocabulary a
        )
        SELECT COUNT(*) FROM cleaned c
        WHERE (c.myanmar IS NULL OR c.myanmar = '')
          AND c.cleaned_hw != c.headword
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = c.cleaned_hw
                AND d.myanmar IS NOT NULL AND d.myanmar != ''
          )
    """)
    myan_after_clean = cur.fetchone()[0]

    cur.execute(f"""
        WITH cleaned AS (
            SELECT id,
                   headword,
                   {CLEAN_EXPR_A} as cleaned_hw,
                   english, myanmar, pos
            FROM vocabulary a
        )
        SELECT COUNT(*) FROM cleaned c
        WHERE (c.pos IS NULL OR c.pos = '')
          AND c.cleaned_hw != c.headword
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = c.cleaned_hw
                AND d.pos IS NOT NULL AND d.pos != ''
          )
    """)
    pos_after_clean = cur.fetchone()[0]

    if eng_after_clean or myan_after_clean or pos_after_clean:
        print("\nAdditional fills unlocked by headword cleaning:")
        print(f"  English:  +{eng_after_clean:,}")
        print(f"  Myanmar:  +{myan_after_clean:,}")
        print(f"  POS:      +{pos_after_clean:,}")

    print(f"\n{'='*60}\n")


def run_fix(conn: sqlite3.Connection, verbose: bool) -> None:
    """Apply all cleaning and cross-fills."""
    cur = conn.cursor()
    t0 = time.time()

    # ── Step 0: Clean dictionary zolai headwords too ──────────────────────
    print("\n[0/6] Cleaning dictionary zolai headwords...")
    dict_clean_expr = _build_replace_expr("zolai")

    # First, find and merge collision groups (same logic as vocabulary)
    cur.execute(f"""
        SELECT id, zolai, {dict_clean_expr} as cleaned,
               english, myanmar, pos
        FROM dictionary
    """)
    all_dict_rows = cur.fetchall()

    from collections import defaultdict
    dict_groups: dict[str, list] = defaultdict(list)
    for row in all_dict_rows:
        dict_groups[row[2]].append(row)  # group by cleaned

    dict_merged = 0
    dict_cleaned = 0
    for cleaned_zolai, rows in dict_groups.items():
        if len(rows) == 1:
            # Single row — just clean it
            rid, orig_zolai, _, ren, rmy, rpos = rows[0]
            if orig_zolai != cleaned_zolai:
                cur.execute("UPDATE dictionary SET zolai=? WHERE id=?",
                            (cleaned_zolai, rid))
                dict_cleaned += 1
            continue

        # Multiple rows — keep best, delete rest
        # Prefer: longer english, lower id
        def sort_key(r):
            is_clean = 1 if r[1] == r[2] else 0
            eng_len = len(r[3] or '')
            return (-eng_len, -is_clean, r[0])
        rows.sort(key=sort_key)
        keep = rows[0]
        delete = rows[1:]

        keep_id, _, _, keep_eng, keep_myan, keep_pos = keep
        for _, _, _, del_eng, del_myan, del_pos in delete:
            if (not keep_eng or keep_eng == '') and del_eng:
                keep_eng = del_eng
            if (not keep_myan or keep_myan == '') and del_myan:
                keep_myan = del_myan
            if (not keep_pos or keep_pos == '') and del_pos:
                keep_pos = del_pos

        # Delete extras first, then update
        delete_ids = [r[0] for r in delete]
        if delete_ids:
            placeholders = ",".join("?" * len(delete_ids))
            cur.execute(f"DELETE FROM dictionary WHERE id IN ({placeholders})",
                        delete_ids)
            dict_merged += len(delete_ids)

        cur.execute("UPDATE dictionary SET zolai=?, english=?, myanmar=?, pos=? WHERE id=?",
                     (cleaned_zolai, keep_eng, keep_myan, keep_pos, keep_id))
        dict_cleaned += 1

        if verbose:
            print(f"  Dict '{cleaned_zolai}': kept id={keep_id}, deleted {len(delete_ids)}")

    print(f"  Cleaned {dict_cleaned:,} dictionary headwords, removed {dict_merged:,} duplicates")

    # ── Step 1: Merge collision groups BEFORE cleaning ─────────────────────
    # Find all rows where cleaning would change the headword, and group them
    # by their cleaned form.  For each group, keep the best row (highest
    # frequency, prefer already-clean over dirty) and delete the rest.
    print("\n[1/6] Finding collision groups...")

    cur.execute(f"""
        SELECT id, headword, {CLEAN_EXPR} as cleaned,
               frequency, english, myanmar, pos
        FROM vocabulary
    """)
    all_rows = cur.fetchall()  # (id, headword, cleaned, freq, eng, myan, pos)

    # Group by cleaned headword
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for row in all_rows:
        cleaned = row[2]
        groups[cleaned].append(row)

    # Find groups that need merging (count > 1)
    merge_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"  Found {len(merge_groups):,} collision groups")

    # ── Step 2: Merge collisions ──────────────────────────────────────────
    print("\n[2/6] Merging collisions (keeping higher frequency)...")
    merged = 0
    cleaned_count = 0

    for cleaned_hw, rows in merge_groups.items():
        # Sort: highest frequency first, then prefer clean headword, then lowest id
        def sort_key(r):
            hw, cleaned, freq = r[1], r[2], r[3]
            is_clean = 1 if hw == cleaned else 0
            return (-freq, -is_clean, r[0])

        rows.sort(key=sort_key)
        keep = rows[0]  # best row
        delete = rows[1:]  # rest

        keep_id, keep_hw, _, keep_freq, keep_eng, keep_myan, keep_pos = keep

        # Merge data from deleted rows into kept row
        for _, del_hw, _, del_freq, del_eng, del_myan, del_pos in delete:
            if not keep_eng and del_eng:
                keep_eng = del_eng
            if not keep_myan and del_myan:
                keep_myan = del_myan
            if not keep_pos and del_pos:
                keep_pos = del_pos

        # Delete duplicates FIRST to avoid UNIQUE constraint collision
        delete_ids = [r[0] for r in delete]
        if delete_ids:
            placeholders = ",".join("?" * len(delete_ids))
            cur.execute(
                f"DELETE FROM vocabulary WHERE id IN ({placeholders})",
                delete_ids,
            )
            merged += len(delete_ids)

        # THEN update kept row: set cleaned headword + merged data
        cur.execute("""
            UPDATE vocabulary
            SET headword = ?, english = ?, myanmar = ?, pos = ?
            WHERE id = ?
        """, (cleaned_hw, keep_eng or "", keep_myan or "", keep_pos or "", keep_id))
        cleaned_count += 1

        if verbose:
            print(
                f"  Merged '{cleaned_hw}': kept id={keep_id} (freq={keep_freq}), "
                f"deleted {len(delete_ids)} duplicates"
            )

    # ── Step 3: Clean remaining non-colliding headwords ───────────────────
    print("\n[3/6] Cleaning remaining headwords...")

    cur.execute(f"""
        UPDATE vocabulary SET headword = {CLEAN_EXPR}
        WHERE headword != {CLEAN_EXPR}
    """)
    cleaned_count += cur.rowcount
    print(f"  Cleaned/merged {cleaned_count:,} headwords, removed {merged:,} duplicates")

    # ── Step 4: Cross-fill from dictionary ────────────────────────────────
    print("\n[4/6] Cross-filling from dictionary...")

    # English
    cur.execute("""
        UPDATE vocabulary SET english = (
            SELECT d.english FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.english IS NOT NULL AND d.english != ''
            LIMIT 1
        )
        WHERE (vocabulary.english IS NULL OR vocabulary.english = '' OR vocabulary.english = '-')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = vocabulary.headword
                AND d.english IS NOT NULL AND d.english != ''
          )
    """)
    eng_filled = cur.rowcount
    print(f"  English filled:  {eng_filled:,}")

    # Myanmar
    cur.execute("""
        UPDATE vocabulary SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (vocabulary.myanmar IS NULL OR vocabulary.myanmar = '')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = vocabulary.headword
                AND d.myanmar IS NOT NULL AND d.myanmar != ''
          )
    """)
    myan_filled = cur.rowcount
    print(f"  Myanmar filled:  {myan_filled:,}")

    # POS
    cur.execute("""
        UPDATE vocabulary SET pos = (
            SELECT d.pos FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.pos IS NOT NULL AND d.pos != ''
            LIMIT 1
        )
        WHERE (vocabulary.pos IS NULL OR vocabulary.pos = '')
          AND EXISTS (
              SELECT 1 FROM dictionary d
              WHERE d.zolai = vocabulary.headword
                AND d.pos IS NOT NULL AND d.pos != ''
          )
    """)
    pos_filled = cur.rowcount
    print(f"  POS filled:      {pos_filled:,}")

    # ── Step 5: Report ────────────────────────────────────────────────────
    print("\n[5/6] Final counts...")

    cur.execute("SELECT COUNT(*) FROM vocabulary")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM vocabulary "
        "WHERE english IS NULL OR english = '' OR english = '-'"
    )
    eng_empty = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM vocabulary WHERE myanmar IS NULL OR myanmar = ''"
    )
    myan_empty = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vocabulary WHERE pos IS NULL OR pos = ''")
    pos_empty = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"RESULTS  ({time.time() - t0:.1f}s)")
    print(f"{'='*60}")
    print(f"  Total vocabulary rows:       {total:,}")
    print(f"  English empty remaining:     {eng_empty:,}")
    print(f"  Myanmar empty remaining:     {myan_empty:,}")
    print(f"  POS empty remaining:         {pos_empty:,}")
    print(f"\n  Headwords cleaned:           {cleaned_count:,}")
    print(f"  Duplicates merged:           {merged:,}")
    print(f"  English cross-filled:        {eng_filled:,}")
    print(f"  Myanmar cross-filled:        {myan_filled:,}")
    print(f"  POS cross-filled:            {pos_filled:,}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Clean vocabulary headwords and cross-fill translations."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report only, no changes (default)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-row details",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=120000")

    try:
        if args.fix:
            run_fix(conn, args.verbose)
            conn.commit()
            print("Changes committed.")
        else:
            run_dry(conn, args.verbose)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
