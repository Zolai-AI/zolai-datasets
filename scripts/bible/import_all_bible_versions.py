#!/usr/bin/env python3
"""Reusable Bible USX importer — imports ALL versions from Kaggle source.

Parses USX files from the Kaggle Chin-Bible dataset and populates the
bible_verses table in zolai.db with all available Bible versions.

Sources:
  TDB77          → zo_tdb77     (Tedim Bible 1977)
  Chin 1977      → zo_tedim2010 (Tedim Bible 2010/2011)
  HCL06          → zo_hcl06     (Hakha Chin 2006)
  FCL            → zo_fcl       (Falam Chin 2002)
  KJV            → en_kJV       (English King James)
  Judson         → myanmar_judson + myanmar (Myanmar Judson)

NOTE: "Tedim (Chin) Bible" directory is SKIPped — it is actually the
Lai (Hakha) Common Language Bible 2006 with misleading naming. Use HCL06.

Usage:
    python import_all_bible_versions.py [--all] [--source NAME] [--dry-run] [--verbose]
    python import_all_bible_versions.py --source TDB77 --dry-run --verbose
    python import_all_bible_versions.py --all --verbose
"""

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"
KAGGLE_ROOT = Path("/home/peter/Downloads/Kaggle/Chin-Bible")

# ── Source mapping: Kaggle directory → DB column ─────────────────────────────
SOURCES = {
    "TDB77": {
        "dir": "TDB77/USX_1",
        "column": "zo_tdb77",
        "description": "Tedim Bible 1977",
    },
    "Chin 1977 (Tedim Bible)": {
        "dir": "Chin 1977 (Tedim Bible)/USX_1",
        "column": "zo_tedim2010",
        "description": "Tedim Bible 2010/2011",
    },
    "HCL06": {
        "dir": "HCL06/USX_1",
        "column": "zo_hcl06",
        "description": "Hakha Chin 2006",
    },
    "FCL": {
        "dir": "FCL/USX_1",
        "column": "zo_fcl",
        "description": "Falam Chin 2002",
    },
    "KJV": {
        "dir": "King James Version/USX",
        "column": "en_kJV",
        "description": "English King James Version",
    },
    "Judson": {
        "dir": "Judson Bible Burmese/USX_1",
        "column": "myanmar_judson",
        "description": "Myanmar Judson Bible",
    },
}

# ── Regex patterns for USX parsing ───────────────────────────────────────────
# Zero-width characters + soft hyphen
ZW_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
# Any remaining XML/HTML tags
TAG_PATTERN = re.compile(r"<[^>]+>")
# Multiple whitespace → single space
WS_PATTERN = re.compile(r"[ \t\u00a0]+")
# Leading/trailing whitespace on lines
STRIP_LINE = re.compile(r"^\s+|\s+$", re.MULTILINE)
# Verse number with optional # suffix
VERSE_NUM_PATTERN = re.compile(r"(\d+)#?")
# Chapter marker
CHAPTER_PATTERN = re.compile(r'<chapter\s+number="(\d+)"\s+style="c"\s*/?>')
# Verse marker (handles both self-closing styles)
VERSE_PATTERN = re.compile(r'<verse\s+number="(\d+[^"]*)"\s+style="v"\s*/?>')


def clean_text(text: str) -> str:
    """Clean extracted text: remove XML tags, ZW chars, normalize whitespace."""
    text = ZW_PATTERN.sub("", text)
    text = TAG_PATTERN.sub("", text)
    text = WS_PATTERN.sub(" ", text)
    text = STRIP_LINE.sub("", text)
    return text.strip()


def parse_verse_number(raw: str) -> int:
    """Parse verse number, stripping # suffix if present."""
    m = VERSE_NUM_PATTERN.match(raw)
    if m:
        return int(m.group(1))
    # Fallback: try plain int
    return int(raw.rstrip("#"))


def parse_usx_file(filepath: Path, verbose: bool = False) -> list[tuple[str, int, int, str]]:
    """Parse a single USX file, returning list of (book, chapter, verse, text).

    Handles USX quirks:
    1. Verse markers: <verse number="X" style="v" /> or <verse number="X" style="v"/>
    2. Chapter markers: <chapter number="X" style="c" />
    3. Verse numbers with # suffix: <verse number="1#" style="v"/>
    4. XML inline tags: <char style="xt">...</char>, <char style="add">...</char>
    5. Zero-width characters: \u200b, \u200c, \u200d, \ufeff
    6. Multi-paragraph verses: text spans multiple <para> elements
    """
    content = filepath.read_text(encoding="utf-8")

    # Extract book code from <book code="GEN" style="id">
    book_match = re.search(r'<book\s+code="([A-Z0-9]+)"', content)
    if not book_match:
        if verbose:
            print(f"  WARNING: No book code found in {filepath.name}")
        return []
    book_code = book_match.group(1)

    # Normalize to single line (handles multi-line tags)
    content = re.sub(r"\n\s*", " ", content)

    # Find all chapter markers
    chapter_positions = list(re.finditer(CHAPTER_PATTERN, content))
    if not chapter_positions:
        if verbose:
            print(f"  WARNING: No chapter markers in {filepath.name}")
        return []

    results: list[tuple[str, int, int, str]] = []

    for ch_idx, ch_match in enumerate(chapter_positions):
        chapter_num = int(ch_match.group(1))
        ch_start = ch_match.end()
        ch_end = (
            chapter_positions[ch_idx + 1].start()
            if ch_idx + 1 < len(chapter_positions)
            else len(content)
        )
        chapter_content = content[ch_start:ch_end]

        # Find all verse markers in this chapter
        verse_positions = list(re.finditer(VERSE_PATTERN, chapter_content))

        for v_idx, v_match in enumerate(verse_positions):
            verse_num = parse_verse_number(v_match.group(1))
            v_start = v_match.end()
            v_end = (
                verse_positions[v_idx + 1].start()
                if v_idx + 1 < len(verse_positions)
                else len(chapter_content)
            )
            verse_text = chapter_content[v_start:v_end]
            cleaned = clean_text(verse_text)
            if cleaned:
                results.append((book_code, chapter_num, verse_num, cleaned))

    return results


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Connect to SQLite DB with WAL mode and busy timeout."""
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def get_total_verses(conn: sqlite3.Connection) -> int:
    """Get total verse count from bible_verses."""
    return conn.execute("SELECT COUNT(*) FROM bible_verses").fetchone()[0]


def get_column_count(conn: sqlite3.Connection, column: str) -> int:
    """Get count of non-NULL rows for a given column."""
    return conn.execute(
        f"SELECT COUNT(*) FROM bible_verses WHERE {column} IS NOT NULL"
    ).fetchone()[0]


def import_source(
    source_name: str,
    source_cfg: dict,
    conn: sqlite3.Connection,
    dry_run: bool = False,
    verbose: bool = False,
    total_verses: int = 0,
) -> dict:
    """Import a single Bible source. Returns stats dict."""
    source_dir = KAGGLE_ROOT / source_cfg["dir"]
    column = source_cfg["column"]
    description = source_cfg["description"]

    if not source_dir.exists():
        print(f"  ERROR: Source directory not found: {source_dir}")
        return {"source": source_name, "files": 0, "parsed": 0, "updated": 0,
                "missing": 0, "error": "dir not found"}

    usx_files = sorted(source_dir.glob("*.usx"))
    if verbose:
        print(f"  Found {len(usx_files)} USX files in {source_dir}")

    # Parse all USX files
    all_verses: dict[tuple[str, int, int], str] = {}
    for usx_file in usx_files:
        verses = parse_usx_file(usx_file, verbose=verbose)
        for book, ch, v, text in verses:
            all_verses[(book, ch, v)] = text
        if verbose:
            print(f"    {usx_file.name}: {len(verses)} verses")

    if verbose:
        print(f"  Total parsed: {len(all_verses)} verses")

    if dry_run:
        # Show samples
        for (book, ch, v), text in list(all_verses.items())[:3]:
            print(f"    {book} {ch}:{v} → {text[:80]}...")
        return {"source": source_name, "files": len(usx_files),
                "parsed": len(all_verses), "updated": 0, "missing": 0}

    # Update database
    cur = conn.cursor()
    updated = 0
    missing = 0
    missing_samples: list[str] = []

    for (book, ch, v), text in all_verses.items():
        cur.execute(
            f"UPDATE bible_verses SET {column} = ? "
            "WHERE book = ? AND chapter = ? AND verse = ?",
            (text, book, ch, v),
        )
        if cur.rowcount > 0:
            updated += 1
        else:
            missing += 1
            if len(missing_samples) < 5:
                missing_samples.append(f"{book} {ch}:{v}")

    # For Judson, also set myanmar = myanmar_judson
    if column == "myanmar_judson":
        cur.execute(
            "UPDATE bible_verses SET myanmar = myanmar_judson "
            "WHERE myanmar_judson IS NOT NULL"
        )
        if verbose:
            myanmar_set = cur.rowcount
            print(f"  Synced myanmar = myanmar_judson for {myanmar_set} rows")

    filled = get_column_count(conn, column)

    if missing_samples:
        print(f"  Missing samples: {', '.join(missing_samples)}")

    return {
        "source": source_name,
        "description": description,
        "files": len(usx_files),
        "parsed": len(all_verses),
        "updated": updated,
        "missing": missing,
        "filled": filled,
    }


def print_coverage_report(conn: sqlite3.Connection, total: int) -> None:
    """Print a formatted coverage report for all version columns."""
    columns = [
        ("TDB77", "zo_tdb77", "Tedim Bible 1977"),
        ("Tedim 2010", "zo_tedim2010", "Tedim Bible 2010"),
        ("HCL06", "zo_hcl06", "Hakha Chin 2006"),
        ("FCL", "zo_fcl", "Falam Chin 2002"),
        ("KJV", "en_kJV", "English KJV"),
        ("Judson", "myanmar", "Myanmar Judson"),
    ]

    print(f"\n{'='*72}")
    print("=== Bible Version Coverage ===")
    print(f"{'='*72}")
    print(
        f"{'Source':<16}| {'Column':<16}| {'Filled':>7} | {'Total':>7} | "
        f"{'Missing':>7} | {'Coverage':>8}"
    )
    print(f"{'-'*16}|{'-'*17}|{'-'*9}|{'-'*9}|{'-'*9}|{'-'*10}")

    total_filled = 0
    for name, col, desc in columns:
        filled = get_column_count(conn, col)
        missing = total - filled
        pct = (filled / total * 100) if total else 0
        total_filled += filled
        print(
            f"{name:<16}| {col:<16}| {filled:>7} | {total:>7} | "
            f"{missing:>7} | {pct:>6.1f}%"
        )

    print(f"{'-'*16}|{'-'*17}|{'-'*9}|{'-'*9}|{'-'*9}|{'-'*10}")
    all_pct = (total_filled / (total * len(columns)) * 100) if total else 0
    print(
        f"{'TOTAL':<16}| {'ALL':<16}| {total_filled:>7} | {total * len(columns):>7} | "
        f"{total * len(columns) - total_filled:>7} | {all_pct:>6.1f}%"
    )
    print(f"{'='*72}")


def cross_validate(conn: sqlite3.Connection) -> None:
    """Cross-validate: check for verses missing from key columns."""
    print(f"\n{'='*72}")
    print("=== Cross-Validation ===")
    print(f"{'='*72}")

    # Check: no verse has NULL in ALL Zolai columns
    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses "
        "WHERE zo_tdb77 IS NULL AND zo_tedim2010 IS NULL"
    ).fetchone()
    no_zolai = row[0]
    if no_zolai:
        print(f"  WARNING: {no_zolai} verses have NULL in BOTH zo_tdb77 and zo_tedim2010")
    else:
        print(f"  OK: All verses have at least one Zolai column filled")

    # Check: no verse has NULL in en_kJV
    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE en_kJV IS NULL"
    ).fetchone()
    no_kjv = row[0]
    if no_kjv:
        print(f"  WARNING: {no_kjv} verses have NULL en_kJV")
        # Show samples
        samples = conn.execute(
            "SELECT book, chapter, verse FROM bible_verses "
            "WHERE en_kJV IS NULL LIMIT 5"
        ).fetchall()
        if samples:
            print(f"    Samples: {', '.join(f'{b} {c}:{v}' for b, c, v in samples)}")
    else:
        print(f"  OK: All verses have en_kJV")

    # Cross-check: verses in one Zolai version but not the other
    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL AND zo_tedim2010 IS NULL"
    ).fetchone()
    tdb_only = row[0]

    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses "
        "WHERE zo_tdb77 IS NULL AND zo_tedim2010 IS NOT NULL"
    ).fetchone()
    tedim_only = row[0]

    if tdb_only:
        print(f"  INFO: {tdb_only} verses in zo_tdb77 but not zo_tedim2010")
    if tedim_only:
        print(f"  INFO: {tedim_only} verses in zo_tedim2010 but not zo_tdb77")

    # Myanmar coverage
    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar IS NOT NULL"
    ).fetchone()
    myanmar_filled = row[0]
    total = get_total_verses(conn)
    myanmar_pct = (myanmar_filled / total * 100) if total else 0
    print(f"  Myanmar (generic): {myanmar_filled}/{total} ({myanmar_pct:.1f}%)")

    row = conn.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar_judson IS NOT NULL"
    ).fetchone()
    judson_filled = row[0]
    judson_pct = (judson_filled / total * 100) if total else 0
    print(f"  Myanmar (Judson):  {judson_filled}/{total} ({judson_pct:.1f}%)")

    print(f"{'='*72}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import ALL Bible versions from Kaggle USX source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    Import all sources
  %(prog)s --source TDB77           Import only TDB77
  %(prog)s --all --dry-run          Preview without writing
  %(prog)s --all --verbose          Show per-file progress
        """,
    )
    parser.add_argument(
        "--all", action="store_true", default=True,
        help="Import all sources (default)",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Import only one source (e.g., TDB77, KJV, Judson)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse files but don't write to DB",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show per-file progress",
    )
    parser.add_argument(
        "--db", type=Path, default=DB_PATH,
        help=f"Path to zolai.db (default: {DB_PATH})",
    )
    args = parser.parse_args()

    # Determine which sources to import
    if args.source:
        if args.source not in SOURCES:
            print(f"ERROR: Unknown source '{args.source}'. Available: {', '.join(SOURCES.keys())}")
            sys.exit(1)
        sources_to_import = {args.source: SOURCES[args.source]}
    else:
        sources_to_import = SOURCES

    db_path = args.db
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    print(f"Kaggle root: {KAGGLE_ROOT}")
    print(f"Sources to import: {', '.join(sources_to_import.keys())}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Connect to DB
    conn = connect_db(db_path)
    total_verses = get_total_verses(conn)
    print(f"Total verses in DB: {total_verses}")

    # Step 1: Clear garbage from myanmar column
    if not args.dry_run:
        before_myanmar = get_column_count(conn, "myanmar")
        conn.execute("UPDATE bible_verses SET myanmar = NULL WHERE myanmar IS NOT NULL")
        print(f"\nStep 1: Cleared {before_myanmar} rows from myanmar column")

    # Step 2: Import each source
    all_stats = []
    for source_name, source_cfg in sources_to_import.items():
        print(f"\n{'─'*50}")
        print(f"Importing: {source_name} ({source_cfg['description']})")
        print(f"  Column: {source_cfg['column']}")
        print(f"  Source: {KAGGLE_ROOT / source_cfg['dir']}")

        before_count = get_column_count(conn, source_cfg["column"])
        print(f"  Before: {before_count}/{total_verses}")

        stats = import_source(
            source_name, source_cfg, conn,
            dry_run=args.dry_run, verbose=args.verbose,
            total_verses=total_verses,
        )
        all_stats.append(stats)

        if not args.dry_run and "filled" in stats:
            print(f"  After:  {stats['filled']}/{total_verses}")
            print(f"  Updated: {stats['updated']}, Parsed: {stats['parsed']}")

    # Commit
    if not args.dry_run:
        conn.commit()
        print(f"\nAll changes committed.")

    # Step 3: Coverage report
    if not args.dry_run:
        print_coverage_report(conn, total_verses)

    # Step 4: Cross-validate
    if not args.dry_run:
        cross_validate(conn)

    # Step 5: Note about follow-up scripts
    if not args.dry_run:
        print(f"\n{'='*72}")
        print("=== Follow-up Steps ===")
        print(f"{'='*72}")
        print("  NOTE: cross_fill_all.py and validate_and_correct.py do not exist yet.")
        print("  Consider creating them for:")
        print("    - Cross-filling NULL columns from other versions")
        print("    - Grammar/ZVS validation of imported text")
        print(f"{'='*72}")

    conn.close()

    if args.dry_run:
        print("\nDry run complete — no database changes.")


if __name__ == "__main__":
    main()
