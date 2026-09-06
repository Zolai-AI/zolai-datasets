#!/usr/bin/env python3
"""
Extract proverbs, wise sayings, and idiomatic expressions from Bible corpus.
Reads: data/bible/parallel_corpus_v1.jsonl (31,102 verses)
Outputs: data/bible/language_learning/proverbs.jsonl
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CORPUS_FILE = DATA_DIR / "bible" / "parallel_corpus_v1.jsonl"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "proverbs.jsonl"

# Books with proverbial/wisdom content
PROVERBIAL_BOOKS = {"PRO", "ECC", "JOB"}

# Books with significant wisdom/poetic content
WISE_BOOKS = {"PSA", "SNG", "ISA", "JER", "LAM"}

# Multi-word patterns that indicate proverbs/idioms
IDIOM_PATTERNS = [
    r"\bhinahleh\b",       # "like this" — comparative
    r"\btuahleh\b",        # "like that"
    r"\bcihmai\b",         # "isn't it?" — rhetorical
    r"\bbangci\b",         # "what" — interrogative wisdom
    r"\bkua\b",            # "how" — interrogative wisdom
    r"\bmahmah\b",         # "always" — habitual
    r"\bbawlbawlna\b",     # "righteousness"
    r"\bsinzat\b",         # "wisdom"
    r"\bthukna\b",         # "deep/thought"
]


def is_proverbial_structure(zo_text: str) -> bool:
    """Check if text has proverbial/wise saying structure."""
    if not zo_text:
        return False
    # Short, declarative statements often proverbs
    words = zo_text.split()
    if 3 <= len(words) <= 20:
        # Check for wisdom markers
        for pattern in IDIOM_PATTERNS:
            if re.search(pattern, zo_text, re.IGNORECASE):
                return True
        # Check for comparative structures
        if re.search(r"\bhinahleh\b|\btuahleh\b|\bkici\b", zo_text, re.IGNORECASE):
            return True
    return False


def classify_type(zo_text: str, en_text: str, book: str) -> str:
    """Classify the type of wisdom content."""
    if book == "PRO":
        return "proverb"
    if book == "ECC":
        return "ecclesiastes_saying"
    if book == "JOB":
        return "job_wisdom"
    if book == "PSA":
        return "psalm_wisdom"
    if book == "SNG":
        return "song_expression"

    # Check for idiomatic expressions
    if re.search(r"\bhinahleh\b|\btuahleh\b", zo_text or "", re.IGNORECASE):
        return "idiom"
    if re.search(r"\bmahmah\b|\bbawlbawlna\b", zo_text or "", re.IGNORECASE):
        return "wisdom_saying"

    return "wise_saying"


def main():
    print("[extract_proverbs] Starting proverb/idiom extraction...")
    print(f"  Corpus: {CORPUS_FILE}")

    if not CORPUS_FILE.exists():
        print(f"  ERROR: Corpus not found: {CORPUS_FILE}")
        sys.exit(1)

    results = []
    total_verses = 0
    proverbs_by_book = {}

    with open(CORPUS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                verse = json.loads(line)
            except json.JSONDecodeError:
                continue

            total_verses += 1
            book = verse.get("book", "")
            zo = verse.get("zo_tdb77", "") or verse.get("zo_tedim2010", "")
            en = verse.get("en_kJV", "")
            chapter = verse.get("chapter", "")
            verse_num = verse.get("verse", "")
            ref = verse.get("ref", "")

            if not zo:
                continue

            is_proverbial = book in PROVERBIAL_BOOKS
            is_wise = book in WISE_BOOKS
            has_idiom = is_proverbial_structure(zo)

            if is_proverbial or is_wise or has_idiom:
                entry_type = classify_type(zo, en, book)
                entry = {
                    "zo": zo,
                    "en": en,
                    "book": book,
                    "chapter": chapter,
                    "verse": verse_num,
                    "ref": ref,
                    "type": entry_type,
                    "is_proverbial_book": is_proverbial,
                    "has_idiom_pattern": has_idiom,
                }
                results.append(entry)
                proverbs_by_book[book] = proverbs_by_book.get(book, 0) + 1

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for entry in results:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("\n[extract_proverbs] Done!")
    print(f"  Total verses scanned: {total_verses:,}")
    print(f"  Proverbs/sayings found: {len(results):,}")
    print("\n  By book:")
    for book, count in sorted(proverbs_by_book.items(), key=lambda x: -x[1]):
        print(f"    {book}: {count}")
    print(f"\n  Output: {OUTPUT_FILE}")

    # Type distribution
    type_counts = {}
    for entry in results:
        t = entry["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\n  By type:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")

    # Show sample proverbs
    print("\n  Sample proverbs (first 10):")
    for entry in results[:10]:
        print(f"    [{entry['ref']}] {entry['zo'][:80]}...")
        print(f"      → {entry['en'][:80]}...")


if __name__ == "__main__":
    main()
