#!/usr/bin/env python3
"""Build unified Myanmar dictionary from all sources.

Merges 5 data sources into a single dict_myanmar_master_v1.jsonl file:
  1. Dalsuum ZO→MY (verified Zolai headwords)
  2. Trilingual ZO→MY→EN (adds English bridge)
  3. EN→MY parallel (sentence-level pairs)
  4. EN→MY news clean (sentence-level)
  5. Burmese monolingual dictionary (definitions only)

Also builds a Myanmar→English index for reverse lookup.

Usage:
    python build_unified_myanmar.py
    python build_unified_myanmar.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[3]  # zolai-ai root
DATA = WORKSPACE / "data"
OUTPUT_DIR = DATA / "processed" / "my"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file, skip errors."""
    items: list[dict[str, Any]] = []
    if not path.exists():
        print(f"  WARN: {path} not found, skipping")
        return items
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                items.append(json.loads(line.strip()))
            except (json.JSONDecodeError, ValueError):
                continue
    return items


def build_unified(dry_run: bool = False) -> None:
    """Merge all Myanmar sources into unified dictionary."""
    unified: dict[str, dict[str, Any]] = {}  # myanmar headword → best entry
    dual_index: dict[str, dict[str, Any]] = {}  # english word → {myanmar, zolai}

    # Source 1: Dalsuum ZO→MY (highest quality — verified Zolai headwords)
    print("Loading dalsuum ZO→MY...")
    zo_my_path = DATA / "processed" / "my" / "dict_zo_my_v1.jsonl"
    zo_my = load_jsonl(zo_my_path)
    for entry in zo_my:
        my = entry.get("myanmar", "").strip()
        if my and my not in unified:
            unified[my] = {
                "myanmar": my,
                "zolai": entry.get("zolai", ""),
                "english": "",
                "pos": "",
                "source": "dalsuum",
                "quality": "verified",
                "domain": "dictionary",
            }
    print(f"  After dalsuum: {len(unified)} entries")

    # Source 2: Trilingual ZO→MY→EN (adds English bridge)
    print("Loading trilingual...")
    tri_path = DATA / "processed" / "my" / "dict_trilingual_v1.jsonl"
    tri = load_jsonl(tri_path)
    for entry in tri:
        my = entry.get("myanmar", "").strip()
        if my:
            if my in unified:
                # Enrich with English
                en = entry.get("english", "").strip()
                if en and not unified[my].get("english"):
                    unified[my]["english"] = en
            else:
                unified[my] = {
                    "myanmar": my,
                    "zolai": entry.get("zolai", ""),
                    "english": entry.get("english", "").strip(),
                    "pos": "",
                    "source": "dalsuum_trilingual",
                    "quality": "verified",
                    "domain": "dictionary",
                }
    print(f"  After trilingual: {len(unified)} entries")

    # Source 3: EN→MY parallel (sentence-level pairs)
    # NOTE: This dataset has en/my fields SWAPPED —
    #   "en" field contains Myanmar text, "my" field contains English text.
    print("Loading EN→MY parallel...")
    parallel_path = DATA / "raw" / "my" / "en_my_parallel.jsonl"
    parallel = load_jsonl(parallel_path)
    parallel_myanmar = 0
    parallel_swapped = 0
    for entry in parallel:
        en_field = entry.get("en", "").strip()
        my_field = entry.get("my", "").strip()

        if not en_field or not my_field:
            continue

        # Detect field swap: if "en" has Myanmar chars, fields are swapped
        en_is_myanmar = any(
            0x1000 <= ord(c) <= 0x109F for c in en_field[:20]
        )

        if en_is_myanmar:
            # Fields are swapped: en=Myanmar, my=English
            my_text = en_field
            en_text = my_field
            parallel_swapped += 1
        else:
            # Normal: en=English, my=Myanmar
            my_text = my_field
            en_text = en_field

        if my_text not in unified:
            unified[my_text] = {
                "myanmar": my_text,
                "zolai": "",
                "english": en_text,
                "pos": "",
                "source": "parallel_en_my",
                "quality": "parallel",
                "domain": "sentence",
            }
            parallel_myanmar += 1
    print(f"  After parallel: {len(unified)} entries "
          f"({parallel_myanmar} new, {parallel_swapped} swapped)")

    # Source 4: EN→MY news clean (sentence-level, correct field order)
    print("Loading EN→MY news...")
    news_path = DATA / "raw" / "my" / "en_my_news_clean.jsonl"
    news = load_jsonl(news_path)
    news_count = 0
    for entry in news:
        my = entry.get("my", "").strip()
        en = entry.get("en", "").strip()
        if my and en and my not in unified:
            unified[my] = {
                "myanmar": my,
                "zolai": "",
                "english": en,
                "pos": "",
                "source": "news_en_my",
                "quality": "news",
                "domain": "news",
            }
            news_count += 1
    print(f"  After news: {len(unified)} entries ({news_count} new)")

    # Source 5: Burmese monolingual dictionary (definitions only)
    print("Loading Burmese dictionary...")
    burmese_path = DATA / "raw" / "my" / "my_dictionary.jsonl"
    burmese = load_jsonl(burmese_path)
    burmese_count = 0
    for entry in burmese:
        word = entry.get("word", "").strip()
        meaning = entry.get("meaning", "").strip()
        pos = entry.get("pos", "").strip()
        if word and word not in unified:
            unified[word] = {
                "myanmar": word,
                "zolai": "",
                "english": "",
                "pos": pos,
                "source": "burmese_dict",
                "quality": "monolingual",
                "domain": "definition",
                "definition_my": meaning,
            }
            burmese_count += 1
    print(f"  After monolingual: {len(unified)} entries ({burmese_count} new)")

    if dry_run:
        print("\n[DRY RUN — no files written]")
        return

    # Write unified dictionary (MY→everything)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "dict_myanmar_master_v1.jsonl"
    with open(output, "w", encoding="utf-8") as f:
        for my, entry in sorted(unified.items()):
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    count = sum(1 for _ in open(output))
    print(f"\nUnified dictionary: {count} entries")
    print(f"Output: {output}")

    # Build reverse index (English → Myanmar) for top entries
    for entry in unified.values():
        en = entry.get("english", "").strip()
        if en and en.lower() not in dual_index:
            dual_index[en.lower()] = {
                "english": en,
                "myanmar": entry["myanmar"],
                "zolai": entry.get("zolai", ""),
                "source": entry["source"],
            }

    reverse_output = OUTPUT_DIR / "dict_en_my_index_v1.jsonl"
    with open(reverse_output, "w", encoding="utf-8") as f:
        for en, entry in sorted(dual_index.items()):
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    rev_count = sum(1 for _ in open(reverse_output))
    print(f"Reverse index: {rev_count} entries")
    print(f"Output: {reverse_output}")

    # Stats
    sources: dict[str, int] = {}
    qualities: dict[str, int] = {}
    domains: dict[str, int] = {}
    for entry in unified.values():
        s = entry["source"]
        q = entry["quality"]
        d = entry.get("domain", "")
        sources[s] = sources.get(s, 0) + 1
        qualities[q] = qualities.get(q, 0) + 1
        domains[d] = domains.get(d, 0) + 1

    print("\nBy source:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    print("\nBy quality:")
    for q, c in sorted(qualities.items(), key=lambda x: -x[1]):
        print(f"  {q}: {c}")

    print("\nBy domain:")
    for d, c in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {d}: {c}")

    with_en = sum(1 for e in unified.values() if e.get("english"))
    with_zo = sum(1 for e in unified.values() if e.get("zolai"))
    print(f"\nWith English: {with_en}")
    print(f"With Zolai: {with_zo}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build unified Myanmar dictionary from all sources",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing files",
    )
    args = parser.parse_args()

    build_unified(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
