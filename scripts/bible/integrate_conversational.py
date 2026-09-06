#!/usr/bin/env python3
"""
Integrate conversational Zolai data from multiple sources.
Reads: paumkim/zomi-dataset data files (conversational, youtube, google groups, hauhna)
Outputs: data/bible/language_learning/conversational.jsonl
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# Input files with metadata
INPUT_FILES = [
    {
        "path": DATA_DIR / "online" / "zomi-dataset" / "data" / "conversational_zomi.txt",
        "source": "paumkim_conversational",
        "register": "conversational",
    },
    {
        "path": DATA_DIR / "online" / "zomi-dataset" / "data" / "youtube_casual_zomi.txt",
        "source": "youtube_casual",
        "register": "casual",
    },
    {
        "path": DATA_DIR / "online" / "zomi-dataset" / "data" / "google_groups_norm.txt",
        "source": "google_groups",
        "register": "forum",
    },
    {
        "path": DATA_DIR / "online" / "zomi-dataset" / "data" / "hauhna_leh_khansauna.txt",
        "source": "hauhna_khansauna",
        "register": "educational",
    },
]

OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "conversational.jsonl"

# Lines to skip (non-Zolai content)
SKIP_PATTERNS = [
    r"^[\x00-\x1f]",  # Control characters
    r"^\s*$",  # Empty
    r"^[=\-\*]{3,}",  # Separator lines
    r"^function\s*\{",  # JavaScript
    r"^var\s+\w+\s*=",  # JavaScript variables
    r"^if\s*\(",  # Code
    r"return\s+",  # Code
    r"^http",  # URLs
    r"^\d+\.\s+[A-Z]",  # Numbered English paragraphs
]

# Minimum Zolai word count to keep
MIN_ZO_WORDS = 3


def is_zolai_line(line: str) -> bool:
    """Check if line contains Zolai text (not pure English/code)."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, line):
            return False

    # Check for Zolai characters or common words
    zo_chars = len(re.findall(r"[\u1000-\u109f]", line))
    zo_words = len(re.findall(
        r"\b(?:hi|in|a|leh|ci|ta|tu|na|khi|ka|pi|si|hih|hu|hoi|hou|hong|hei|hei|ciang|tua|tuate|te|pen|ate|au|amu|amau)\b",
        line, re.IGNORECASE
    ))

    # Keep if has Zolai chars or multiple Zolai function words
    return zo_chars > 0 or zo_words >= 2


def parse_conversational_file(filepath: Path, source: str, register: str) -> list:
    """Parse a conversational file into sentence entries."""
    entries = []
    if not filepath.exists():
        print(f"  WARNING: File not found: {filepath}")
        return entries

    line_count = 0
    kept_count = 0

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            line_count += 1
            if not line:
                continue

            if not is_zolai_line(line):
                continue

            # Count Zolai words
            words = re.findall(r"[a-zA-Z\u1000-\u109f\uaa00-\uaaff']+", line)
            if len(words) < MIN_ZO_WORDS:
                continue

            # Detect context clues
            context = detect_context(line)

            entry = {
                "zo": line,
                "en": "",  # No English translation in conversational data
                "context": context,
                "source": source,
                "register": register,
                "word_count": len(words),
            }
            entries.append(entry)
            kept_count += 1

    print(f"    {filepath.name}: {line_count:,} lines → {kept_count:,} entries")
    return entries


def detect_context(line: str) -> str:
    """Detect the conversational context from the line."""
    lower = line.lower()

    # Greeting patterns
    if re.search(r"\b(khupi|khopai|chibai|vanawm|cingklang)\b", lower):
        return "greeting"

    # Question patterns
    if re.search(r"\b(hiam|bang\s*ci|kua|mahti)\b", lower):
        return "question"

    # Exclamation
    if re.search(r"\b(ei|ae|mah|hmm|wow)\b", lower):
        return "exclamation"

    # Request/command
    if re.search(r"\b(kei|nang|please|hong|hei)\b", lower):
        return "request"

    # Statement about self
    if re.search(r"\b(ka\s|kei\s)", lower):
        return "self_statement"

    return "statement"


def main():
    print("[integrate_conversational] Starting conversational data integration...")
    print(f"  Input files: {len(INPUT_FILES)}")

    all_entries = []
    source_counts = {}

    for file_info in INPUT_FILES:
        filepath = file_info["path"]
        source = file_info["source"]
        register = file_info["register"]
        print(f"\n  Processing: {source} ({register})...")

        entries = parse_conversational_file(filepath, source, register)
        all_entries.extend(entries)
        source_counts[source] = len(entries)

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.writelines(json.dumps(entry, ensure_ascii=False) + "\n" for entry in all_entries)

    print("\n[integrate_conversational] Done!")
    print(f"  Total entries: {len(all_entries):,}")
    print("\n  By source:")
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {source}: {count:,}")
    print(f"\n  Output: {OUTPUT_FILE}")

    # Register distribution
    reg_counts = {}
    for entry in all_entries:
        r = entry["register"]
        reg_counts[r] = reg_counts.get(r, 0) + 1
    print("\n  By register:")
    for r, c in sorted(reg_counts.items(), key=lambda x: -x[1]):
        print(f"    {r}: {c:,}")

    # Context distribution
    ctx_counts = {}
    for entry in all_entries:
        ctx = entry["context"]
        ctx_counts[ctx] = ctx_counts.get(ctx, 0) + 1
    print("\n  By context:")
    for ctx, c in sorted(ctx_counts.items(), key=lambda x: -x[1]):
        print(f"    {ctx}: {c:,}")

    # Show samples
    print("\n  Sample entries:")
    for entry in all_entries[:5]:
        print(f"    [{entry['register']}] {entry['zo'][:80]}...")
        print(f"      context={entry['context']}, words={entry['word_count']}")


if __name__ == "__main__":
    main()
