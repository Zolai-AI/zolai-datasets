#!/usr/bin/env python3
"""Cross-table validation and auto-correction for zolai.db.

Phase 1: Detect mismatches (read-only audit)
Phase 2: Auto-correct (dictionary = source of truth)
Phase 3: Fill dictionary_en_zo from dictionary
Phase 4: Re-run cross_fill_all propagation
Phase 5: Print detailed report
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"


def _coverage(conn: sqlite3.Connection, table: str, col: str) -> tuple[int, int]:
    """Return (total, filled) for a table.column."""
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    filled = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
    ).fetchone()[0]
    return total, filled


def _pct(filled: int, total: int) -> float:
    return (filled / total * 100) if total else 0.0


# ── Phase 1: Detect mismatches ──────────────────────────────────────────────

def detect_english_mismatches(conn: sqlite3.Connection) -> list[dict]:
    """dictionary.english vs vocabulary.english — return disagreements."""
    rows = conn.execute("""
        SELECT d.zolai, d.english AS dict_en, v.english AS vocab_en
        FROM dictionary d
        JOIN vocabulary v ON d.zolai = v.headword
        WHERE d.english IS NOT NULL AND d.english != ''
          AND v.english IS NOT NULL AND v.english != ''
          AND d.english != v.english
    """).fetchall()
    return [{"word": r[0], "dict": r[1], "vocab": r[2]} for r in rows]


def detect_myanmar_mismatches(conn: sqlite3.Connection) -> dict:
    """Detect myanmar mismatches across dictionary/vocabulary/word_usage."""
    results = {}

    # dictionary vs vocabulary
    rows = conn.execute("""
        SELECT d.zolai, d.myanmar, v.myanmar
        FROM dictionary d
        JOIN vocabulary v ON d.zolai = v.headword
        WHERE d.myanmar IS NOT NULL AND d.myanmar != ''
          AND v.myanmar IS NOT NULL AND v.myanmar != ''
          AND d.myanmar != v.myanmar
    """).fetchall()
    results["dict_vs_vocab"] = [{"word": r[0], "dict": r[1], "vocab": r[2]} for r in rows]

    # dictionary vs word_usage
    rows = conn.execute("""
        SELECT d.zolai, d.myanmar, w.myanmar
        FROM dictionary d
        JOIN word_usage w ON d.zolai = w.word
        WHERE d.myanmar IS NOT NULL AND d.myanmar != ''
          AND w.myanmar IS NOT NULL AND w.myanmar != ''
          AND d.myanmar != w.myanmar
    """).fetchall()
    results["dict_vs_usage"] = [{"word": r[0], "dict": r[1], "usage": r[2]} for r in rows]

    # vocabulary vs word_usage (both must match dictionary)
    rows = conn.execute("""
        SELECT v.headword, v.myanmar, w.myanmar
        FROM vocabulary v
        JOIN word_usage w ON v.headword = w.word
        WHERE v.myanmar IS NOT NULL AND v.myanmar != ''
          AND w.myanmar IS NOT NULL AND w.myanmar != ''
          AND v.myanmar != w.myanmar
    """).fetchall()
    results["vocab_vs_usage"] = [{"word": r[0], "vocab": r[1], "usage": r[2]} for r in rows]

    return results


def detect_pos_mismatches(conn: sqlite3.Connection) -> list[dict]:
    """dictionary.pos vs vocabulary.pos."""
    rows = conn.execute("""
        SELECT d.zolai, d.pos AS dict_pos, v.pos AS vocab_pos
        FROM dictionary d
        JOIN vocabulary v ON d.zolai = v.headword
        WHERE d.pos IS NOT NULL AND d.pos != ''
          AND v.pos IS NOT NULL AND v.pos != ''
          AND d.pos != v.pos
    """).fetchall()
    return [{"word": r[0], "dict": r[1], "vocab": r[2]} for r in rows]


# ── Phase 2: Auto-correct ───────────────────────────────────────────────────

def fix_vocabulary_english(conn: sqlite3.Connection) -> int:
    """vocabulary.english ← dictionary.english (dictionary wins)."""
    conn.execute("""
        UPDATE vocabulary SET english = (
            SELECT d.english FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.english IS NOT NULL AND d.english != ''
            LIMIT 1
        )
        WHERE headword IN (
            SELECT d.zolai FROM dictionary d
            JOIN vocabulary v ON d.zolai = v.headword
            WHERE d.english != v.english
              AND d.english IS NOT NULL AND d.english != ''
        )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fix_vocabulary_myanmar(conn: sqlite3.Connection) -> int:
    """vocabulary.myanmar ← dictionary.myanmar (dictionary wins)."""
    conn.execute("""
        UPDATE vocabulary SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE headword IN (
            SELECT d.zolai FROM dictionary d
            JOIN vocabulary v ON d.zolai = v.headword
            WHERE (d.myanmar != v.myanmar
                   OR (d.myanmar IS NOT NULL
                       AND (v.myanmar IS NULL OR v.myanmar = '')))
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
        )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fix_word_usage_myanmar(conn: sqlite3.Connection) -> int:
    """word_usage.myanmar ← dictionary.myanmar (dictionary wins)."""
    conn.execute("""
        UPDATE word_usage SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = word_usage.word
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE word IN (
            SELECT d.zolai FROM dictionary d
            JOIN word_usage w ON d.zolai = w.word
            WHERE (d.myanmar != w.myanmar
                   OR (d.myanmar IS NOT NULL
                       AND (w.myanmar IS NULL OR w.myanmar = '')))
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
        )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fix_vocabulary_pos(conn: sqlite3.Connection) -> int:
    """vocabulary.pos ← dictionary.pos (dictionary wins)."""
    conn.execute("""
        UPDATE vocabulary SET pos = (
            SELECT d.pos FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.pos IS NOT NULL AND d.pos != ''
            LIMIT 1
        )
        WHERE headword IN (
            SELECT d.zolai FROM dictionary d
            JOIN vocabulary v ON d.zolai = v.headword
            WHERE d.pos != v.pos
              AND d.pos IS NOT NULL AND d.pos != ''
        )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


# ── Phase 3: Fill dictionary_en_zo ─────────────────────────────────────────

def fix_dictionary_en_zo_myanmar(conn: sqlite3.Connection) -> int:
    """dictionary_en_zo.myanmar ← dictionary.myanmar (fill blanks).

    dictionary_en_zo.headword = English word; dictionary.english = English word.
    Match on English to pull Myanmar from dictionary.
    """
    conn.execute("""
        UPDATE dictionary_en_zo SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.english = dictionary_en_zo.headword
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND headword IN (
              SELECT d.english FROM dictionary d
              WHERE d.myanmar IS NOT NULL AND d.myanmar != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


# ── Phase 4: Cross-fill propagation ────────────────────────────────────────

def run_cross_fill(conn: sqlite3.Connection) -> None:
    """Re-run key cross-fill steps from cross_fill_all.py."""
    # Fill phrases.myanmar from dictionary
    conn.execute("""
        UPDATE phrases SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = phrases.zolai
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND zolai IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    # Fill proverbs.myanmar from dictionary
    conn.execute("""
        UPDATE proverbs SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = proverbs.zolai
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND zolai IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    # Fill training_exercises.myanmar from dictionary
    conn.execute("""
        UPDATE training_exercises SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = training_exercises.zolai
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND zolai IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    conn.commit()


# ── Phase 5: Report ────────────────────────────────────────────────────────

def print_report(
    conn: sqlite3.Connection,
    eng_mismatches: int,
    eng_fixed: int,
    mya_mismatches: int,
    mya_fixed: int,
    pos_mismatches: int,
    pos_fixed: int,
) -> None:
    print("\n" + "=" * 60)
    print("=== Cross-Validation Report ===")
    print("=" * 60)
    print(f"\nEnglish mismatches found: {eng_mismatches} (fixed: {eng_fixed})")
    print(f"Myanmar mismatches found: {mya_mismatches} (fixed: {mya_fixed})")
    print(f"POS mismatches found:     {pos_mismatches} (fixed: {pos_fixed})")

    print("\nPost-correction coverage:")
    coverage_items = [
        ("dictionary.myanmar", "dictionary", "myanmar"),
        ("dictionary.english", "dictionary", "english"),
        ("vocabulary.myanmar", "vocabulary", "myanmar"),
        ("vocabulary.pos", "vocabulary", "pos"),
        ("phrases.myanmar", "phrases", "myanmar"),
        ("proverbs.myanmar", "proverbs", "myanmar"),
        ("word_usage.myanmar", "word_usage", "myanmar"),
        ("training_exercises.myanmar", "training_exercises", "myanmar"),
    ]
    for label, table, col in coverage_items:
        total, filled = _coverage(conn, table, col)
        print(f"  {label:35s} {filled:>7,}/{total:>7,} ({_pct(filled, total):.1f}%)")

    print("\n" + "=" * 60)


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"DB: {DB_PATH}")
    print(f"Size: {DB_PATH.stat().st_size / 1e6:.1f} MB")

    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")

    # ── Phase 1: Detect ──────────────────────────────────────────────────
    print("\n--- Phase 1: Detecting mismatches (read-only) ---")

    eng_mm = detect_english_mismatches(conn)
    print(f"  English mismatches (dict vs vocab): {len(eng_mm)}")

    mya_mm = detect_myanmar_mismatches(conn)
    total_mya = sum(len(v) for v in mya_mm.values())
    for k, v in mya_mm.items():
        print(f"  Myanmar mismatches ({k}): {len(v)}")

    pos_mm = detect_pos_mismatches(conn)
    print(f"  POS mismatches (dict vs vocab):     {len(pos_mm)}")

    # ── Phase 2: Auto-correct ────────────────────────────────────────────
    print("\n--- Phase 2: Auto-correcting (dictionary = source of truth) ---")

    n = fix_vocabulary_english(conn)
    eng_fixed = n
    print(f"  Fixed vocabulary.english:    {n:,}")

    n = fix_vocabulary_myanmar(conn)
    mya_vocab_fixed = n
    print(f"  Fixed vocabulary.myanmar:    {n:,}")

    n = fix_word_usage_myanmar(conn)
    mya_usage_fixed = n
    print(f"  Fixed word_usage.myanmar:    {n:,}")

    n = fix_vocabulary_pos(conn)
    pos_fixed = n
    print(f"  Fixed vocabulary.pos:        {n:,}")

    mya_fixed = mya_vocab_fixed + mya_usage_fixed

    conn.commit()

    # ── Phase 3: Fill dictionary_en_zo ───────────────────────────────────
    print("\n--- Phase 3: Filling dictionary_en_zo.myanmar from dictionary ---")
    n = fix_dictionary_en_zo_myanmar(conn)
    print(f"  Filled dictionary_en_zo.myanmar: {n:,}")
    conn.commit()

    # ── Phase 4: Cross-fill propagation ──────────────────────────────────
    print("\n--- Phase 4: Cross-fill propagation ---")
    run_cross_fill(conn)
    print("  Cross-fill complete.")

    # ── Phase 5: Report ──────────────────────────────────────────────────
    print_report(
        conn,
        eng_mismatches=len(eng_mm),
        eng_fixed=eng_fixed,
        mya_mismatches=total_mya,
        mya_fixed=mya_fixed,
        pos_mismatches=len(pos_mm),
        pos_fixed=pos_fixed,
    )

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
