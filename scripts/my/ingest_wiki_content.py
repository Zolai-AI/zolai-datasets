#!/usr/bin/env python3
"""Ingest markdown from zolai-wiki and data/reference into wiki_content table.

Creates the wiki_content table + FTS5 index, walks markdown files,
and inserts them idempotently (SHA-256 hash skip on re-run).

Usage:
    python ingest_wiki_content.py              # ingest all
    python ingest_wiki_content.py --dry-run    # show what would be ingested
    python ingest_wiki_content.py --stats      # show DB state only
    python ingest_wiki_content.py --limit 10   # ingest max 10 files
    python ingest_wiki_content.py --force      # re-ingest even if hash matches
"""
from __future__ import annotations

import argparse
import hashlib
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
WIKI_DIR = WORKSPACE / "zolai-wiki"
REF_DIR = WORKSPACE / "data" / "reference"

# Directories to skip
SKIP_DIRS = {".git", "node_modules", "archive", "__pycache__"}
SKIP_FILES = {"SUMMARY.md", "README.md"}

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS wiki_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_category TEXT NOT NULL,
    source_path TEXT NOT NULL UNIQUE,
    title TEXT,
    content TEXT NOT NULL,
    word_count INTEGER,
    section_count INTEGER,
    content_hash TEXT NOT NULL,
    entry_version TEXT DEFAULT 'v1.0',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
CREATE_INDEX_CAT = (
    "CREATE INDEX IF NOT EXISTS idx_wiki_cat ON wiki_content(wiki_category);"
)
CREATE_INDEX_HASH = (
    "CREATE INDEX IF NOT EXISTS idx_wiki_hash ON wiki_content(content_hash);"
)
CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_content_fts
USING fts5(title, content, content=wiki_content, content_rowid=id);
"""
REBUILD_FTS = "INSERT INTO wiki_content_fts(wiki_content_fts) VALUES('rebuild')"

INSERT_CONTENT = """
INSERT OR IGNORE INTO wiki_content
    (wiki_category, source_path, title, content, word_count,
     section_count, content_hash)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

REPLACE_CONTENT = """
INSERT OR REPLACE INTO wiki_content
    (wiki_category, source_path, title, content, word_count,
     section_count, content_hash)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

INSERT_AUDIT = """
INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value,
                           changed_at, reason)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def file_hash(path: Path) -> str:
    """Return truncated SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def extract_title(content: str) -> str | None:
    """Extract first '# ' heading as title."""
    for line in content.split("\n"):
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    return None


def count_sections(content: str) -> int:
    """Count ## heading-level sections."""
    return sum(1 for line in content.split("\n") if re.match(r"^##\s+", line))


def classify_category(rel_path: Path) -> str:
    """Classify file into wiki category from path parts."""
    parts = rel_path.parts
    if "grammar" in parts:
        return "grammar"
    if "vocabulary" in parts:
        return "vocabulary"
    if "culture" in parts:
        return "culture"
    if "linguistics" in parts:
        return "linguistics"
    if "reference" in parts or "docs" in parts:
        return "reference"
    if "literature" in parts:
        return "literature"
    if "genealogy" in parts:
        return "genealogy"
    return "other"


def walk_files() -> list[tuple[Path, str]]:
    """Walk zolai-wiki and data/reference for ingestible files."""
    files: list[tuple[Path, str]] = []

    # zolai-wiki
    if WIKI_DIR.exists():
        for md in sorted(WIKI_DIR.rglob("*.md")):
            rel = md.relative_to(WIKI_DIR)
            if any(skip in rel.parts for skip in SKIP_DIRS):
                continue
            if md.name in SKIP_FILES:
                continue
            files.append((md, f"zolai-wiki/{rel}"))

    # data/reference
    if REF_DIR.exists():
        for ext in ("*.md", "*.txt"):
            for fp in sorted(REF_DIR.rglob(ext)):
                rel = fp.relative_to(WORKSPACE)
                if any(skip in fp.parts for skip in SKIP_DIRS):
                    continue
                files.append((fp, str(rel)))

    return files


def get_existing_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {source_path: content_hash} for existing rows."""
    rows = conn.execute(
        "SELECT source_path, content_hash FROM wiki_content"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def print_stats(conn: sqlite3.Connection) -> None:
    """Print wiki_content table statistics."""
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM wiki_content").fetchone()[0]
    cats = cur.execute(
        "SELECT wiki_category, COUNT(*) FROM wiki_content "
        "GROUP BY wiki_category ORDER BY COUNT(*) DESC"
    ).fetchall()
    print(f"\n=== wiki_content stats ({total} rows) ===")
    for cat, cnt in cats:
        print(f"  {cat}: {cnt}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be ingested without writing")
    parser.add_argument("--stats", action="store_true",
                        help="Print DB stats and exit")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max files to ingest (0 = unlimited)")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest even if hash matches")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Create table + indexes + FTS
    conn.executescript(CREATE_TABLE)
    conn.execute(CREATE_INDEX_CAT)
    conn.execute(CREATE_INDEX_HASH)
    conn.executescript(CREATE_FTS)
    conn.commit()

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    files = walk_files()
    print(f"Found {len(files)} files to process")

    existing = get_existing_hashes(conn) if not args.force else {}
    inserted = 0
    skipped = 0
    errors = 0

    for fp, source_path in files:
        if args.limit and inserted >= args.limit:
            break

        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  SKIP {source_path}: {e}")
            errors += 1
            continue

        ch = file_hash(fp)

        # Skip if hash matches (unless --force)
        if not args.force and source_path in existing:
            if existing[source_path] == ch:
                skipped += 1
                continue

        rel = Path(source_path)
        category = classify_category(rel)
        title = extract_title(content)
        wc = len(content.split())
        sc = count_sections(content)

        if args.dry_run:
            print(f"  WOULD INSERT: {source_path} "
                  f"[{category}, {wc}w, {sc}s, {ch}]")
            inserted += 1
            continue

        try:
            sql = REPLACE_CONTENT if args.force else INSERT_CONTENT
            cur = conn.execute(
                sql,
                (category, source_path, title, content, wc, sc, ch),
            )
            if cur.rowcount > 0:
                inserted += 1
                conn.execute(
                    INSERT_AUDIT,
                    ("wiki_content", cur.lastrowid, "content_hash",
                     existing.get(source_path, ""), ch, now_iso(),
                     f"ingest_wiki_content: {source_path}"),
                )
        except Exception as e:
            print(f"  ERROR {source_path}: {e}")
            errors += 1

    if not args.dry_run:
        # Rebuild FTS
        try:
            conn.execute(REBUILD_FTS)
        except Exception:
            pass
        conn.commit()
        print(f"\nInserted: {inserted}, Skipped: {skipped}, Errors: {errors}")
        print_stats(conn)
    else:
        print(f"\nDry run: {inserted} would be inserted, "
              f"{skipped} skipped")

    conn.close()


if __name__ == "__main__":
    main()
