#!/usr/bin/env python3
"""
Phase 2: Word Alignment Engine.

Reads parallel_corpus_v1.jsonl, tokenizes ZO and EN, uses dictionary
to find ZO→EN mappings, and produces word-level alignments.

Usage:
    python3 scripts/bible/align_words.py

Input:
    ../data/bible/parallel_corpus_v1.jsonl
    ../data/dictionary/processed/dict_zo_en_master_v1.jsonl
    ../data/dictionary/processed/dict_bible_supplement_v1.jsonl

Output:
    ../data/bible/word_alignments_v1.jsonl
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
DICT_PATH = WORKSPACE / "data" / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
SUPPLEMENT_PATH = WORKSPACE / "data" / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"
OUTPUT_PATH = WORKSPACE / "data" / "bible" / "word_alignments_v1.jsonl"

# Function words that commonly map to English stopwords — skip these
ZOLAI_FUNCTION_WORDS = {
    "in", "a", "hi", "uh", "leh", "tawh", "ah", "kha", "ta", "pah",
    "ciangin", "bangin", "pen", "na", "ding", "lai", "hen", "la", "tua", "te",
    "i", "napi", "hiam", "un", "ni", "aw", "ma", "mah", "ka", "nang", "amah",
    "eima", "keima", "nangmah", "ih", "ite", "nate", "kite", "amaute",
    "hong", "an", "ciin", "ci", "khi", "kuh", "pe", "panin", "cih",
    "tungtunga", "tungah", "nuai-a", "nuai", "sunga", "sung",
    "leitang", "tuate", "amau", "kam", "khin", "ngei", "kei", "lo",
}

EN_STOPWORDS = {
    "the", "and", "of", "to", "in", "a", "an", "is", "was", "he", "she", "it",
    "his", "her", "they", "them", "their", "that", "this", "for", "with", "not",
    "but", "all", "be", "are", "were", "have", "had", "has", "from", "by", "at",
    "on", "or", "so", "as", "him", "we", "you", "i", "my", "thy", "thee",
    "shall", "will", "said", "unto", "upon", "which", "who", "then", "when",
    "also", "now", "out", "up", "did", "do", "no", "if", "me", "us", "our",
    "its", "than", "into", "even", "yet", "let", "may", "one", "two", "three",
}


def load_dictionary() -> tuple[dict[str, list[str]], dict[str, str]]:
    """Load master + supplement dictionaries. Returns (all_meanings, first_meaning)."""
    all_m: dict[str, list[str]] = {}
    first_m: dict[str, str] = {}

    for path in [DICT_PATH, SUPPLEMENT_PATH]:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                # Handle both formats
                hw = d.get("zolai", d.get("headword", "")).strip().lower()
                en_raw = d.get("english", d.get("translations", []))
                if not hw or len(hw.split()) > 3:
                    continue
                if isinstance(en_raw, str):
                    en_raw = [en_raw]
                clean = []
                for t in en_raw:
                    if not isinstance(t, str):
                        continue
                    m = t.split("\n")[0].strip()
                    # Remove parenthetical notes
                    m = re.sub(r"\s*\([^)]*\)\s*.*", "", m).strip()
                    # Remove trailing POS tags
                    m = re.sub(r"\s+[a-z]{2,4}\s*[:\-].*$", "", m).strip()
                    if m and len(m) > 1 and m not in clean:
                        clean.append(m)
                if clean:
                    all_m[hw] = clean
                    first_m[hw] = clean[0]

    return all_m, first_m


def tokenize_zo(text: str) -> list[str]:
    """Tokenize Zolai text into words (strip punctuation)."""
    return re.findall(r"[a-z']+", text.lower())


def tokenize_en(text: str) -> list[str]:
    """Tokenize English text into words (strip punctuation)."""
    return re.findall(r"[a-zA-Z']+", text.lower())


def align_verse(
    zo_text: str,
    en_text: str,
    all_dict: dict[str, list[str]],
    first_dict: dict[str, str],
) -> list[dict]:
    """Align ZO words to EN words for a single verse."""
    zo_tokens = tokenize_zo(zo_text)
    en_tokens = tokenize_en(en_text)
    en_lower = [t.lower() for t in en_tokens]

    alignments = []
    seen_pairs: set[str] = set()

    for zo_word in zo_tokens:
        if zo_word in ZOLAI_FUNCTION_WORDS:
            continue
        if len(zo_word) <= 1:
            continue

        # Look up in dictionary
        if zo_word in first_dict:
            en_word = first_dict[zo_word]
            # Check if this English word appears in the verse
            en_word_lower = en_word.lower()
            if en_word_lower in en_lower:
                # Find best matching EN token position
                en_positions = [
                    i for i, t in enumerate(en_lower) if t == en_word_lower
                ]
                # Pick position closest to a plausible alignment point
                # (SOV→SVO: Object and Verb are close, Subject is later)
                best_pos = en_positions[0] if en_positions else 0
                confidence = 0.9 if len(all_dict.get(zo_word, [])) == 1 else 0.7
            else:
                # Dictionary match but word not in this verse
                best_pos = -1
                en_word = first_dict[zo_word]
                confidence = 0.5
        else:
            continue  # Unknown word — skip

        pair_key = f"{zo_word}|{en_word}|{best_pos}"
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        alignments.append({
            "zo_word": zo_word,
            "en_word": en_word,
            "en_position": best_pos,
            "confidence": round(confidence, 2),
            "source": "dict_match",
        })

    return alignments


def build_alignments():
    """Build word alignments from parallel corpus."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not CORPUS_PATH.exists():
        print(f"ERROR: Corpus not found: {CORPUS_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Loading dictionary...")
    all_dict, first_dict = load_dictionary()
    print(f"  Dict entries: {len(all_dict):,} (first meanings: {len(first_dict):,})")

    total_verses = 0
    total_alignments = 0
    verses_with_alignments = 0
    unique_zo = set()
    unique_en = set()
    confidence_dist = Counter()

    with open(CORPUS_PATH, encoding="utf-8") as inf, \
         open(OUTPUT_PATH, "w", encoding="utf-8") as outf:
        for line in inf:
            v = json.loads(line)
            total_verses += 1

            # Use Tedim2010 as primary ZO, fall back to TDB77
            zo_text = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en_text = v.get("en_kJV") or ""

            if not zo_text or not en_text:
                continue

            alignments = align_verse(zo_text, en_text, all_dict, first_dict)
            if not alignments:
                continue

            verses_with_alignments += 1
            for a in alignments:
                a["ref"] = v["ref"]
                a["book"] = v["book"]
                outf.write(json.dumps(a, ensure_ascii=False) + "\n")
                total_alignments += 1
                unique_zo.add(a["zo_word"])
                unique_en.add(a["en_word"])
                confidence_dist[a["confidence"]] += 1

    print(f"✅ Word alignments built: {OUTPUT_PATH.name}")
    print(f"   Verses processed: {total_verses:,}")
    print(f"   Verses with alignments: {verses_with_alignments:,}")
    print(f"   Total alignments: {total_alignments:,}")
    print(f"   Unique ZO words: {len(unique_zo):,}")
    print(f"   Unique EN words: {len(unique_en):,}")
    print(f"   Confidence distribution: {dict(confidence_dist.most_common())}")
    print(f"   Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_alignments()
