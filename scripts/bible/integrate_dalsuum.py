#!/usr/bin/env python3
"""
Integrate Dalsuum Zolai-English-Myanmar Dictionary
Reads data/online/dalsuum-zolai-dictionary/words.json (7,861 headwords)
Cross-checks against existing dict_zo_en_clean.jsonl (93K entries)
Outputs: data/dictionary/processed/dict_dalsuum_merged.jsonl
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
INPUT_FILE = DATA_DIR / "online" / "dalsuum-zolai-dictionary" / "words.json"
EXISTING_DICT = DATA_DIR / "dictionary" / "processed" / "dict_zo_en_clean.jsonl"
OUTPUT_FILE = DATA_DIR / "dictionary" / "processed" / "dict_dalsuum_merged.jsonl"

# ZVS 2018 forbidden form mappings
ZVS_MAP = {
    "pathian": "pasian",
    "ram": "gam",
    "fapa": "tapa",
    "bawipa": "topa",
    "siangpahrang": "kumpipa",
    "cu": "tua",
    "cun": "tua",
    "suah": "chuak",
    "zalenna": "suahtakna",
    "nunnak": "nuntakna",
}

# Synset ID → POS mapping (from dalsuum data)
SYNSET_POS = {
    0: "n", 1: "v", 2: "adj", 3: "adv", 4: "pron", 5: "prep",
    6: "conj", 7: "det", 8: "other",
}


def zvs_normalize(word: str) -> str:
    """Apply ZVS 2018 normalization to a word."""
    low = word.strip().lower()
    return ZVS_MAP.get(low, low)


def load_existing_zo_en(path: Path) -> dict:
    """Load existing ZO→EN dictionary as {zolai_lower: entry}."""
    existing = {}
    if not path.exists():
        return existing
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                zolai = entry.get("zolai", "").strip().lower()
                if zolai:
                    existing[zolai] = entry
            except json.JSONDecodeError:
                continue
    return existing


def parse_senses_for_word(word_id: int, senses: list) -> list:
    """Extract all senses for a given word ID."""
    results = []
    for s in senses:
        if s.get("wseq") == word_id or s.get("id") == word_id:
            results.append(s)
    # Also try matching by word position
    return results


def extract_headword_from_sense(sense_text: str) -> str:
    """Try to extract clean English headword from sense text."""
    # Remove numbering like "1. " or "a. "
    text = re.sub(r"^[0-9a-z][\.\)]\s*", "", sense_text.strip())
    # Take first phrase before semicolon or dash
    text = re.split(r"[;–—]", text)[0]
    # Remove trailing POS tags
    text = re.sub(r"\s*\((?:n|v|adj|adv|pron|prep|conj|det)\.\)\s*$", "", text)
    return text.strip()


def main():
    print(f"[integrate_dalsuum] Loading Dalsuum dictionary from: {INPUT_FILE}")
    if not INPUT_FILE.exists():
        print(f"  ERROR: File not found: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        dalsuum = json.load(f)

    words = dalsuum.get("words", [])
    senses = dalsuum.get("senses", [])
    synsets = dalsuum.get("synset", [])

    print(f"  Words: {len(words)}, Senses: {len(senses)}, Synsets: {len(synsets)}")

    # Build synset ID → POS
    synset_pos = {}
    for s in synsets:
        synset_pos[s.get("id", -1)] = s.get("shortname", "other")

    # Build word ID → word text mapping
    word_map = {}
    for w in words:
        word_map[w["id"]] = w["word"]

    # Load existing dictionary for cross-checking
    print(f"[integrate_dalsuum] Loading existing dictionary: {EXISTING_DICT}")
    existing = load_existing_zo_en(EXISTING_DICT)
    print(f"  Existing entries: {len(existing)}")

    # Process senses → build merged entries
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged_count = 0
    new_count = 0
    updated_count = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for sense in senses:
            word_id = sense.get("wseq", sense.get("id", 0))
            word_text = word_map.get(word_id, "").strip()
            if not word_text:
                continue

            # Normalize
            zolai_norm = zvs_normalize(word_text)

            # Extract English from sense
            sense_text = sense.get("sense", "")
            english = extract_headword_from_sense(sense_text)

            if not english or len(english) < 1:
                continue

            # POS from synset
            wrte = sense.get("wrte", -1)
            pos = synset_pos.get(wrte, "other")

            # Example sentence
            example = sense.get("exam", "")

            # Check if word already exists in existing dict
            existing_entry = existing.get(zolai_norm.lower())

            entry = {
                "headword": english,
                "translation": english,
                "zolai_word": word_text,
                "zolai_normalized": zolai_norm,
                "myanmar_word": "",  # Dalsuum doesn't separate Myanmar
                "pos": pos,
                "source": "dalsuum",
                "sense": sense_text,
                "example": example,
                "existing_match": existing_entry is not None,
            }

            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            merged_count += 1

            if existing_entry:
                updated_count += 1
            else:
                new_count += 1

    print("\n[integrate_dalsuum] Done!")
    print(f"  Total entries written: {merged_count}")
    print(f"  New words (not in existing dict): {new_count}")
    print(f"  Words already in existing dict: {updated_count}")
    print(f"  Output: {OUTPUT_FILE}")

    # Summary stats
    print("\n  POS distribution:")
    pos_counts = {}
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            p = entry.get("pos", "other")
            pos_counts[p] = pos_counts.get(p, 0) + 1
    for p, c in sorted(pos_counts.items(), key=lambda x: -x[1]):
        print(f"    {p}: {c}")


if __name__ == "__main__":
    main()
