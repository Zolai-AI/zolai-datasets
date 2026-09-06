#!/usr/bin/env python3
"""
Build comprehensive vocabulary database from ALL sources.
Merges: vocab_by_frequency + vocab_comprehensive + corpus online + dalsuum + dict_zo_en
Outputs: data/bible/language_learning/vocab_master.jsonl (target 25K+)
"""

import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "vocab_master.jsonl"

# All vocabulary sources (priority order — higher priority wins)
VOCAB_SOURCES = [
    {
        "name": "vocab_by_frequency",
        "path": DATA_DIR / "bible" / "language_learning" / "vocab_by_frequency.jsonl",
        "key_zo": "zo",
        "key_en": "translation",
        "has_freq": True,
        "freq_key": "frequency",
    },
    {
        "name": "vocab_comprehensive",
        "path": DATA_DIR / "bible" / "language_learning" / "vocab_comprehensive.jsonl",
        "key_zo": "word",
        "key_en": "translation",
        "has_freq": True,
        "freq_key": "frequency",
    },
    {
        "name": "dict_zo_en",
        "path": DATA_DIR / "dictionary" / "processed" / "dict_zo_en_clean.jsonl",
        "key_zo": "zolai",
        "key_en": "english_clean",
        "has_freq": False,
        "freq_key": None,
    },
]

# Online corpus vocab (if extracted)
ONLINE_VOCAB = DATA_DIR / "bible" / "language_learning" / "vocab_online.jsonl"

# Dalsuum dictionary
DALSUUM_DICT = DATA_DIR / "dictionary" / "processed" / "dict_dalsuum_merged.jsonl"

# ZVS 2018 normalization map
ZVS_MAP = {
    "pathian": "pasian", "ram": "gam", "fapa": "tapa", "bawipa": "topa",
    "siangpahrang": "kumpipa", "cu": "tua", "cun": "tua",
    "suah": "chuak", "zalenna": "suahtakna", "nunnak": "nuntakna",
}


def zvs_normalize(word: str) -> str:
    low = word.strip().lower()
    return ZVS_MAP.get(low, low)


def load_jsonl_entries(filepath: Path, key_zo: str, key_en: str,
                       has_freq: bool = False, freq_key: str | None = None) -> list:
    """Load a JSONL vocab file into unified format."""
    entries = []
    if not filepath.exists():
        return entries
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            zo = data.get(key_zo, "").strip()
            en = data.get(key_en, "")
            if isinstance(en, list):
                en = en[0] if en else ""
            en = str(en).strip() if en else ""
            if not zo or len(zo) < 2:
                continue
            freq = data.get(freq_key, 0) if has_freq and freq_key else 0
            entries.append({
                "word": zvs_normalize(zo),
                "translation": en,
                "frequency": freq,
            })
    return entries


def load_corpus_vocab(filepath: Path) -> dict:
    """Load online corpus vocab as {word: frequency}."""
    freqs = {}
    if not filepath.exists():
        return freqs
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                word = data.get("word", "").strip().lower()
                freq = data.get("frequency", 0)
                if word and freq > 0:
                    freqs[word] = freq
            except json.JSONDecodeError:
                continue
    return freqs


def load_dalsuum_vocab(filepath: Path) -> dict:
    """Load dalsuum entries as {word: translation}."""
    vocab = {}
    if not filepath.exists():
        return vocab
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                word = data.get("zolai_normalized", "").strip().lower()
                trans = data.get("translation", "")
                if word and trans:
                    vocab[word] = trans
            except json.JSONDecodeError:
                continue
    return vocab


def main():
    print("[vocab_builder] Building master vocabulary database...")
    print(f"  Output: {OUTPUT_FILE}")

    # Master vocab dict: {normalized_word: {word, translation, frequency, sources}}
    master = {}

    # 1. Load primary vocab sources
    for source in VOCAB_SOURCES:
        name = source["name"]
        filepath = source["path"]
        print(f"\n  Loading {name}: {filepath.name}")
        entries = load_jsonl_entries(
            filepath, source["key_zo"], source["key_en"],
            source["has_freq"], source["freq_key"]
        )
        print(f"    Loaded {len(entries):,} entries")
        for entry in entries:
            word = entry["word"]
            if word not in master:
                master[word] = {
                    "word": word,
                    "translation": entry["translation"],
                    "frequency": entry["frequency"],
                    "sources": set(),
                }
            m = master[word]
            m["sources"].add(name)
            # Update frequency (take max)
            m["frequency"] = max(m["frequency"], entry["frequency"])
            # Update translation (take non-empty)
            if entry["translation"] and not m["translation"]:
                m["translation"] = entry["translation"]

    print(f"\n  After primary sources: {len(master):,} unique words")

    # 2. Add corpus frequency data
    print("\n  Loading corpus frequencies...")
    corpus_freqs = load_corpus_vocab(ONLINE_VOCAB)
    print(f"    Corpus words: {len(corpus_freqs):,}")
    new_from_corpus = 0
    for word, freq in corpus_freqs.items():
        if word in master:
            master[word]["frequency"] = max(master[word]["frequency"], freq)
            master[word]["sources"].add("paumkim_corpus")
        else:
            master[word] = {
                "word": word,
                "translation": "",
                "frequency": freq,
                "sources": {"paumkim_corpus"},
            }
            new_from_corpus += 1
    print(f"    Added {new_from_corpus:,} new words from corpus")

    # 3. Add dalsuum dictionary words
    print("\n  Loading dalsuum dictionary...")
    dalsuum_vocab = load_dalsuum_vocab(DALSUUM_DICT)
    print(f"    Dalsuum words: {len(dalsuum_vocab):,}")
    new_from_dalsuum = 0
    for word, trans in dalsuum_vocab.items():
        if word in master:
            master[word]["sources"].add("dalsuum")
            if trans and not master[word]["translation"]:
                master[word]["translation"] = trans
        else:
            master[word] = {
                "word": word,
                "translation": trans,
                "frequency": 0,
                "sources": {"dalsuum"},
            }
            new_from_dalsuum += 1
    print(f"    Added {new_from_dalsuum:,} new words from dalsuum")

    # 4. Convert to sorted list
    vocab_list = list(master.values())
    for entry in vocab_list:
        entry["sources"] = sorted(entry["sources"])
        entry["source_count"] = len(entry["sources"])

    # Sort by frequency desc, then source_count desc, then alphabetically
    vocab_list.sort(key=lambda x: (-x["frequency"], -x["source_count"], x["word"]))

    # 5. Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in vocab_list:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 6. Stats
    print("\n[vocab_builder] Done!")
    print(f"  Total unique words: {len(vocab_list):,}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

    # Source distribution
    source_counts = defaultdict(int)
    for entry in vocab_list:
        for s in entry["sources"]:
            source_counts[s] += 1
    print("\n  Source distribution:")
    for s, c in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {s}: {c:,}")

    # Frequency stats
    has_freq = sum(1 for e in vocab_list if e["frequency"] > 0)
    has_trans = sum(1 for e in vocab_list if e["translation"])
    print(f"\n  Words with frequency data: {has_freq:,}")
    print(f"  Words with translation: {has_trans:,}")

    # Top 20 words
    print("\n  Top 20 words:")
    for entry in vocab_list[:20]:
        trans = entry["translation"][:40] if entry["translation"] else "(no translation)"
        print(f"    {entry['word']:25s} freq={entry['frequency']:>8,}  {trans}")


if __name__ == "__main__":
    main()
