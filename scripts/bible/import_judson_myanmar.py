#!/usr/bin/env python3
"""Parse USX Bible files and import Myanmar Judson translations into bible_verses.

Reads .usx files from the Judson Bible Burmese USX directory, extracts Myanmar
text for each verse, and updates both the `myanmar` and `myanmar_judson` columns.

Usage:
    python import_judson_myanmar.py [--source DIR] [--db PATH]
"""

import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"
DEFAULT_SOURCE = Path("/home/peter/Downloads/Kaggle/Chin-Bible/Judson Bible Burmese/USX_1")

# Zero-width characters to strip
ZW_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
# Any remaining XML/HTML tags
TAG_PATTERN = re.compile(r"<[^>]+>")
# Multiple whitespace → single space
WS_PATTERN = re.compile(r"[ \t\u00a0]+")
# Leading/trailing whitespace on lines
STRIP_LINE = re.compile(r"^\s+|\s+$", re.MULTILINE)


def clean_text(text: str) -> str:
    """Clean extracted Myanmar text: remove XML tags, ZW chars, normalize whitespace."""
    text = ZW_PATTERN.sub("", text)
    text = TAG_PATTERN.sub("", text)
    text = WS_PATTERN.sub(" ", text)
    text = STRIP_LINE.sub("", text)
    return text.strip()


def parse_usx_file(filepath: Path) -> list[tuple[str, int, int, str]]:
    """Parse a single USX file, returning list of (book, chapter, verse, myanmar_text).

    The USX format uses:
      <chapter number="X" style="c" />
      <verse number="X" style="v" />Myanmar text here...

    Verses may span multiple <para> elements; we accumulate text across paragraphs
    within the same chapter until the next verse marker.
    """
    content = filepath.read_text(encoding="utf-8")

    # Extract book code from <book code="GEN" style="id">
    book_match = re.search(r'<book\s+code="([A-Z0-9]+)"', content)
    if not book_match:
        print(f"  WARNING: No book code found in {filepath.name}")
        return []
    book_code = book_match.group(1)

    results = []
    current_chapter = 0
    current_verse = 0
    current_text_parts: list[str] = []

    # Process line by line for better paragraph tracking
    # But first, normalize the content to handle multi-line tags
    content = re.sub(r"\n\s*", " ", content)

    # Split on chapter markers to handle chapters
    # Find all chapter markers
    chapter_positions = list(re.finditer(r'<chapter\s+number="(\d+)"\s+style="c"\s*/>', content))

    for ch_idx, ch_match in enumerate(chapter_positions):
        current_chapter = int(ch_match.group(1))
        ch_start = ch_match.end()
        ch_end = chapter_positions[ch_idx + 1].start() if ch_idx + 1 < len(chapter_positions) else len(content)
        chapter_content = content[ch_start:ch_end]

        # Find all verse markers in this chapter
        verse_positions = list(re.finditer(r'<verse\s+number="(\d+)"\s+style="v"\s*/>', chapter_content))

        for v_idx, v_match in enumerate(verse_positions):
            verse_num = int(v_match.group(1))
            v_start = v_match.end()
            v_end = verse_positions[v_idx + 1].start() if v_idx + 1 < len(verse_positions) else len(chapter_content)
            verse_text = chapter_content[v_start:v_end]

            cleaned = clean_text(verse_text)
            if cleaned:
                results.append((book_code, current_chapter, verse_num, cleaned))

    return results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Import Judson Myanmar Bible translations")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="Directory containing USX files")
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="Path to zolai.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse files but don't write to DB")
    args = parser.parse_args()

    source_dir = args.source
    db_path = args.db

    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)

    usx_files = sorted(source_dir.glob("*.usx"))
    print(f"Found {len(usx_files)} USX files in {source_dir}")

    # ── Step 1: Parse all USX files ──────────────────────────────────────
    all_verses: dict[tuple[str, int, int], str] = {}  # (book, ch, v) → text
    for usx_file in usx_files:
        verses = parse_usx_file(usx_file)
        for book, ch, v, text in verses:
            all_verses[(book, ch, v)] = text
        print(f"  {usx_file.name}: {len(verses)} verses")

    print(f"\nTotal parsed verses: {len(all_verses)}")

    if args.dry_run:
        # Show a sample
        for (book, ch, v), text in list(all_verses.items())[:5]:
            print(f"  {book} {ch}:{v} → {text[:80]}...")
        print("\nDry run — no database changes.")
        return

    # ── Step 2: Connect to DB and clear existing Myanmar data ─────────────
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    cur = conn.cursor()

    # Clear ALL existing Myanmar data
    before_myanmar = cur.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar IS NOT NULL"
    ).fetchone()[0]
    before_judson = cur.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar_judson IS NOT NULL"
    ).fetchone()[0]

    cur.execute("UPDATE bible_verses SET myanmar = NULL")
    cur.execute("UPDATE bible_verses SET myanmar_judson = NULL")
    print(f"\nCleared existing data: {before_myanmar} myanmar, {before_judson} myanmar_judson")

    # ── Step 3: Update database ──────────────────────────────────────────
    total_verses = cur.execute("SELECT COUNT(*) FROM bible_verses").fetchone()[0]
    updated = 0
    missing = 0
    missing_samples: list[str] = []

    for (book, ch, v), text in all_verses.items():
        cur.execute(
            "UPDATE bible_verses SET myanmar = ?, myanmar_judson = ? "
            "WHERE book = ? AND chapter = ? AND verse = ?",
            (text, text, book, ch, v),
        )
        if cur.rowcount > 0:
            updated += 1
        else:
            missing += 1
            if len(missing_samples) < 10:
                missing_samples.append(f"{book} {ch}:{v}")

    conn.commit()

    # ── Step 4: Report ───────────────────────────────────────────────────
    total_with_myanmar = cur.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar IS NOT NULL"
    ).fetchone()[0]
    total_with_judson = cur.execute(
        "SELECT COUNT(*) FROM bible_verses WHERE myanmar_judson IS NOT NULL"
    ).fetchone()[0]
    pct = (total_with_myanmar / total_verses * 100) if total_verses else 0

    print(f"\n{'='*50}")
    print(f"=== Judson Myanmar Import ===")
    print(f"Files processed:   {len(usx_files)}")
    print(f"Verses parsed:     {len(all_verses)}")
    print(f"Verses updated:    {updated}")
    print(f"Missing (no match): {missing}")
    if missing_samples:
        print(f"Missing samples:   {', '.join(missing_samples)}")
    print(f"Total with Myanmar: {total_with_myanmar}/{total_verses} ({pct:.1f}%)")
    print(f"Total with Judson:  {total_with_judson}/{total_verses} ({pct:.1f}%)")
    print(f"{'='*50}")

    # ── Step 5: Verify sample ────────────────────────────────────────────
    print("\nSample verification:")
    for book, ch, v in [("GEN", 1, 1), ("GEN", 1, 31), ("MAT", 1, 1), ("REV", 22, 21)]:
        row = cur.execute(
            "SELECT myanmar, myanmar_judson FROM bible_verses "
            "WHERE book = ? AND chapter = ? AND verse = ?",
            (book, ch, v),
        ).fetchone()
        if row:
            my, jd = row
            match = "✓" if my == jd else "✗ DIFFER"
            print(f"  {book} {ch}:{v} myanmar={my[:50] if my else 'NULL'}... {match}")
        else:
            print(f"  {book} {ch}:{v} NOT IN DB")

    conn.close()


if __name__ == "__main__":
    main()
