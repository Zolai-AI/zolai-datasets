#!/usr/bin/env python3
"""Populate wiki_lessons from wiki_content table.

Classifies wiki_content rows into lesson types, extracts grammar
patterns and vocabulary lists, and inserts into wiki_lessons.

Usage:
    python populate_wiki_lessons.py              # populate all
    python populate_wiki_lessons.py --dry-run    # show what would be inserted
    python populate_wiki_lessons.py --stats      # show DB state only
"""
from __future__ import annotations

import argparse
import json
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

# ---------------------------------------------------------------------------
# Category → lesson_type mapping
# ---------------------------------------------------------------------------
CATEGORY_MAP = {
    "grammar": "grammar",
    "vocabulary": "vocabulary",
    "culture": "reference",
    "linguistics": "reference",
    "reference": "reference",
    "literature": "reference",
    "genealogy": "reference",
    "other": "reference",
}


def classify_lesson_type(category: str) -> str:
    return CATEGORY_MAP.get(category, "reference")


def extract_grammar_patterns(content: str) -> str:
    """Extract grammar patterns from markdown tables."""
    patterns: list[str] = []
    for line in content.split("\n"):
        # Match table rows with pipe separators
        if "|" in line and not line.strip().startswith("|---"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                # Skip header-like rows
                if not all(c.isupper() or c == "---" for c in cells):
                    patterns.append(" | ".join(cells[:3]))
    return json.dumps(patterns[:50])  # Cap at 50 patterns


def extract_vocabulary(content: str) -> str:
    """Extract vocabulary from '- `word`' or '- word:' lines."""
    vocab: list[str] = []
    for line in content.split("\n"):
        m = re.match(r"^- [`\"]?(\w[\w\s-]*?)[`\"]?", line)
        if m:
            vocab.append(m.group(1).strip())
    return json.dumps(vocab[:100])  # Cap at 100 entries


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
INSERT_LESSON = """
INSERT OR IGNORE INTO wiki_lessons
    (lesson_type, title, content_summary, word_count,
     grammar_patterns, vocabulary_list, source_file)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

INSERT_AUDIT = """
INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value,
                           changed_at, reason)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")

    if args.stats:
        total = conn.execute(
            "SELECT COUNT(*) FROM wiki_lessons"
        ).fetchone()[0]
        by_type = conn.execute(
            "SELECT lesson_type, COUNT(*) FROM wiki_lessons "
            "GROUP BY lesson_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        print(f"\n=== wiki_lessons stats ({total} rows) ===")
        for lt, cnt in by_type:
            print(f"  {lt}: {cnt}")
        conn.close()
        return

    # Read wiki_content
    rows = conn.execute(
        "SELECT id, wiki_category, source_path, title, content, word_count "
        "FROM wiki_content"
    ).fetchall()

    if not rows:
        print("No wiki_content rows found. Run ingest_wiki_content.py first.")
        conn.close()
        return

    print(f"Processing {len(rows)} wiki_content rows")
    inserted = 0
    skipped = 0

    for wc_id, category, source_path, title, content, word_count in rows:
        lesson_type = classify_lesson_type(category)
        summary = (content[:200] + "...") if len(content) > 200 else content

        grammar = extract_grammar_patterns(content)
        vocab = extract_vocabulary(content)

        if args.dry_run:
            print(f"  WOULD INSERT: {source_path} [{lesson_type}]")
            inserted += 1
            continue

        try:
            cur = conn.execute(
                INSERT_LESSON,
                (lesson_type, title or source_path, summary, word_count,
                 grammar, vocab, source_path),
            )
            if cur.rowcount > 0:
                inserted += 1
                conn.execute(
                    INSERT_AUDIT,
                    ("wiki_lessons", cur.lastrowid, "source_file",
                     "", source_path, now_iso(),
                     f"populate_wiki_lessons: {source_path}"),
                )
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR {source_path}: {e}")

    if not args.dry_run:
        conn.commit()
        print(f"\nInserted: {inserted}, Skipped (dup): {skipped}")
        total = conn.execute(
            "SELECT COUNT(*) FROM wiki_lessons"
        ).fetchone()[0]
        by_type = conn.execute(
            "SELECT lesson_type, COUNT(*) FROM wiki_lessons "
            "GROUP BY lesson_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        print(f"\n=== wiki_lessons stats ({total} rows) ===")
        for lt, cnt in by_type:
            print(f"  {lt}: {cnt}")
    else:
        print(f"\nDry run: {inserted} would be inserted, {skipped} skipped")

    conn.close()


if __name__ == "__main__":
    main()
