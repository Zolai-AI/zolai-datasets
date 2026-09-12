"""Extract Myanmar (Burmese) data from Dalsuum Zolai Dictionary.

Reads data/online/dalsuum-zolai-dictionary/words.json and extracts
senses containing Myanmar Unicode script (\u1000-\u109F).

Output:
    data/processed/my/dict_zo_my_dalsuum.jsonl  — ZO→MY entries
    data/processed/my/myanmar_source_report.json — extraction stats

Usage:
    python extract_myanmar.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

MYANMAR_PATTERN = re.compile(r"[\u1000-\u109F]")
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parents[2]  # zolai-ai root
DALSUUM_PATH = (
    WORKSPACE / "data" / "online" / "dalsuum-zolai-dictionary" / "words.json"
)
OUTPUT_DIR = WORKSPACE / "data" / "processed" / "my"
OUTPUT_JSONL = OUTPUT_DIR / "dict_zo_my_dalsuum.jsonl"
OUTPUT_REPORT = OUTPUT_DIR / "myanmar_source_report.json"

# Synset mapping from dalsuum words.json
SYNSET_MAP = {
    0: "n", 1: "v", 2: "adj", 3: "adv", 4: "prep",
    5: "conj", 6: "pron", 7: "int", 19: "tn",
}


def extract_myanmar_senses(
    data: dict,
) -> list[dict]:
    """Extract senses containing Myanmar Unicode from the dalsuum dictionary."""
    results: list[dict] = []
    for sense in data.get("senses", []):
        sense_text = sense.get("sense", "")
        if MYANMAR_PATTERN.search(sense_text):
            # Extract Myanmar text (strip whitespace)
            myanmar_text = sense_text.strip()
            headword = sense.get("word", "")
            pos_code = sense.get("wrte", -1)
            pos = SYNSET_MAP.get(pos_code, "")
            results.append({
                "zolai": headword,
                "myanmar": myanmar_text,
                "source": "dalsuum",
                "pos": pos,
            })
    return results


def build_report(
    entries: list[dict],
    total_senses: int,
) -> dict:
    """Build extraction statistics report."""
    pos_counts: Counter[str] = Counter(e["pos"] for e in entries)
    headword_counts: Counter[str] = Counter(e["zolai"] for e in entries)
    multi_sense = sum(1 for _, c in headword_counts.items() if c > 1)
    return {
        "source": str(DALSUUM_PATH),
        "total_senses_in_source": total_senses,
        "myanmar_senses_extracted": len(entries),
        "unique_headwords": len(headword_counts),
        "headwords_with_multiple_senses": multi_sense,
        "pos_distribution": dict(pos_counts.most_common()),
        "top_headwords": dict(headword_counts.most_common(20)),
    }


def main() -> int:
    """Main extraction entry point."""
    if not DALSUUM_PATH.exists():
        print(f"ERROR: Source file not found: {DALSUUM_PATH}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {DALSUUM_PATH} ...")
    with open(DALSUUM_PATH, encoding="utf-8") as f:
        data = json.load(f)

    total_senses = len(data.get("senses", []))
    print(f"  Total senses in source: {total_senses}")

    entries = extract_myanmar_senses(data)
    print(f"  Myanmar senses extracted: {len(entries)}")

    # Write JSONL
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Written: {OUTPUT_JSONL}")

    # Write report
    report = build_report(entries, total_senses)
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  Written: {OUTPUT_REPORT}")

    print(f"\nSummary:")
    print(f"  Unique headwords with MY: {report['unique_headwords']}")
    print(f"  Total MY senses: {report['myanmar_senses_extracted']}")
    print(f"  POS distribution: {report['pos_distribution']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
