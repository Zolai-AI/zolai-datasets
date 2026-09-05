#!/usr/bin/env python3
"""
Phase 4: Vocabulary Database Builder.

Aggregates from master dict, supplement, word alignments, and parallel corpus
to build a comprehensive Zolai vocabulary database with frequency, examples,
and collocations.

Usage:
    python3 scripts/bible/build_vocabulary_db.py

Input:
    ../data/dictionary/processed/dict_zo_en_master_v1.jsonl
    ../data/dictionary/processed/dict_canonical_v1.jsonl
    ../data/bible/word_alignments_v1.jsonl
    ../data/bible/parallel_corpus_v1.jsonl

Output:
    ../data/bible/vocabulary_db_v1.jsonl
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
DICT_PATH = WORKSPACE / "data" / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
SUPPLEMENT_PATH = WORKSPACE / "data" / "dictionary" / "processed" / "dict_canonical_v1.jsonl"
ALIGNMENTS_PATH = WORKSPACE / "data" / "bible" / "word_alignments_v1.jsonl"
CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
OUTPUT_PATH = WORKSPACE / "data" / "bible" / "vocabulary_db_v1.jsonl"

# POS tag mapping
POS_MAP = {
    "n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb",
    "pron": "pronoun", "prep": "preposition", "conj": "conjunction",
    "part": "particle", "interj": "interjection", "num": "numeral",
}


def load_dict_entries() -> dict[str, dict]:
    """Load dictionary entries into a lookup by headword."""
    entries: dict[str, dict] = {}
    for path in [DICT_PATH, SUPPLEMENT_PATH]:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                hw = d.get("zolai", d.get("headword", "")).strip().lower()
                en_raw = d.get("english", d.get("translations", []))
                if not hw or len(hw.split()) > 3:
                    continue
                if isinstance(en_raw, str):
                    en_raw = [en_raw]
                clean = []
                pos = ""
                for t in en_raw:
                    if not isinstance(t, str):
                        continue
                    m = t.split("\n")[0].strip()
                    # Extract POS if present
                    pos_match = re.match(r"^(\w+)\s*[/:]", m)
                    if pos_match and not pos:
                        candidate = pos_match.group(1).lower()
                        if candidate in POS_MAP:
                            pos = POS_MAP[candidate]
                    # Clean meaning
                    m = re.sub(r"\s*\([^)]*\)\s*.*", "", m).strip()
                    m = re.sub(r"\s+[a-z]{2,4}\s*[:\-].*$", "", m).strip()
                    if m and len(m) > 1 and m not in clean:
                        clean.append(m)
                if clean:
                    entries[hw] = {
                        "meanings": clean,
                        "pos": pos,
                        "source": d.get("source", "unknown"),
                    }
    return entries


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def build_vocab():
    """Build the vocabulary database."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Loading dictionary...")
    dict_entries = load_dict_entries()
    print(f"  Dict headwords: {len(dict_entries):,}")

    # Load alignments to build frequency + collocation data
    print("Loading alignments...")
    word_freq: Counter = Counter()
    word_examples: dict[str, list[str]] = defaultdict(list)
    word_collocations: dict[str, Counter] = defaultdict(Counter)
    word_confidence: dict[str, list[float]] = defaultdict(list)

    with open(ALIGNMENTS_PATH, encoding="utf-8") as f:
        for line in f:
            a = json.loads(line)
            zo = a["zo_word"]
            word_freq[zo] += 1
            if zo not in word_examples:
                word_examples[zo] = []
            if len(word_examples[zo]) < 3:
                word_examples[zo].append(f"{a['ref']}: {a['en_word']}")
            word_confidence[zo].append(a["confidence"])

    # Load corpus for collocations
    print("Loading corpus for collocations...")
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            v = json.loads(line)
            zo_text = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            if not zo_text:
                continue
            tokens = tokenize(zo_text)
            for i, tok in enumerate(tokens):
                # Collocate = adjacent words
                for j in range(max(0, i - 2), min(len(tokens), i + 3)):
                    if i != j and len(tokens[j]) > 1:
                        word_collocations[tok][tokens[j]] += 1

    print(f"  Words with frequency: {len(word_freq):,}")

    # Build vocabulary entries
    all_words = set(dict_entries.keys()) | set(word_freq.keys())
    vocab_entries = []

    for word in sorted(all_words):
        freq = word_freq.get(word, 0)
        meanings = dict_entries.get(word, {}).get("meanings", [])
        pos = dict_entries.get(word, {}).get("pos", "")
        source = dict_entries.get(word, {}).get("source", "corpus_only")

        # Get confidence
        confs = word_confidence.get(word, [])
        avg_conf = round(sum(confs) / len(confs), 2) if confs else 0.5

        # Get top collocations
        top_cols = word_collocations[word].most_common(5)
        collocations = [
            {"word": c[0], "count": c[1]} for c in top_cols
        ]

        # Get example verses
        examples = word_examples.get(word, [])

        vocab_entries.append({
            "zo": word,
            "english": meanings[0] if meanings else "",
            "pos": pos,
            "meanings": meanings[:5],
            "frequency": freq,
            "examples": examples,
            "collocations": collocations,
            "confidence": avg_conf,
            "source": source,
        })

    # Write output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for v in vocab_entries:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    # Stats
    with_meanings = sum(1 for v in vocab_entries if v["meanings"])
    with_freq = sum(1 for v in vocab_entries if v["frequency"] > 0)
    top_20 = sorted(vocab_entries, key=lambda x: -x["frequency"])[:20]

    print(f"\n✅ Vocabulary database built: {OUTPUT_PATH.name}")
    print(f"   Total entries: {len(vocab_entries):,}")
    print(f"   With meanings: {with_meanings:,}")
    print(f"   With frequency: {with_freq:,}")
    print("\n   Top 20 words by frequency:")
    for v in top_20:
        print(f"     {v['zo']:12s} freq={v['frequency']:5d}  {v['english'][:40]}")
    print(f"   Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_vocab()
