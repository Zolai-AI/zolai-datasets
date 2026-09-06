#!/usr/bin/env python3
"""
Extract vocabulary from paumkim corpus (3M+ lines, ~208MB).
Processes line-by-line to avoid memory issues.
Outputs:
  - data/bible/language_learning/vocab_online.jsonl (all words with frequency)
  - data/bible/language_learning/vocab_new_words.jsonl (only words NOT in existing vocab)
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

CORPUS_FILES = [
    DATA_DIR / "online" / "paumkim-corpus" / "zomi_clean_p1.txt",
    DATA_DIR / "online" / "paumkim-corpus" / "zomi_clean_p2.txt",
    DATA_DIR / "online" / "paumkim-corpus" / "zomi_clean_p3.txt",
    DATA_DIR / "online" / "paumkim-corpus" / "zomi_clean_p4.txt",
]

EXISTING_VOCAB = DATA_DIR / "bible" / "language_learning" / "vocab_comprehensive.jsonl"
OUTPUT_ALL = DATA_DIR / "bible" / "language_learning" / "vocab_online.jsonl"
OUTPUT_NEW = DATA_DIR / "bible" / "language_learning" / "vocab_new_words.jsonl"

# Minimum word length to count
MIN_WORD_LEN = 2
# Maximum word length to count
MAX_WORD_LEN = 40


def tokenize_line(line: str) -> list:
    """Tokenize a line into words. Handles Zolai orthography."""
    # Remove URLs
    line = re.sub(r"https?://\S+", "", line)
    # Split on whitespace and punctuation
    tokens = re.findall(r"[a-zA-Z\u1000-\u109f\uaa00-\uaaff]+", line)
    # Filter by length
    return [t.lower() for t in tokens if MIN_WORD_LEN <= len(t) <= MAX_WORD_LEN]


def load_existing_vocab(path: Path) -> set:
    """Load existing vocabulary words as a set."""
    words = set()
    if not path.exists():
        print(f"  WARNING: Existing vocab not found: {path}")
        return words
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                w = entry.get("word", "").strip().lower()
                if w:
                    words.add(w)
            except json.JSONDecodeError:
                continue
    return words


def main():
    print("[extract_corpus_vocab] Starting corpus vocabulary extraction...")
    print(f"  Corpus files: {len(CORPUS_FILES)}")

    # Check files exist
    existing_files = [f for f in CORPUS_FILES if f.exists()]
    if not existing_files:
        print("  ERROR: No corpus files found!")
        sys.exit(1)
    print(f"  Found {len(existing_files)}/{len(CORPUS_FILES)} corpus files")

    # Count words
    word_counts = Counter()
    total_lines = 0

    for corpus_file in existing_files:
        print(f"  Processing: {corpus_file.name}...")
        file_lines = 0
        with open(corpus_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                tokens = tokenize_line(line)
                word_counts.update(tokens)
                file_lines += 1
                total_lines += 1
                if total_lines % 500000 == 0:
                    print(f"    ... {total_lines:,} lines processed, {len(word_counts):,} unique words")
        print(f"    Done: {file_lines:,} lines")

    print(f"\n  Total lines: {total_lines:,}")
    print(f"  Unique words: {len(word_counts):,}")

    # Load existing vocab
    print(f"\n[extract_corpus_vocab] Loading existing vocab: {EXISTING_VOCAB}")
    existing_vocab = load_existing_vocab(EXISTING_VOCAB)
    print(f"  Existing vocab words: {len(existing_vocab):,}")

    # Write all vocab
    OUTPUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n[extract_corpus_vocab] Writing all vocab to: {OUTPUT_ALL}")

    new_words = []
    with open(OUTPUT_ALL, "w", encoding="utf-8") as out:
        for word, freq in word_counts.most_common():
            entry = {
                "word": word,
                "frequency": freq,
                "source": "paumkim_corpus",
                "in_existing_vocab": word in existing_vocab,
            }
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            if word not in existing_vocab:
                new_words.append(entry)

    # Write new words only
    print(f"  Writing new words to: {OUTPUT_NEW}")
    with open(OUTPUT_NEW, "w", encoding="utf-8") as out:
        for entry in new_words:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("\n[extract_corpus_vocab] Done!")
    print(f"  Total vocab written: {len(word_counts):,}")
    print(f"  New words (not in existing): {len(new_words):,}")
    print(f"  Coverage: {len(word_counts) - len(new_words)}/{len(word_counts)} "
          f"({100 * (len(word_counts) - len(new_words)) / max(len(word_counts), 1):.1f}%)")

    # Show top 20 new words
    if new_words:
        print("\n  Top 20 new words by frequency:")
        for entry in new_words[:20]:
            print(f"    {entry['word']:30s} freq={entry['frequency']:,}")


if __name__ == "__main__":
    main()
