#!/usr/bin/env python3
"""
Build Tedim-Hakha-Falam-Paite cross-language comparison.
Reads Bible JSONs from linguistics directory.
Extracts parallel verses and finds vocabulary differences.
Outputs: data/bible/language_learning/cross_language.jsonl
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Bible JSON directory
BIBLE_DIR = Path("/home/peter/Documents/Linguistics/Zolai/bible-master/json")

# Version files
VERSIONS = {
    "tedim": {"file": "tedim1932.json", "label": "Tedim 1932"},
    "hakha": {"file": "hakha1920.json", "label": "Hakha 1920"},
    "falam": {"file": "falam1973.json", "label": "Falam 1973"},
    "paite": {"file": "paite1971.json", "label": "Paite 1971"},
}

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "cross_language.jsonl"

# Book number to code mapping (standard Bible order)
BOOK_NUM_TO_CODE = {
    "1": "GEN", "2": "EXO", "3": "LEV", "4": "NUM", "5": "DEU",
    "6": "JOS", "7": "JUG", "8": "RUT", "9": "1SA", "10": "2SA",
    "11": "1KI", "12": "2KI", "13": "1CH", "14": "2CH", "15": "EZR",
    "16": "NEH", "17": "EST", "18": "JOB", "19": "PSA", "20": "PRO",
    "21": "ECC", "22": "SNG", "23": "ISA", "24": "JER", "25": "LAM",
    "26": "EZK", "27": "DAN", "28": "HOS", "29": "JOE", "30": "AMO",
    "31": "OBA", "32": "JON", "33": "MIC", "34": "NAM", "35": "HAB",
    "36": "ZEP", "37": "HAG", "38": "ZEC", "39": "MAL",
    "40": "MAT", "41": "MRK", "42": "LUK", "43": "JHN", "44": "ACT",
    "45": "ROM", "46": "1CO", "47": "2CO", "48": "GAL", "49": "EPH",
    "50": "PHP", "51": "COL", "52": "1TH", "53": "2TH", "54": "1TI",
    "55": "2TI", "56": "TIT", "57": "PHM", "58": "HEB", "59": "JAS",
    "60": "1PE", "61": "2PE", "62": "1JN", "63": "2JN", "64": "3JN",
    "65": "JUD", "66": "REV",
}


def load_bible_json(filepath: Path) -> dict:
    """Load a Bible JSON file and extract verses."""
    if not filepath.exists():
        print(f"  WARNING: File not found: {filepath}")
        return {}

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    verses = {}
    # Structure: data["book"][book_num]["chapter"][ch_num]["verse"][vs_num] = {"text": "..."}
    books = data.get("book", {})

    for book_num, book_data in books.items():
        book_code = BOOK_NUM_TO_CODE.get(str(book_num), f"B{book_num}")
        chapters = book_data.get("chapter", {})
        for ch_num, ch_data in chapters.items():
            vs_dict = ch_data.get("verse", {})
            for vs_num, vs_data in vs_dict.items():
                if isinstance(vs_data, dict) and "text" in vs_data:
                    ref = f"{book_code} {ch_num}:{vs_num}"
                    verses[ref] = {
                        "text": vs_data["text"],
                        "book": book_code,
                        "chapter": ch_num,
                        "verse": vs_num,
                    }

    return verses


def tokenize(text: str) -> list:
    """Tokenize text into words."""
    return re.findall(r"[a-zA-Z\u1000-\u109f\uaa00-\uaaff']+", text.lower())


def find_vocabulary_differences(tedim_words: list, other_words: list) -> list:
    """Find words that differ between Tedim and another version."""
    tedim_set = set(tedim_words)
    other_set = set(other_words)

    # Words in Tedim but not in other
    tedim_only = tedim_set - other_set
    # Words in other but not in Tedim
    other_only = other_set - tedim_set

    return list(tedim_only)[:5], list(other_only)[:5]


def classify_difference(tedim_word: str, other_word: str, category_hint: str = "") -> str:
    """Classify the type of vocabulary difference."""
    if category_hint:
        return category_hint

    # Check for shared roots
    if tedim_word[:3] == other_word[:3]:
        return "morphological_variant"

    # Check for cognates (similar length, some shared chars)
    if abs(len(tedim_word) - len(other_word)) <= 2:
        shared = set(tedim_word) & set(other_word)
        if len(shared) >= 2:
            return "cognate"

    return "different_word"


def main():
    print("[build_cross_language] Starting cross-language comparison...")
    print(f"  Bible directory: {BIBLE_DIR}")

    if not BIBLE_DIR.exists():
        print(f"  ERROR: Bible directory not found: {BIBLE_DIR}")
        sys.exit(1)

    # Load all versions
    all_verses = {}
    for version_key, version_info in VERSIONS.items():
        filepath = BIBLE_DIR / version_info["file"]
        print(f"\n  Loading {version_info['label']}...")
        verses = load_bible_json(filepath)
        print(f"    Loaded {len(verses):,} verses")
        all_verses[version_key] = verses

    # Find common references
    tedim_refs = set(all_verses.get("tedim", {}).keys())
    common_refs = tedim_refs.copy()
    for version_key in ["hakha", "falam", "paite"]:
        common_refs &= set(all_verses.get(version_key, {}).keys())

    print(f"\n  Common references across all 4 versions: {len(common_refs):,}")

    # Build comparison entries
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    comparison_count = 0
    differences_by_category = defaultdict(int)
    sample_comparisons = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for ref in sorted(common_refs):
            tedim_data = all_verses["tedim"].get(ref, {})
            tedim_text = tedim_data.get("text", "")

            # Skip very short verses (names, numbers)
            tedim_words = tokenize(tedim_text)
            if len(tedim_words) < 3:
                continue

            # Compare with each other version
            for other_key in ["hakha", "falam", "paite"]:
                other_data = all_verses[other_key].get(ref, {})
                other_text = other_data.get("text", "")

                other_words = tokenize(other_text)
                if not other_words:
                    continue

                # Find differences
                tedim_only, other_only = find_vocabulary_differences(
                    tedim_words, other_words
                )

                if not tedim_only and not other_only:
                    continue  # Same vocabulary

                # Classify differences
                category = classify_difference(
                    tedim_only[0] if tedim_only else "",
                    other_only[0] if other_only else "",
                )

                entry = {
                    "concept": tedim_text[:100],
                    "tedim": tedim_text,
                    "hakha": all_verses["hakha"].get(ref, {}).get("text", ""),
                    "falam": all_verses["falam"].get(ref, {}).get("text", ""),
                    "paite": all_verses["paite"].get(ref, {}).get("text", ""),
                    "ref": ref,
                    "book": tedim_data.get("book", ""),
                    "category": category,
                    "compared_with": other_key,
                    "tedim_unique": tedim_only[:3],
                    "other_unique": other_only[:3],
                }

                out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                comparison_count += 1
                differences_by_category[category] += 1

                if len(sample_comparisons) < 5:
                    sample_comparisons.append(entry)

    print("\n[build_cross_language] Done!")
    print(f"  Total comparison entries: {comparison_count:,}")
    print("\n  By category:")
    for cat, count in sorted(differences_by_category.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count:,}")
    print(f"\n  Output: {OUTPUT_FILE}")

    # Show samples
    if sample_comparisons:
        print("\n  Sample comparisons:")
        for entry in sample_comparisons[:3]:
            print(f"    [{entry['ref']}] ({entry['compared_with']})")
            print(f"      Tedim:  {entry['tedim'][:80]}...")
            print(f"      Unique: {entry['tedim_unique']}")
            print(f"      Other:  {entry['other_unique']}")


if __name__ == "__main__":
    main()
