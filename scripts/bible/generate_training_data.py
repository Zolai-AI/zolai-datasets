#!/usr/bin/env python3
"""
Phase 5: Training Data Generator.

Generates translation pairs, grammar exercises, and vocabulary quizzes
from the parallel corpus and vocabulary database.

Usage:
    python3 scripts/bible/generate_training_data.py

Input:
    ../data/bible/parallel_corpus_v1.jsonl
    ../data/bible/vocabulary_db_v1.jsonl
    ../data/bible/grammar_patterns_v1.jsonl

Output:
    ../data/bible/translation_pairs_v1.jsonl
    ../data/bible/grammar_exercises_v1.jsonl
    ../data/bible/vocabulary_quiz_v1.jsonl
"""

import json
import re
import sys
import random
from collections import defaultdict
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
VOCAB_PATH = WORKSPACE / "data" / "bible" / "vocabulary_db_v1.jsonl"
GRAMMAR_PATH = WORKSPACE / "data" / "bible" / "grammar_patterns_v1.jsonl"
TRANSLATIONS_PATH = WORKSPACE / "data" / "bible" / "translation_pairs_v1.jsonl"
EXERCISES_PATH = WORKSPACE / "data" / "bible" / "grammar_exercises_v1.jsonl"
QUIZ_PATH = WORKSPACE / "data" / "bible" / "vocabulary_quiz_v1.jsonl"

random.seed(42)  # Reproducibility


def load_corpus() -> list[dict]:
    with open(CORPUS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_vocab() -> dict[str, dict]:
    vocab = {}
    with open(VOCAB_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            vocab[d["zo"]] = d
    return vocab


def load_grammar_patterns() -> list[dict]:
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def generate_translations(corpus: list[dict]) -> int:
    """Generate ZO→EN and EN→ZO translation pairs."""
    count = 0
    with open(TRANSLATIONS_PATH, "w", encoding="utf-8") as f:
        for v in corpus:
            zo_tdb77 = v.get("zo_tdb77")
            zo_tedim = v.get("zo_tedim2010")
            en = v.get("en_kJV")
            if not en:
                continue

            # ZO → EN pair (use Tedim2010 as primary)
            zo = zo_tedim or zo_tdb77
            if zo:
                # Confidence: both versions match → high
                if zo_tdb77 and zo_tedim:
                    confidence = 0.95
                elif zo:
                    confidence = 0.85
                else:
                    confidence = 0.0

                f.write(json.dumps({
                    "source": zo,
                    "target": en,
                    "direction": "zo_to_en",
                    "reference": v["ref"],
                    "confidence": confidence,
                }, ensure_ascii=False) + "\n")
                count += 1

            # EN → ZO pair
            if zo_tedim:
                f.write(json.dumps({
                    "source": en,
                    "target": zo_tedim,
                    "direction": "en_to_zo",
                    "reference": v["ref"],
                    "confidence": 0.9,
                }, ensure_ascii=False) + "\n")
                count += 1

    return count


def generate_grammar_exercises(corpus: list[dict], patterns: list[dict]) -> int:
    """Generate grammar exercises from corpus patterns."""
    count = 0

    # Build ref → verse lookup
    ref_to_verse: dict[str, dict] = {}
    for v in corpus:
        ref_to_verse[v["ref"]] = v

    # Tense exercise templates
    tense_instructions = {
        "tense_khin": "Translate this sentence using past tense (khin):",
        "tense_ngei": "Translate this sentence using experiential past (ngei):",
        "tense_ding": "Translate this sentence using future tense (ding):",
        "tense_ta": "Translate this sentence using inchoative (ta):",
        "tense_pah": "Translate this sentence using inchoative/continuative (pah):",
    }

    negation_instructions = {
        "negation_kei": "Make this sentence negative using 'kei':",
        "negation_lo": "Make this sentence negative using 'lo':",
        "negation_kei_lo": "Make this sentence strongly negative using 'kei ... lo':",
    }

    aspect_instructions = {
        "aspect_zo": "Express this sentence in the completive aspect (zo):",
        "aspect_lai": "Express this sentence in the progressive aspect (lai):",
        "aspect_sak": "Express this sentence using the causative (sak):",
    }

    all_instructions = {
        **tense_instructions, **negation_instructions, **aspect_instructions,
    }

    # Group patterns by ref
    patterns_by_ref: dict[str, list[dict]] = defaultdict(list)
    for p in patterns:
        for ref in p.get("refs", "").split("; "):
            if ref:
                patterns_by_ref[ref].append(p)

    with open(EXERCISES_PATH, "w", encoding="utf-8") as f:
        for ref, pats in patterns_by_ref.items():
            verse = ref_to_verse.get(ref)
            if not verse:
                continue

            zo = verse.get("zo_tedim2010") or verse.get("zo_tdb77") or ""
            en = verse.get("en_kJV") or ""
            if not zo or not en:
                continue

            for p in pats:
                pattern_type = p["pattern"]
                instruction = all_instructions.get(pattern_type, "")
                if not instruction:
                    continue

                f.write(json.dumps({
                    "instruction": instruction,
                    "input": en,
                    "output": zo,
                    "pattern_id": p["id"],
                    "pattern_type": pattern_type,
                    "reference": ref,
                    "confidence": p.get("confidence", 0.7),
                }, ensure_ascii=False) + "\n")
                count += 1

    return count


def generate_vocabulary_quiz(corpus: list[dict], vocab: dict[str, dict]) -> int:
    """Generate vocabulary quiz questions."""
    count = 0

    # Collect words with meanings from corpus
    word_occurrences: dict[str, list[str]] = defaultdict(list)
    for v in corpus:
        zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
        en = v.get("en_kJV") or ""
        if not zo or not en:
            continue
        tokens = tokenize(zo)
        for tok in tokens:
            if len(tok) > 2 and tok in vocab and vocab[tok].get("meanings"):
                word_occurrences[tok].append(v["ref"])

    with open(QUIZ_PATH, "w", encoding="utf-8") as f:
        for word, refs in word_occurrences.items():
            v = vocab[word]
            meanings = v.get("meanings", [])
            if not meanings:
                continue

            # Quiz type 1: ZO → EN (multiple choice)
            correct = meanings[0]
            # Pick 3 distractors from same POS
            distractors = []
            for other_word, other_v in vocab.items():
                if other_word != word and other_v.get("meanings"):
                    other_meanings = other_v["meanings"]
                    if len(distractors) < 3 and other_meanings[0] != correct:
                        distractors.append(other_meanings[0])
                if len(distractors) >= 3:
                    break

            options = [correct] + distractors[:3]
            random.shuffle(options)

            f.write(json.dumps({
                "instruction": f"What does '{word}' mean in English?",
                "input": word,
                "output": correct,
                "options": options,
                "correct_index": options.index(correct),
                "type": "zo_to_en",
                "reference": "; ".join(refs[:3]),
                "frequency": v.get("frequency", 0),
            }, ensure_ascii=False) + "\n")
            count += 1

            # Quiz type 2: EN → ZO (fill in the blank)
            if len(refs) > 0:
                ref = refs[0]
                f.write(json.dumps({
                    "instruction": f"Translate '{correct}' into Zolai.",
                    "input": correct,
                    "output": word,
                    "type": "en_to_zo",
                    "reference": ref,
                    "frequency": v.get("frequency", 0),
                }, ensure_ascii=False) + "\n")
                count += 1

    return count


def generate_training_data():
    """Generate all training datasets."""
    OUTPUT_PATH = TRANSLATIONS_PATH.parent
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    if not CORPUS_PATH.exists():
        print(f"ERROR: Corpus not found: {CORPUS_PATH}", file=sys.stderr)
        sys.exit(1)
    if not VOCAB_PATH.exists():
        print(f"ERROR: Vocabulary not found: {VOCAB_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Loading data...")
    corpus = load_corpus()
    vocab = load_vocab()
    patterns = load_grammar_patterns()
    print(f"  Corpus: {len(corpus):,} verses")
    print(f"  Vocabulary: {len(vocab):,} words")
    print(f"  Grammar patterns: {len(patterns):,}")

    print("\nGenerating translation pairs...")
    n_translations = generate_translations(corpus)
    print(f"  → {n_translations:,} translation pairs")

    print("\nGenerating grammar exercises...")
    n_exercises = generate_grammar_exercises(corpus, patterns)
    print(f"  → {n_exercises:,} grammar exercises")

    print("\nGenerating vocabulary quizzes...")
    n_quizzes = generate_vocabulary_quiz(corpus, vocab)
    print(f"  → {n_quizzes:,} vocabulary quiz questions")

    print("\n✅ Training data generated:")
    print(f"   {TRANSLATIONS_PATH.name}: {n_translations:,} pairs")
    print(f"   {EXERCISES_PATH.name}: {n_exercises:,} exercises")
    print(f"   {QUIZ_PATH.name}: {n_quizzes:,} questions")


if __name__ == "__main__":
    generate_training_data()
