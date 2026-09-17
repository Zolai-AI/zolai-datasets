#!/usr/bin/env python3
"""Comprehensive vocabulary cross-fill script.

Fills missing columns across dictionary, dictionary_en_zo, vocabulary, and
word_usage by cross-referencing existing data.  Pure SQL — no external APIs.

Rules (dependency order):
  1. vocabulary.myanmar  ← dictionary.myanmar
  2. vocabulary.english  ← dictionary.english
  3. vocabulary.pos      ← dictionary.pos
  4. dictionary_en_zo.myanmar ← dictionary.myanmar
  5. dictionary.myanmar  ← dictionary_en_zo.myanmar
  6. dictionary.myanmar  ← vocabulary.myanmar
  7. dictionary.pos      ← vocabulary.pos
  8. word_usage.myanmar  ← dictionary.myanmar

Usage:
    python fill_all_vocab_gaps.py              # dry-run (default)
    python fill_all_vocab_gaps.py --fix        # apply changes
    python fill_all_vocab_gaps.py --rule 5     # run single rule
    python fill_all_vocab_gaps.py --verbose    # show matched row samples
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"

# ── Rule definitions ─────────────────────────────────────────────────────────

RULES = [
    {
        "id": 1,
        "name": "vocabulary.myanmar ← dictionary.myanmar",
        "target_table": "vocabulary",
        "target_col": "myanmar",
        "update_sql": """
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
        """,
        "count_sql": """
            SELECT COUNT(*) FROM vocabulary v
            JOIN dictionary d ON d.zolai = v.headword
            WHERE (v.myanmar IS NULL OR v.myanmar = '')
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
        """,
    },
    {
        "id": 2,
        "name": "vocabulary.english ← dictionary.english",
        "target_table": "vocabulary",
        "target_col": "english",
        "update_sql": """
            UPDATE vocabulary SET english = (
                SELECT d.english FROM dictionary d
                WHERE d.zolai = vocabulary.headword
                  AND d.english IS NOT NULL AND d.english != ''
                LIMIT 1
            )
            WHERE (vocabulary.english IS NULL OR vocabulary.english = ''
                   OR vocabulary.english = '-')
              AND EXISTS (
                  SELECT 1 FROM dictionary d
                  WHERE d.zolai = vocabulary.headword
                    AND d.english IS NOT NULL AND d.english != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM vocabulary v
            JOIN dictionary d ON d.zolai = v.headword
            WHERE (v.english IS NULL OR v.english = '' OR v.english = '-')
              AND d.english IS NOT NULL AND d.english != ''
        """,
    },
    {
        "id": 3,
        "name": "vocabulary.pos ← dictionary.pos",
        "target_table": "vocabulary",
        "target_col": "pos",
        "update_sql": """
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
        """,
        "count_sql": """
            SELECT COUNT(*) FROM vocabulary v
            JOIN dictionary d ON d.zolai = v.headword
            WHERE (v.pos IS NULL OR v.pos = '')
              AND d.pos IS NOT NULL AND d.pos != ''
        """,
    },
    {
        "id": 4,
        "name": "dictionary_en_zo.myanmar ← dictionary.myanmar",
        "target_table": "dictionary_en_zo",
        "target_col": "myanmar",
        "update_sql": """
            UPDATE dictionary_en_zo SET myanmar = (
                SELECT d.myanmar FROM dictionary d
                WHERE d.english = dictionary_en_zo.headword
                  AND d.myanmar IS NOT NULL AND d.myanmar != ''
                LIMIT 1
            )
            WHERE (dictionary_en_zo.myanmar IS NULL OR dictionary_en_zo.myanmar = '')
              AND EXISTS (
                  SELECT 1 FROM dictionary d
                  WHERE d.english = dictionary_en_zo.headword
                    AND d.myanmar IS NOT NULL AND d.myanmar != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM dictionary_en_zo e
            JOIN dictionary d ON d.english = e.headword
            WHERE (e.myanmar IS NULL OR e.myanmar = '')
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
        """,
    },
    {
        "id": 5,
        "name": "dictionary.myanmar ← dictionary_en_zo.myanmar",
        "target_table": "dictionary",
        "target_col": "myanmar",
        "update_sql": """
            UPDATE dictionary SET myanmar = (
                SELECT e.myanmar FROM dictionary_en_zo e
                WHERE e.headword = dictionary.english
                  AND e.myanmar IS NOT NULL AND e.myanmar != ''
                LIMIT 1
            )
            WHERE (dictionary.myanmar IS NULL OR dictionary.myanmar = '')
              AND EXISTS (
                  SELECT 1 FROM dictionary_en_zo e
                  WHERE e.headword = dictionary.english
                    AND e.myanmar IS NOT NULL AND e.myanmar != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM dictionary d
            JOIN dictionary_en_zo e ON e.headword = d.english
            WHERE (d.myanmar IS NULL OR d.myanmar = '')
              AND e.myanmar IS NOT NULL AND e.myanmar != ''
        """,
    },
    {
        "id": 6,
        "name": "dictionary.myanmar ← vocabulary.myanmar",
        "target_table": "dictionary",
        "target_col": "myanmar",
        "update_sql": """
            UPDATE dictionary SET myanmar = (
                SELECT v.myanmar FROM vocabulary v
                WHERE v.headword = dictionary.zolai
                  AND v.myanmar IS NOT NULL AND v.myanmar != ''
                LIMIT 1
            )
            WHERE (dictionary.myanmar IS NULL OR dictionary.myanmar = '')
              AND EXISTS (
                  SELECT 1 FROM vocabulary v
                  WHERE v.headword = dictionary.zolai
                    AND v.myanmar IS NOT NULL AND v.myanmar != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM dictionary d
            JOIN vocabulary v ON v.headword = d.zolai
            WHERE (d.myanmar IS NULL OR d.myanmar = '')
              AND v.myanmar IS NOT NULL AND v.myanmar != ''
        """,
    },
    {
        "id": 7,
        "name": "dictionary.pos ← vocabulary.pos",
        "target_table": "dictionary",
        "target_col": "pos",
        "update_sql": """
            UPDATE dictionary SET pos = (
                SELECT v.pos FROM vocabulary v
                WHERE v.headword = dictionary.zolai
                  AND v.pos IS NOT NULL AND v.pos != ''
                LIMIT 1
            )
            WHERE (dictionary.pos IS NULL OR dictionary.pos = '')
              AND EXISTS (
                  SELECT 1 FROM vocabulary v
                  WHERE v.headword = dictionary.zolai
                    AND v.pos IS NOT NULL AND v.pos != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM dictionary d
            JOIN vocabulary v ON v.headword = d.zolai
            WHERE (d.pos IS NULL OR d.pos = '')
              AND v.pos IS NOT NULL AND v.pos != ''
        """,
    },
    {
        "id": 8,
        "name": "word_usage.myanmar ← dictionary.myanmar",
        "target_table": "word_usage",
        "target_col": "myanmar",
        "update_sql": """
            UPDATE word_usage SET myanmar = (
                SELECT d.myanmar FROM dictionary d
                WHERE d.zolai = word_usage.word
                  AND d.myanmar IS NOT NULL AND d.myanmar != ''
                LIMIT 1
            )
            WHERE (word_usage.myanmar IS NULL OR word_usage.myanmar = '')
              AND EXISTS (
                  SELECT 1 FROM dictionary d
                  WHERE d.zolai = word_usage.word
                    AND d.myanmar IS NOT NULL AND d.myanmar != ''
              )
        """,
        "count_sql": """
            SELECT COUNT(*) FROM word_usage w
            JOIN dictionary d ON d.zolai = w.word
            WHERE (w.myanmar IS NULL OR w.myanmar = '')
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
        """,
    },
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _col_count(conn: sqlite3.Connection, table: str, col: str) -> tuple[int, int]:
    """Return (total, filled) for a table.column."""
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    filled = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
    ).fetchone()[0]
    return total, filled


def _print_rule_result(rule: dict, pending: int, updated: int, elapsed_ms: float,
                       verbose: bool, conn: sqlite3.Connection) -> None:
    status = "APPLIED" if updated > 0 else "nothing to do"
    print(f"  Rule {rule['id']}: {rule['name']}")
    print(f"    Matched: {pending:,}  |  Updated: {updated:,}  |  {elapsed_ms:.0f}ms  |  {status}")

    if verbose and pending > 0:
        # Show a few sample matches
        tbl = rule["target_table"]
        col = rule["target_col"]
        print(f"    Sample matches:")
        # Pick a representative sample — use the count query with LIMIT
        sample_sql = rule["count_sql"].replace("SELECT COUNT(*)", f"SELECT 1 LIMIT 4")
        # Instead, just show current coverage stats
        t, f = _col_count(conn, tbl, col)
        print(f"      {tbl}.{col}: {f:,}/{t:,} filled")


def _print_summary(conn: sqlite3.Connection) -> None:
    """Print before/after-style coverage for all affected columns."""
    print(f"\n{'='*70}")
    print(f"  VOCABULARY CROSS-FILL — FINAL COVERAGE")
    print(f"{'='*70}")

    for table, col in [
        ("dictionary", "myanmar"),
        ("dictionary", "pos"),
        ("dictionary_en_zo", "myanmar"),
        ("vocabulary", "myanmar"),
        ("vocabulary", "english"),
        ("vocabulary", "pos"),
        ("word_usage", "myanmar"),
    ]:
        total, filled = _col_count(conn, table, col)
        pct = (filled / total * 100) if total > 0 else 0
        bar_len = 30
        filled_bar = int(bar_len * filled / total) if total > 0 else 0
        bar = "█" * filled_bar + "░" * (bar_len - filled_bar)
        print(f"\n  {table}.{col}")
        print(f"    [{bar}] {pct:.1f}%")
        print(f"    {filled:>7,} / {total:>7,} filled")

    print(f"\n{'='*70}")


def _print_monitor_output(conn: sqlite3.Connection) -> None:
    """Equivalent to monitor_myanmar_progress.py output."""
    print(f"\n{'='*70}")
    print(f"  MYANMAR TRANSLATION PROGRESS")
    print(f"{'='*70}")

    for table, col, label in [
        ("dictionary", "myanmar", "Dictionary ZO→EN"),
        ("dictionary_en_zo", "myanmar", "Dictionary EN→ZO"),
        ("vocabulary", "myanmar", "Vocabulary"),
        ("word_usage", "myanmar", "Word Usage"),
    ]:
        total, filled = _col_count(conn, table, col)
        missing = total - filled
        pct = (filled / total * 100) if total > 0 else 0
        bar_len = 30
        filled_bar = int(bar_len * filled / total) if total > 0 else 0
        bar = "█" * filled_bar + "░" * (bar_len - filled_bar)
        print(f"\n  {label}")
        print(f"    [{bar}] {pct:.1f}%")
        print(f"    Done: {filled:,} | Missing: {missing:,} | Total: {total:,}")

    print(f"\n{'='*70}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill missing vocabulary data via cross-table SQL joins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--fix", action="store_true",
                        help="Actually write changes (default: dry-run)")
    parser.add_argument("--rule", type=int, nargs="*", default=None,
                        help="Run only specific rule(s) by ID (e.g. --rule 1 5)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show sample matches for each rule")
    args = parser.parse_args()

    db = DB_PATH
    if not db.exists():
        print(f"Error: database not found at {db}", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.fix

    print(f"Database: {db}")
    print(f"Mode:     {'DRY-RUN' if dry_run else 'WRITE'}")
    print(f"Time:     {time.strftime('%Y-%m-%d %H:%M:%S')}")

    if args.rule:
        print(f"Rules:    {', '.join(str(r) for r in args.rule)}")
    else:
        print(f"Rules:    all (1–{len(RULES)})")

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    # ── BEFORE snapshot ───────────────────────────────────────────────────
    before: dict[str, int] = {}
    for rule in RULES:
        key = f"{rule['target_table']}.{rule['target_col']}"
        if key not in before:
            before[key] = conn.execute(
                f"SELECT COUNT(*) FROM {rule['target_table']}"
                f" WHERE {rule['target_col']} IS NOT NULL AND {rule['target_col']} != ''"
            ).fetchone()[0]

    # ── Run rules ─────────────────────────────────────────────────────────
    rules_to_run = [r for r in RULES if args.rule is None or r["id"] in args.rule]
    total_updated = 0

    for rule in rules_to_run:
        # Count pending before update
        pending = conn.execute(rule["count_sql"]).fetchone()[0]

        if pending == 0:
            print(f"\n  Rule {rule['id']}: {rule['name']}")
            print(f"    Matched: 0  |  nothing to do")
            continue

        t0 = time.monotonic()

        if dry_run:
            # Count only — don't modify
            updated = pending
            elapsed_ms = (time.monotonic() - t0) * 1000
            _print_rule_result(rule, pending, updated, elapsed_ms, args.verbose, conn)
        else:
            conn.execute(rule["update_sql"])
            updated = conn.execute("SELECT changes()").fetchone()[0]
            elapsed_ms = (time.monotonic() - t0) * 1000
            _print_rule_result(rule, pending, updated, elapsed_ms, args.verbose, conn)
            conn.commit()

        total_updated += updated

    # ── AFTER snapshot ────────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  SUMMARY — {'would update' if dry_run else 'updated'} {total_updated:,} rows")
    print(f"{'─'*70}")

    for table, col in [
        ("dictionary", "myanmar"), ("dictionary", "pos"),
        ("dictionary_en_zo", "myanmar"),
        ("vocabulary", "myanmar"), ("vocabulary", "english"), ("vocabulary", "pos"),
        ("word_usage", "myanmar"),
    ]:
        key = f"{table}.{col}"
        t_total, t_filled = _col_count(conn, table, col)
        t_pct = (t_filled / t_total * 100) if t_total > 0 else 0
        print(f"  {key:30s}  {t_filled:>7,}/{t_total:>7,}  ({t_pct:.1f}%)")

    if not dry_run:
        _print_summary(conn)
        _print_monitor_output(conn)

    conn.close()
    print(f"\nDone.")


if __name__ == "__main__":
    main()
