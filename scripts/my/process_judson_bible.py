"""Process the Judson 1835 Burmese Bible — fix language field.

Reads data/corpus/reference/bible_judson_1835_en.jsonl (30,770 lines)
where each verse has language: "zolai" but the text is actually Burmese.
Fixes language field to "my" and outputs cleaned version.

Output:
    data/processed/my/bible_judson_v1.jsonl — corrected language field
    Data printed: total verses, books, chapters

Usage:
    python process_judson_bible.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parents[2]  # zolai-ai root
INPUT_PATH = (
    WORKSPACE / "data" / "corpus" / "reference" / "bible_judson_1835_en.jsonl"
)
OUTPUT_DIR = WORKSPACE / "data" / "processed" / "my"
OUTPUT_JSONL = OUTPUT_DIR / "bible_judson_v1.jsonl"


def main() -> int:
    """Main entry point."""
    if not INPUT_PATH.exists():
        print(f"ERROR: Source file not found: {INPUT_PATH}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {INPUT_PATH} ...")
    verses: list[dict] = []
    books: set[str] = set()
    chapters: set[str] = set()

    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            verse = json.loads(line)
            # Fix language field
            verse["language"] = "my"
            verses.append(verse)
            books.add(verse.get("book", ""))
            chapters.add(f"{verse.get('book', '')}.{verse.get('chapter', 0)}")

    print(f"  Total verses: {len(verses)}")
    print(f"  Unique books: {len(books)}")
    print(f"  Unique chapters: {len(chapters)}")

    # Write output
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for verse in verses:
            f.write(json.dumps(verse, ensure_ascii=False) + "\n")
    print(f"  Written: {OUTPUT_JSONL}")

    # Print summary
    book_counts = Counter(v.get("book", "") for v in verses)
    print("\nBook distribution (top 10):")
    for book, count in book_counts.most_common(10):
        print(f"  {book}: {count} verses")

    return 0


if __name__ == "__main__":
    sys.exit(main())
