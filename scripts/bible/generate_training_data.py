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





# ── Grammar-Aware Synthesis ────────────────────────────────

OUT_DIR = EXERCISES_PATH.parent


def generate_negation_exercises(corpus: list[dict]) -> int:
    """Generate negation exercises using correct grammar rules.

    Rules:
    - "kei" is the standard negation particle for ALL persons
    - "lo" is also valid (literary/formal)
    - Future negation: "kei + ding" or "lo + ding"
    """
    count = 0
    negation_patterns = [
        (r"\bhi\b", "kei", "present negation with kei"),
        (r"\bding\b", "kei", "future negation with kei"),
        (r"\bhi\b", "lo", "present negation with lo"),
        (r"\bding\b", "lo", "future negation with lo"),
    ]

    out_path = OUT_DIR / "negation_exercises.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for v in corpus:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            words = re.findall(r"[a-zA-Z'’]+", zo)
            has_verb = any(w in words for w in ["hi", "ding", "a", "in"])

            if has_verb:
                for pattern, neg_part, desc in negation_patterns:
                    if re.search(pattern, zo):
                        instr = (
                            f"Make this sentence negative "
                            f"using '{neg_part}':"
                        )
                        f.write(json.dumps({
                            "instruction": instr,
                            "input": en,
                            "output": zo,
                            "negation_type": desc,
                            "reference": ref,
                            "confidence": 0.8,
                        }, ensure_ascii=False) + "\n")
                        count += 1
                        break
    return count


def generate_question_exercises(corpus: list[dict]) -> int:
    """Generate question exercises using correct grammar rules.

    Rules:
    - Yes/no: Subject + verb + hiam?
    - Future: Subject + verb + diam?
    - Content: bang hang + verb + subject + hiam?
    """
    count = 0
    out_path = OUT_DIR / "question_exercises.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for v in corpus:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            words = re.findall(r"[a-zA-Z'’]+", zo)

            has_verb = any(w in words for w in ["hi", "a", "in"])
            if "hiam" not in words and has_verb:
                f.write(json.dumps({
                    "instruction": (
                        "Turn this statement into a yes/no "
                        "question (add 'hiam' at the end):"
                    ),
                    "input": en,
                    "output": zo,
                    "question_type": "yes/no",
                    "reference": ref,
                    "confidence": 0.85,
                }, ensure_ascii=False) + "\n")
                count += 1

            if "why" in en.lower() and "bang hang" not in words:
                instr = (
                    "Rewrite this as a content question using "
                    "'bang hang' + verb + subject + 'hiam':"
                )
                f.write(json.dumps({
                    "instruction": instr,
                    "input": en,
                    "output": zo,
                    "question_type": "content",
                    "word_order": "bang hang + V + S + hiam",
                    "reference": ref,
                    "confidence": 0.8,
                }, ensure_ascii=False) + "\n")
                count += 1
    return count


def generate_error_correction_exercises(corpus: list[dict]) -> int:
    """Generate error correction exercises from known patterns.

    Based on native speaker corrections:
    1. "Ka an nek hi" -> "Ka ne hi"
    2. "Mi in ne hi" -> "Mipa in ne hi"
    3. "Bang hang na pai hiam?" -> "Bang hang pai na hiam?"
    """
    count = 0
    # (find_correct_pattern, introduce_error, description)
    # pattern finds the CORRECT form; replacement introduces the ERROR
    error_patterns = [
        (r"(\b)ka (\w+) hi", r"\1ka an \2 hi",
         "Remove 'an' before verb (1st person)"),
        (r"(\b)na (\w+) hi", r"\1na an \2 hi",
         "Remove 'an' before verb (2nd person)"),
        (r"(\b)a (\w+) hi", r"\1a an \2 hi",
         "Remove 'an' before verb (3rd person)"),
        (r"(\b)mi in (\w+)", r"\1mipa in \2",
         "Use 'mipa' (man) not 'mi' (person)"),
        (r"bang hang (\w+) na hiam",
         r"bang hang na \1 hiam",
         "Verb before subject in content questions"),
    ]

    out_path = OUT_DIR / "error_correction_exercises.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for v in corpus:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            for cor_pattern, err_repl, expl in error_patterns:
                sim_err = re.sub(
                    cor_pattern, err_repl, zo
                )
                if sim_err != zo:
                    f.write(json.dumps({
                        "instruction": (
                            f"Fix the grammar error: {expl}"
                        ),
                        "input": sim_err,
                        "output": zo,
                        "error_type": expl,
                        "reference": ref,
                        "confidence": 0.9,
                    }, ensure_ascii=False) + "\n")
                    count += 1
                    break
    return count


def generate_conditional_exercises(corpus: list[dict]) -> int:
    """Generate conditional exercises using correct grammar.

    Rule: "na pai kei a leh" is CORRECT (not forbidden)
    """
    count = 0
    out_path = OUT_DIR / "conditional_exercises.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for v in corpus:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            if "if " in en.lower():
                words = re.findall(
                    r"[a-zA-Z'’]+", zo
                )
                if "leh" not in words:
                    f.write(json.dumps({
                        "instruction": (
                            "Rewrite this as a conditional "
                            "using 'a leh' at the end:"
                        ),
                        "input": en,
                        "output": zo,
                        "grammar_point": "conditional (a leh)",
                        "reference": ref,
                        "confidence": 0.8,
                    }, ensure_ascii=False) + "\n")
                    count += 1
    return count


def generate_pronoun_exercises(corpus: list[dict]) -> int:
    """Generate pronoun exercises using correct grammar.

    Rules:
    - "a" = 3rd person agreement marker (goes before verb)
    - "amah" = 3rd person standalone pronoun (emphasis)
    """
    count = 0
    out_path = OUT_DIR / "pronoun_exercises.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for v in corpus:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            if any(w in zo for w in ["a ", "a'"]):
                words = re.findall(
                    r"[a-zA-Z'’]+", zo
                )
                if "a" in words and "amah" not in words:
                    f.write(json.dumps({
                        "instruction": (
                            "Rewrite this sentence with "
                            "emphasis on the subject "
                            "(use 'amah'):"
                        ),
                        "input": en,
                        "output": zo,
                        "grammar_point": (
                            "pronoun emphasis (amah)"
                        ),
                        "reference": ref,
                        "confidence": 0.75,
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


    print("\nGenerating negation exercises (grammar-aware)...")
    n_negation = generate_negation_exercises(corpus)
    print(f"  \u2192 {n_negation:,} negation exercises")

    print("\nGenerating question exercises (grammar-aware)...")
    n_questions = generate_question_exercises(corpus)
    print(f"  \u2192 {n_questions:,} question exercises")

    print("\nGenerating error correction exercises...")
    n_errors = generate_error_correction_exercises(corpus)
    print(f"  \u2192 {n_errors:,} error correction exercises")

    print("\nGenerating conditional exercises...")
    n_conditional = generate_conditional_exercises(corpus)
    print(f"  \u2192 {n_conditional:,} conditional exercises")

    print("\nGenerating pronoun exercises...")
    n_pronoun = generate_pronoun_exercises(corpus)
    print(f"  \u2192 {n_pronoun:,} pronoun exercises")

    total = (n_translations + n_exercises + n_quizzes
             + n_negation + n_questions + n_errors
             + n_conditional + n_pronoun)
    print(f"\n\u2705 Training data generated: {total:,} total")
    print(f"   {TRANSLATIONS_PATH.name}: {n_translations:,} pairs")
    print(f"   {EXERCISES_PATH.name}: {n_exercises:,} exercises")
    print(f"   {QUIZ_PATH.name}: {n_quizzes:,} questions")
    print(f"   negation_exercises.jsonl: {n_negation:,}")
    print(f"   question_exercises.jsonl: {n_questions:,}")
    print(f"   error_correction_exercises.jsonl: {n_errors:,}")
    print(f"   conditional_exercises.jsonl: {n_conditional:,}")
    print(f"   pronoun_exercises.jsonl: {n_pronoun:,}")


if __name__ == "__main__":
    generate_training_data()
