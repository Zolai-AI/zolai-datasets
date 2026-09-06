#!/usr/bin/env python3
"""
Phase 1: Parallel Corpus Parser.

Reads all 66 markdown files from the Tedim_Chin parallel corpus,
parses TDB77, Tedim2010, KJV lines from each verse, and outputs
a unified JSONL file.

Usage:
    python3 scripts/bible/build_parallel_corpus.py

Input:
    ../data/corpus/bible/markdown/Parallel_Corpus/Tedim_Chin/*.md

Output:
    ../data/bible/parallel_corpus_v1.jsonl
"""

import json
import re
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = WORKSPACE / "data" / "corpus" / "bible" / "markdown" / "Parallel_Corpus" / "Tedim_Chin"
OUTPUT_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"

# Book code → full name mapping (66 books)
BOOK_NAMES = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers",
    "DEU": "Deuteronomy", "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles", "EZR": "Ezra", "NEH": "Nehemiah",
    "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
    "ECC": "Ecclesiastes", "SNG": "Song of Solomon", "ISA": "Isaiah",
    "JER": "Jeremiah", "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel",
    "HOS": "Hosea", "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah",
    "JON": "Jonah", "MIC": "Micah", "NAM": "Nahum", "HAB": "Habakkuk",
    "ZEP": "Zephaniah", "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi",
    "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John",
    "ACT": "Acts", "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
    "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians",
    "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy",
    "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon", "HEB": "Hebrews",
    "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John",
    "2JN": "2 John", "3JN": "3 John", "JUD": "Jude", "REV": "Revelation",
}


def extract_book_code(filename: str) -> str:
    """Extract book code from filename like GEN_Tedim_Chin_Parallel.md."""
    return filename.split("_")[0]


def parse_book(filepath: Path, book_code: str) -> list[dict]:
    """Parse a single parallel corpus markdown file into verse records."""
    ref_pat = re.compile(r"\*\*(\d+):(\d+)\*\*")
    zo_pat = re.compile(r"^(?:TDB77|Tedim2010):\s*(.+)", re.IGNORECASE)
    en_pat = re.compile(r"^KJV:\s*(.+)", re.IGNORECASE)

    verses = []
    chapter = ""
    verse = ""
    tdb77 = ""
    tedim2010 = ""
    kjv = ""

    with open(filepath, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Detect chapter headers: ## Chapter N
            ch_match = re.match(r"^##\s+Chapter\s+(\d+)", line)
            if ch_match:
                chapter = ch_match.group(1)
                continue

            # Detect verse references: **C:V**
            ref_match = ref_pat.match(line)
            if ref_match:
                # Yield previous verse if complete
                if chapter and verse:
                    verses.append({
                        "book": book_code,
                        "book_name": BOOK_NAMES.get(book_code, book_code),
                        "chapter": chapter,
                        "verse": verse,
                        "ref": f"{book_code} {chapter}:{verse}",
                        "zo_tdb77": tdb77.strip() if tdb77 else None,
                        "zo_tedim2010": tedim2010.strip() if tedim2010 else None,
                        "en_kJV": kjv.strip() if kjv else None,
                    })
                chapter = ref_match.group(1)
                verse = ref_match.group(2)
                tdb77 = ""
                tedim2010 = ""
                kjv = ""
                continue

            # Detect TDB77 line
            m = zo_pat.match(line)
            if m:
                text = m.group(1).strip()
                if "TDB77" in line and not tdb77:
                    tdb77 = "" if text == "[Missing]" else text
                elif "Tedim2010" in line and not tedim2010:
                    tedim2010 = "" if text == "[Missing]" else text
                continue

            # Detect KJV line
            m = en_pat.match(line)
            if m and not kjv:
                text = m.group(1).strip()
                kjv = "" if text == "[Missing]" else text
                continue

    # Yield last verse in file
    if chapter and verse:
        verses.append({
            "book": book_code,
            "book_name": BOOK_NAMES.get(book_code, book_code),
            "chapter": chapter,
            "verse": verse,
            "ref": f"{book_code} {chapter}:{verse}",
            "zo_tdb77": tdb77.strip() if tdb77 else None,
            "zo_tedim2010": tedim2010.strip() if tedim2010 else None,
            "en_kJV": kjv.strip() if kjv else None,
        })

    return verses


def build_corpus():
    """Build the parallel corpus from all markdown files."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    md_files = sorted(INPUT_DIR.glob("*.md"))
    if not md_files:
        print(f"ERROR: No markdown files found in {INPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    total_verses = 0
    total_complete = 0
    total_partial = 0
    books_found = set()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        for md_file in md_files:
            book_code = extract_book_code(md_file.name)
            books_found.add(book_code)
            verses = parse_book(md_file, book_code)
            for v in verses:
                out.write(json.dumps(v, ensure_ascii=False) + "\n")
                total_verses += 1
                has_zo = bool(v["zo_tdb77"] or v["zo_tedim2010"])
                has_en = bool(v["en_kJV"])
                if has_zo and has_en:
                    total_complete += 1
                elif has_zo or has_en:
                    total_partial += 1

    print(f"✅ Parallel corpus built: {OUTPUT_PATH.name}")
    print(f"   Books: {len(books_found)}/66")
    print(f"   Verses: {total_verses:,}")
    print(f"   Complete (ZO+EN): {total_complete:,}")
    print(f"   Partial (ZO or EN only): {total_partial:,}")
    print(f"   Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_corpus()
