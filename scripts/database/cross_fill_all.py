#!/usr/bin/env python3
"""Comprehensive cross-reference fill script for zolai.db.

Fills ALL missing data by cross-referencing across ALL tables.
No external APIs — pure SQL + Python word-level lookups.

Tables touched:
  vocabulary, dictionary, phrases, proverbs,
  word_usage, training_exercises, grammar_patterns
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"

# ── helpers ──────────────────────────────────────────────────────────────────

def _count(conn: sqlite3.Connection, table: str, col: str) -> tuple[int, int]:
    """Return (total, filled) for a table.column."""
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM {table}")
    total = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''")
    filled = c.fetchone()[0]
    return total, filled


def _before_after(label: str, conn: sqlite3.Connection, table: str, col: str,
                  before: int) -> None:
    total, filled = _count(conn, table, col)
    delta = filled - before
    pct = (filled / total * 100) if total else 0
    print(f"  {label:45s} +{delta:>7,}  ({filled:>7,}/{total:>7,} = {pct:.1f}%)")


# ── Phase 1: Simple SQL cross-fills ──────────────────────────────────────────

def fill_vocabulary_myanmar(conn: sqlite3.Connection) -> int:
    """vocabulary.myanmar ← dictionary.myanmar (direct match on headword)."""
    before = conn.execute(
        "SELECT COUNT(*) FROM vocabulary WHERE myanmar IS NOT NULL AND myanmar != ''"
    ).fetchone()[0]
    conn.execute("""
        UPDATE vocabulary SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND headword IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fill_vocabulary_pos(conn: sqlite3.Connection) -> int:
    """vocabulary.pos ← dictionary.pos (direct match on headword)."""
    conn.execute("""
        UPDATE vocabulary SET pos = (
            SELECT d.pos FROM dictionary d
            WHERE d.zolai = vocabulary.headword
              AND d.pos IS NOT NULL AND d.pos != ''
            LIMIT 1
        )
        WHERE (pos IS NULL OR pos = '')
          AND headword IN (
              SELECT zolai FROM dictionary
              WHERE pos IS NOT NULL AND pos != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fill_dictionary_myanmar(conn: sqlite3.Connection) -> int:
    """dictionary.myanmar ← vocabulary.myanmar (reverse direction)."""
    conn.execute("""
        UPDATE dictionary SET myanmar = (
            SELECT v.myanmar FROM vocabulary v
            WHERE v.headword = dictionary.zolai
              AND v.myanmar IS NOT NULL AND v.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND zolai IN (
              SELECT headword FROM vocabulary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fill_dictionary_pos(conn: sqlite3.Connection) -> int:
    """dictionary.pos ← vocabulary.pos (reverse direction)."""
    conn.execute("""
        UPDATE dictionary SET pos = (
            SELECT v.pos FROM vocabulary v
            WHERE v.headword = dictionary.zolai
              AND v.pos IS NOT NULL AND v.pos != ''
            LIMIT 1
        )
        WHERE (pos IS NULL OR pos = '')
          AND zolai IN (
              SELECT headword FROM vocabulary
              WHERE pos IS NOT NULL AND pos != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fill_word_usage_myanmar(conn: sqlite3.Connection) -> int:
    """word_usage.myanmar ← dictionary.myanmar (match on word)."""
    conn.execute("""
        UPDATE word_usage SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = word_usage.word
              AND d.myanmar IS NOT NULL AND d.myanmar != ''
            LIMIT 1
        )
        WHERE (myanmar IS NULL OR myanmar = '')
          AND word IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def fill_training_exercises_myanmar(conn: sqlite3.Connection) -> int:
    """training_exercises.myanmar ← dictionary.myanmar (match on zolai)."""
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
    return conn.execute("SELECT changes()").fetchone()[0]


# ── Phase 2: Word-level Python lookups (multi-word tables) ───────────────────

def _build_word_myanmar_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Build {zolai_word: myanmar} from dictionary + vocabulary."""
    c = conn.cursor()
    wmap: dict[str, str] = {}

    # Dictionary is authoritative — take first non-empty Myanmar per word
    c.execute("""
        SELECT zolai, myanmar FROM dictionary
        WHERE myanmar IS NOT NULL AND myanmar != ''
    """)
    for word, my in c.fetchall():
        wmap.setdefault(word.strip().lower(), my.strip())

    # Fill gaps from vocabulary
    c.execute("""
        SELECT headword, myanmar FROM vocabulary
        WHERE myanmar IS NOT NULL AND myanmar != ''
    """)
    for word, my in c.fetchall():
        wmap.setdefault(word.strip().lower(), my.strip())

    return wmap


def _lookup_myanmar_for_text(text: str, wmap: dict[str, str]) -> str | None:
    """Split *text* into words and look up each in wmap.

    Returns concatenated Myanmar or None if any word is missing.
    """
    if not text or not text.strip():
        return None
    words = text.strip().split()
    parts: list[str] = []
    for w in words:
        key = w.strip().lower().strip(".,;:!?\"'()[]{}")
        my = wmap.get(key)
        if not my:
            return None
        parts.append(my)
    return " ".join(parts)


def fill_phrases_myanmar(conn: sqlite3.Connection, wmap: dict[str, str]) -> int:
    """phrases.myanmar ← word-by-word dictionary lookup."""
    rows = conn.execute("""
        SELECT id, zolai FROM phrases
        WHERE (myanmar IS NULL OR myanmar = '')
    """).fetchall()
    updates = 0
    for row_id, zolai in rows:
        my = _lookup_myanmar_for_text(zolai, wmap)
        if my:
            conn.execute(
                "UPDATE phrases SET myanmar = ? WHERE id = ?", (my, row_id)
            )
            updates += 1
    return updates


def fill_proverbs_myanmar(conn: sqlite3.Connection, wmap: dict[str, str]) -> int:
    """proverbs.myanmar ← word-by-word dictionary lookup."""
    rows = conn.execute("""
        SELECT id, zolai FROM proverbs
        WHERE (myanmar IS NULL OR myanmar = '')
    """).fetchall()
    updates = 0
    for row_id, zolai in rows:
        my = _lookup_myanmar_for_text(zolai, wmap)
        if my:
            conn.execute(
                "UPDATE proverbs SET myanmar = ? WHERE id = ?", (my, row_id)
            )
            updates += 1
    return updates


def fill_grammar_patterns_myanmar(conn: sqlite3.Connection, wmap: dict[str, str]) -> int:
    """grammar_patterns.myanmar — try to fill from pattern description/examples.

    Grammar patterns don't have a single 'zolai word' column; the pattern is
    abstract (e.g. 'SOV', 'agreement_a').  We attempt extraction from the
    'examples' JSON array — look up the first Zolai word that appears in any
    example verse.  This is best-effort; many patterns won't have a match.
    """
    import json

    rows = conn.execute("""
        SELECT id, examples FROM grammar_patterns
        WHERE (myanmar IS NULL OR myanmar = '')
    """).fetchall()
    updates = 0
    for row_id, examples_json in rows:
        try:
            examples = json.loads(examples_json) if examples_json else []
        except (json.JSONDecodeError, TypeError):
            continue
        # examples is a list of Bible verse refs like "GEN 1:1"
        # We can't directly extract Zolai words from verse refs alone.
        # Skip — patterns without actual Zolai text can't be filled.
        continue  # noqa: no fill possible without the actual verse text
    return updates


# ── Phase 3: Dedup / clean ──────────────────────────────────────────────────

def dedup_dictionary_myanmar(conn: sqlite3.Connection) -> int:
    """Remove duplicate Myanmar entries: if same zolai word has multiple
    dictionary rows with same Myanmar, keep only the first (by id)."""
    conn.execute("""
        DELETE FROM dictionary WHERE id NOT IN (
            SELECT MIN(id) FROM dictionary
            WHERE myanmar IS NOT NULL AND myanmar != ''
            GROUP BY zolai, myanmar
        ) AND myanmar IS NOT NULL AND myanmar != ''
          AND zolai IN (
              SELECT zolai FROM dictionary
              WHERE myanmar IS NOT NULL AND myanmar != ''
              GROUP BY zolai, myanmar
              HAVING COUNT(*) > 1
          )
    """)
    return conn.execute("SELECT changes()").fetchone()[0]


def flag_mismatched_entries(conn: sqlite3.Connection) -> int:
    """Flag entries where English doesn't match across dictionary ↔ vocabulary.

    Returns count of mismatched rows (printed, not modified).
    """
    c = conn.cursor()
    c.execute("""
        SELECT d.zolai, d.english, v.english
        FROM dictionary d
        JOIN vocabulary v ON v.headword = d.zolai
        WHERE d.english IS NOT NULL AND v.english IS NOT NULL
          AND d.english != v.english
          AND d.zolai IN (SELECT headword FROM vocabulary)
        LIMIT 20
    """)
    mismatches = c.fetchall()
    if mismatches:
        print(f"\n  ⚠  English mismatch samples (dictionary vs vocabulary):")
        for zolai, d_en, v_en in mismatches[:10]:
            d_short = (d_en[:30] + "…") if len(d_en) > 30 else d_en
            v_short = (v_en[:30] + "…") if len(v_en) > 30 else v_en
            print(f"      {zolai:20s}  dict={d_short:32s}  vocab={v_short}")
    return len(mismatches)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    db = DB_PATH
    if not db.exists():
        print(f"Error: database not found at {db}", file=sys.stderr)
        sys.exit(1)

    print(f"Database: {db}\n")
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    # Record BEFORE snapshots
    before: dict[str, int] = {}
    for table, col in [
        ("vocabulary", "myanmar"), ("vocabulary", "pos"),
        ("dictionary", "myanmar"), ("dictionary", "pos"),
        ("phrases", "myanmar"), ("proverbs", "myanmar"),
        ("word_usage", "myanmar"), ("training_exercises", "myanmar"),
        ("grammar_patterns", "myanmar"),
    ]:
        before[f"{table}.{col}"] = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]

    # ── Phase 1: Simple SQL cross-fills ──────────────────────────────────
    print("═══ Phase 1: SQL cross-reference fills ═══\n")

    n = fill_vocabulary_myanmar(conn)
    print(f"  vocabulary.myanmar  ← dictionary          +{n:>7,}")

    n = fill_vocabulary_pos(conn)
    print(f"  vocabulary.pos      ← dictionary          +{n:>7,}")

    n = fill_dictionary_myanmar(conn)
    print(f"  dictionary.myanmar  ← vocabulary          +{n:>7,}")

    n = fill_dictionary_pos(conn)
    print(f"  dictionary.pos      ← vocabulary          +{n:>7,}")

    n = fill_word_usage_myanmar(conn)
    print(f"  word_usage.myanmar  ← dictionary          +{n:>7,}")

    n = fill_training_exercises_myanmar(conn)
    print(f"  training_exercises  ← dictionary          +{n:>7,}")

    conn.commit()

    # ── Phase 2: Word-level Python lookups ───────────────────────────────
    print("\n═══ Phase 2: Word-level dictionary lookups ═══\n")

    wmap = _build_word_myanmar_map(conn)
    print(f"  Built word→Myanmar map: {len(wmap):,} entries")

    n = fill_phrases_myanmar(conn, wmap)
    print(f"  phrases.myanmar     ← word-by-word dict   +{n:>7,}")

    n = fill_proverbs_myanmar(conn, wmap)
    print(f"  proverbs.myanmar    ← word-by-word dict   +{n:>7,}")

    n = fill_grammar_patterns_myanmar(conn, wmap)
    print(f"  grammar_patterns    ← (no extractable words) +{n:>7,}")

    conn.commit()

    # ── Phase 3: Dedup / clean ───────────────────────────────────────────
    print("\n═══ Phase 3: Deduplication & consistency ═══\n")

    n = dedup_dictionary_myanmar(conn)
    print(f"  Duplicate dictionary rows removed: {n}")

    n = flag_mismatched_entries(conn)
    print(f"  English mismatches (dict↔vocab): {n}")

    conn.commit()

    # ── Final summary ────────────────────────────────────────────────────
    print("\n═══ Cross-fill Results ═══\n")
    for table, col in [
        ("vocabulary", "myanmar"), ("vocabulary", "pos"),
        ("dictionary", "myanmar"), ("dictionary", "pos"),
        ("phrases", "myanmar"), ("proverbs", "myanmar"),
        ("word_usage", "myanmar"), ("training_exercises", "myanmar"),
        ("grammar_patterns", "myanmar"),
    ]:
        label = f"{table}.{col}"
        _before_after(label, conn, table, col, before[label])

    print("\nDone.")
    conn.close()


if __name__ == "__main__":
    main()
