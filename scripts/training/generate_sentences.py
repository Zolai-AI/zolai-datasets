#!/usr/bin/env python3
"""Rule-based Zolai sentence generation from grammar patterns + dictionary.

Loads grammar patterns from data/bible/grammar_patterns_text.jsonl and
vocabulary from data/bible/vocab_index_full.jsonl. For each pattern, fills
slots (S, O) with real vocabulary words and generates Zolai sentences with
English translations.

Pattern types supported:
  - Declarative: S-in-O-uh-hi, S-in-O-ci-hi, S-in-O-a-hi, etc.
  - Question:    S-in-O-uh-hiam
  - Negation:    S-in-O-kei, a-lo, S-in-O-lo
  - Past:        S-in-O-ciangin, ciangin-a
  - Future:      S-in-O-ding-hi, ding-hi, S-in-O-ding

Usage:
    python generate_sentences.py --max-sentences 5000 --output data/training/generated_sentences.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[4]
GRAMMAR_PATH = WORKSPACE / "data/bible/grammar_patterns_text.jsonl"
VOCAB_PATH = WORKSPACE / "data/bible/vocab_index_full.jsonl"
DICT_PATH = WORKSPACE / "data/dictionary/processed/dict_zo_en_clean.jsonl"

# ---------------------------------------------------------------------------
# ZVS 2018 forbidden forms → correct forms
# ---------------------------------------------------------------------------

ZVS_CORRECTIONS: dict[str, str] = {
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

# Subject markers and their English equivalents
SUBJECT_MARKERS: dict[str, str] = {
    "ka": "I",
    "na": "you",
    "a": "he/she/it",
    "i": "she",
    "ki": "we/they",
}

# Common nouns for subject/object slots (from Bible vocabulary)
COMMON_NOUNS: list[dict[str, str]] = [
    {"zo": "pasian", "en": "God"},
    {"zo": "topa", "en": "Lord"},
    {"zo": "mi", "en": "person"},
    {"zo": "numei", "en": "woman"},
    {"zo": "nupi", "en": "man"},
    {"zo": "pi", "en": "child"},
    {"zo": "sing", "en": "tree"},
    {"zo": "tui", "en": "water"},
    {"zo": "lebung", "en": "earth/land"},
    {"zo": "vantung", "en": "heaven/sky"},
    {"zo": "khuavak", "en": "light"},
    {"zo": "khuamial", "en": "darkness"},
    {"zo": "bawl", "en": "create"},
    {"zo": "tapa", "en": "fire"},
    {"zo": "gam", "en": "go/walk"},
    {"zo": "ci", "en": "say"},
    {"zo": "nek", "en": "eat"},
    {"zo": "in", "en": "name"},
    {"zo": "piang", "en": "name/call"},
    {"zo": "kumpipa", "en": "angel"},
    {"zo": "thu", "en": "word/speak"},
    {"zo": "pia", "en": "bless"},
    {"zo": "lei", "en": "come"},
    {"zo": "kia", "en": "see"},
    {"zo": "thei", "en": "know"},
    {"zo": "chang", "en": "hear"},
    {"zo": "zat", "en": "good"},
    {"zo": "hong", "en": "work"},
    {"zo": "lam", "en": "road/path"},
    {"zo": "sung", "en": "inside"},
    {"zo": "tengah", "en": "there"},
    {"zo": "kikoih", "en": "keep/put"},
    {"zo": "piangsak", "en": "created"},
    {"zo": "chuak", "en": "come out"},
    {"zo": "nuntakna", "en": "to know"},
    {"zo": "suahtakna", "en": "to fear"},
]

# Verb roots that appear in patterns
VERB_ROOTS: dict[str, str] = {
    "uh": "do/make",
    "ci": "say",
    "a": "do",
    "ahi": "do (emphatic)",
    "pia": "bless",
    "nei": "give",
    "ka": "do (1st person)",
    "na": "do (2nd person)",
    "bawl": "create",
    "thei": "know",
    "thu": "speak",
    "gam": "go",
    "lei": "come",
    "kia": "see",
    "nek": "eat",
    "chang": "hear",
    "piang": "name/call",
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load a JSONL file, returning up to *limit* records."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_grammar_patterns() -> list[dict[str, Any]]:
    """Load grammar patterns."""
    return _load_jsonl(GRAMMAR_PATH)


def load_vocabulary() -> dict[str, dict[str, Any]]:
    """Load vocabulary index keyed by word."""
    vocab: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(VOCAB_PATH):
        word = row.get("word", "").strip()
        if word:
            vocab[word] = row
    return vocab


def load_dictionary() -> dict[str, dict[str, str]]:
    """Load ZO→EN dictionary keyed by Zolai word."""
    d: dict[str, dict[str, str]] = {}
    for row in _load_jsonl(DICT_PATH):
        z = row.get("zolai", "").strip().lower()
        en = row.get("english_clean", "").strip()
        if z and en:
            d[z] = {"zolai": z, "english": en}
    return d


# ---------------------------------------------------------------------------
# Pattern classification
# ---------------------------------------------------------------------------


def classify_pattern(pattern: str) -> dict[str, Any]:
    """Classify a grammar pattern into type and components.

    Returns dict with:
      - type: "declarative", "question", "negation", "past", "future", "other"
      - has_subject: bool
      - has_object: bool
      - verb_slot: str (the verb/particle part)
      - suffix: str (the final particle)
    """
    parts = pattern.split("-")
    has_s = "S" in parts
    has_o = "O" in parts
    has_in = "in" in parts

    # Determine pattern type by suffix
    suffix = parts[-1] if parts else ""
    verb_parts = [p for p in parts if p not in ("S", "O", "in")]
    verb_slot = "-".join(verb_parts) if verb_parts else ""

    # Classify
    if suffix == "hiam" or "hiam" in parts:
        ptype = "question"
    elif suffix in ("kei", "lo") or "kei" in parts or "lo" in parts:
        ptype = "negation"
    elif "ciangin" in parts or suffix == "sak":
        ptype = "past"
    elif "ding" in parts:
        ptype = "future"
    elif suffix == "hi" or "hi" in parts:
        ptype = "declarative"
    else:
        ptype = "other"

    return {
        "type": ptype,
        "has_subject": has_s,
        "has_object": has_o,
        "has_ergative": has_in,
        "verb_slot": verb_slot,
        "suffix": suffix,
        "parts": parts,
    }


# ---------------------------------------------------------------------------
# Sentence generation
# ---------------------------------------------------------------------------


def pick_subject(rng: random.Random) -> str:
    """Pick a random subject marker."""
    markers = list(SUBJECT_MARKERS.keys())
    return rng.choice(markers)


def pick_noun(rng: random.Random, exclude: str = "") -> dict[str, str]:
    """Pick a random common noun, avoiding the excluded word."""
    candidates = [n for n in COMMON_NOUNS if n["zo"] != exclude]
    if not candidates:
        candidates = COMMON_NOUNS
    return rng.choice(candidates)


def generate_from_pattern(
    pattern: dict[str, Any],
    vocab: dict[str, dict[str, Any]],
    d: dict[str, dict[str, str]],
    rng: random.Random,
) -> dict[str, str] | None:
    """Generate a single sentence from a grammar pattern.

    Returns {zolai, english, pattern, source} or None if generation fails.
    """
    info = classify_pattern(pattern["pattern"])
    parts = info["parts"]

    subject_zo = ""
    subject_en = ""
    object_zo = ""
    object_en = ""
    verb_zo = ""
    verb_en = ""

    # Pick subject if S slot exists
    if info["has_subject"]:
        if rng.random() < 0.6:
            # Use subject marker
            sm = pick_subject(rng)
            subject_zo = sm
            subject_en = SUBJECT_MARKERS[sm]
        else:
            # Use a noun as subject
            noun = pick_noun(rng)
            subject_zo = noun["zo"]
            subject_en = noun["en"]

    # Pick object if O slot exists
    if info["has_object"]:
        noun = pick_noun(rng, exclude=subject_zo)
        object_zo = noun["zo"]
        object_en = noun["en"]

    # Determine verb/particle parts
    non_slot_parts = [p for p in parts if p not in ("S", "O")]
    verb_en_parts: list[str] = []

    for part in non_slot_parts:
        if part == "in":
            # Ergative marker - no English equivalent, skip
            continue
        elif part in SUBJECT_MARKERS:
            # This is a subject pronoun (e.g., S-in-O-ka-hi → ka is the verb slot person)
            if not subject_zo:
                subject_zo = part
                subject_en = SUBJECT_MARKERS[part]
        elif part in VERB_ROOTS:
            verb_zo = part
            verb_en_parts.append(VERB_ROOTS[part])
        elif part in ("hi", "hiam"):
            # Sentence-final particles
            continue
        elif part == "ding":
            verb_en_parts.insert(0, "will")
        elif part == "ciangin":
            verb_en_parts.insert(0, "did/was")
        elif part == "sak":
            verb_en_parts.append("(completed)")
        elif part == "ah":
            verb_en_parts.append("(ongoing)")
        elif part == "hen":
            verb_en_parts.append("(finished)")
        elif part == "nak":
            verb_en_parts.append("(nominalized)")
        elif part == "kei":
            verb_en_parts.insert(0, "do not")
        elif part == "lo":
            verb_en_parts.insert(0, "does not")
        elif part == "leh":
            verb_en_parts.append("and then")
        elif part == "pia":
            if not verb_zo:
                verb_zo = "pia"
                verb_en_parts.append("bless")
        elif part == "nei":
            if not verb_zo:
                verb_zo = "nei"
                verb_en_parts.append("give")
        elif part == "ci":
            if not verb_zo:
                verb_zo = "ci"
                verb_en_parts.append("say")
        elif part == "thei":
            if not verb_zo:
                verb_zo = "thei"
                verb_en_parts.append("know")
        elif part == "bawl":
            if not verb_zo:
                verb_zo = "bawl"
                verb_en_parts.append("create")
        elif part == "thu":
            if not verb_zo:
                verb_zo = "thu"
                verb_en_parts.append("speak")
        elif part in ("amah", "amaute", "ciangin"):
            # Past tense forms
            if "did" not in " ".join(verb_en_parts):
                verb_en_parts.insert(0, "did")
        else:
            # Unknown part - look it up
            if part in vocab:
                trans_list = vocab[part].get("translations", [])
                if trans_list:
                    t = str(trans_list[0]).split("/")[0].strip()
                    verb_en_parts.append(t)
            elif part.lower() in d:
                verb_en_parts.append(d[part.lower()]["english"])

    # Build the Zolai sentence
    zo_parts: list[str] = []
    if subject_zo:
        zo_parts.append(subject_zo)
    if info["has_ergative"]:
        zo_parts.append("in")
    if object_zo:
        zo_parts.append(object_zo)
    if verb_zo:
        zo_parts.append(verb_zo)
    # Add remaining non-slot parts that aren't already included
    for part in non_slot_parts:
        if part not in ("in", subject_zo, object_zo, verb_zo) and part not in (
            "hi", "hiam", "kei", "lo", "ding", "ciangin", "sak", "ah", "hen",
            "nak", "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
            "amah", "amaute",
        ) and part not in SUBJECT_MARKERS:
            if part not in zo_parts:
                zo_parts.append(part)

    # Add final particle
    if info["suffix"] in ("hi", "hiam", "kei", "lo"):
        zo_parts.append(info["suffix"])

    zolai = " ".join(zo_parts)

    # Build English translation
    if subject_en:
        en_parts = [subject_en]
    else:
        en_parts = []

    if object_en:
        en_parts.append(object_en)

    en_parts.extend(verb_en_parts)

    # Add question marker
    if info["type"] == "question":
        en_parts.append("?")
    else:
        en_parts.append(".")

    english = " ".join(en_parts)

    # Capitalize first letter
    if english:
        english = english[0].upper() + english[1:]

    # Clean up
    english = english.replace("  ", " ").strip()
    if english.endswith(" ."):
        english = english[:-2] + "."
    if english.endswith(" ?"):
        english = english[:-2] + "?"

    if not zolai.strip():
        return None

    return {
        "zolai": zolai,
        "english": english,
        "pattern": pattern["pattern"],
        "source": "generated",
    }


# ---------------------------------------------------------------------------
# Main generation pipeline
# ---------------------------------------------------------------------------


def generate_sentences(
    max_sentences: int = 5000,
    seed: int = 42,
    verbose: bool = True,
) -> list[dict[str, str]]:
    """Generate Zolai sentences from grammar patterns + vocabulary.

    Args:
        max_sentences: Maximum number of sentences to generate.
        seed: Random seed for reproducibility.
        verbose: Print progress.

    Returns:
        List of sentence dicts with zolai, english, pattern, source.
    """
    rng = random.Random(seed)

    if verbose:
        print("Loading grammar patterns...")
    patterns = load_grammar_patterns()
    if verbose:
        print(f"  Loaded {len(patterns)} patterns")

    if verbose:
        print("Loading vocabulary...")
    vocab = load_vocabulary()
    if verbose:
        print(f"  Loaded {len(vocab)} words")

    if verbose:
        print("Loading dictionary...")
    d = load_dictionary()
    if verbose:
        print(f"  Loaded {len(d)} dictionary entries")

    # Weight patterns by frequency
    total_freq = sum(p.get("frequency", 1) for p in patterns)
    weights = [p.get("frequency", 1) / total_freq for p in patterns]

    # Filter patterns that have S or O slots (can generate sentences)
    generable = [p for p in patterns if "S" in p["pattern"] or "O" in p["pattern"]]
    if verbose:
        print(f"  {len(generable)} patterns with S/O slots (out of {len(patterns)})")

    if not generable:
        generable = patterns  # fallback to all patterns

    # Generate sentences
    sentences: list[dict[str, str]] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = max_sentences * 5  # allow 5x attempts for dedup

    while len(sentences) < max_sentences and attempts < max_attempts:
        attempts += 1

        # Pick a pattern weighted by frequency
        pattern = rng.choices(generable, weights=[p.get("frequency", 1) for p in generable])[0]

        result = generate_from_pattern(pattern, vocab, d, rng)
        if result is None:
            continue

        # Dedup by Zolai sentence
        key = result["zolai"].lower().strip()
        if key in seen:
            continue
        seen.add(key)

        sentences.append(result)

        if verbose and len(sentences) % 500 == 0:
            print(f"  Generated {len(sentences)}/{max_sentences} sentences...")

    if verbose:
        print(f"  Done: {len(sentences)} unique sentences from {attempts} attempts")

    return sentences


def save_sentences(sentences: list[dict[str, str]], output_path: Path) -> None:
    """Save sentences to JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in sentences)
    print(f"  Saved {len(sentences)} sentences to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Zolai sentences from grammar patterns + dictionary."
    )
    parser.add_argument(
        "--max-sentences",
        type=int,
        default=5000,
        help="Maximum number of sentences to generate (default: 5000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(WORKSPACE / "data/training/generated_sentences.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    print("=" * 60)
    print("  Zolai Sentence Generator")
    print("  Grammar patterns + Dictionary vocabulary")
    print("=" * 60)
    print()

    sentences = generate_sentences(
        max_sentences=args.max_sentences,
        seed=args.seed,
        verbose=not args.quiet,
    )

    save_sentences(sentences, output_path)

    # Print sample
    print()
    print("Sample sentences:")
    rng = random.Random(99)
    for s in rng.sample(sentences, min(10, len(sentences))):
        print(f"  {s['zolai']:40s} → {s['english']:40s}  [{s['pattern']}]")

    # Stats
    types: dict[str, int] = {}
    for s in sentences:
        t = classify_pattern(s["pattern"])["type"]
        types[t] = types.get(t, 0) + 1

    print()
    print("Pattern type distribution:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:15s} {c:6d} ({c * 100 // len(sentences)}%)")


if __name__ == "__main__":
    main()
