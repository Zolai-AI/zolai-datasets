#!/usr/bin/env python3
"""Full training corpus pipeline: generate → validate → correct → export.

Orchestrates the entire training data generation pipeline:
  Step 1: Generate sentences from grammar patterns + dictionary
  Step 2: Validate (grammar + ZVS 2018)
  Step 3: Auto-correct invalid sentences
  Step 4: Re-validate after correction
  Step 5: Export final valid sentences to Qwen3 chat template format

Usage:
    python build_training_corpus.py
    python build_training_corpus.py --max-sentences 10000 --seed 123
    python build_training_corpus.py --output-dir data/training/pipeline_output
"""

from __future__ import annotations

import argparse
import json
import random
import time
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
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a Tedim Zolai (Zomi) language expert. "
    "You follow ZVS 2018 orthography strictly.\n\n"
    "Grammar rules:\n"
    "- Word order is SOV (Subject-Object-Verb).\n"
    "- Use 'hiam' for yes/no questions (not 'ze').\n"
    "- Use 'bang hang' or 'kua' for content questions.\n"
    "- 1st/2nd person negation: 'kei'. 3rd person negation: 'lo'.\n"
    "- Ergative marker: 'in' for transitive subjects.\n"
    "- Tense: -sak (past), -ah (progressive), -hen (completive), ding (future).\n\n"
    "Forbidden forms (use ZVS 2018 equivalents):\n"
    "- pathian → pasian (God)\n"
    "- ram → gam (earth)\n"
    "- fapa → tapa (fire)\n"
    "- bawipa → topa (lord)\n"
    "- siangpahrang → kumpipa (angel)\n"
    "- cu/cun → tua\n"
    "- suah → chuak\n"
    "- zalenna → suahtakna\n"
    "- nunnak → nuntakna\n\n"
    "Respond only in the requested language. "
    "For translations, give the single best translation on the first line, "
    "then optionally a brief grammar note on the second line."
)

# ZVS corrections
ZVS_CORRECTIONS: dict[str, str] = {
    "pathian": "pasian", "ram": "gam", "fapa": "tapa",
    "bawipa": "topa", "siangpahrang": "kumpipa",
    "cu": "tua", "cun": "tua", "suah": "chuak",
    "zalenna": "suahtakna", "nunnak": "nuntakna",
}

# Subject markers
SUBJECT_MARKERS: dict[str, str] = {
    "ka": "I", "na": "you", "a": "he/she/it", "i": "she", "ki": "we/they",
}

# Common nouns
COMMON_NOUNS: list[dict[str, str]] = [
    {"zo": "pasian", "en": "God"}, {"zo": "topa", "en": "Lord"},
    {"zo": "mi", "en": "person"}, {"zo": "numei", "en": "woman"},
    {"zo": "nupi", "en": "man"}, {"zo": "pi", "en": "child"},
    {"zo": "sing", "en": "tree"}, {"zo": "tui", "en": "water"},
    {"zo": "lebung", "en": "earth"}, {"zo": "vantung", "en": "heaven"},
    {"zo": "khuavak", "en": "light"}, {"zo": "khuamial", "en": "darkness"},
    {"zo": "tapa", "en": "fire"}, {"zo": "gam", "en": "go/walk"},
    {"zo": "ci", "en": "say"}, {"zo": "nek", "en": "eat"},
    {"zo": "kumpipa", "en": "angel"}, {"zo": "thu", "en": "word"},
    {"zo": "pia", "en": "bless"}, {"zo": "lei", "en": "come"},
    {"zo": "kia", "en": "see"}, {"zo": "thei", "en": "know"},
    {"zo": "chang", "en": "hear"}, {"zo": "lam", "en": "road"},
    {"zo": "sung", "en": "inside"}, {"zo": "tengah", "en": "there"},
]

# Verb roots
VERB_ROOTS: dict[str, str] = {
    "uh": "do/make", "ci": "say", "a": "do", "ahi": "do (emphatic)",
    "pia": "bless", "nei": "give", "bawl": "create", "thei": "know",
    "thu": "speak", "gam": "go", "lei": "come", "kia": "see",
    "nek": "eat", "chang": "hear", "piang": "name",
}

# Valid verb endings
VALID_VERB_ENDINGS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute",
})

# Proper nouns
PROPER_NOUNS_EN: dict[str, str] = {
    "pasian": "Pasian", "topa": "Topa", "vantung": "Vantung",
    "kumpipa": "Kumpipa", "jesuh": "Jesuh", "david": "David",
    "israel": "Israel", "adam": "Adam", "noah": "Noah",
    "abraham": "Abraham", "moses": "Moses", "joshua": "Joshua",
    "solomon": "Solomon", "paul": "Paul", "peter": "Peter",
    "john": "John", "matthew": "Matthew", "luke": "Luke",
}

# ---------------------------------------------------------------------------
# Data loading (inline to avoid import issues)
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Step 1: Generate sentences (inline)
# ---------------------------------------------------------------------------


def classify_pattern(pattern: str) -> dict[str, Any]:
    parts = pattern.split("-")
    has_s = "S" in parts
    has_o = "O" in parts
    has_in = "in" in parts
    suffix = parts[-1] if parts else ""
    verb_parts = [p for p in parts if p not in ("S", "O", "in")]
    verb_slot = "-".join(verb_parts) if verb_parts else ""

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
        "type": ptype, "has_subject": has_s, "has_object": has_o,
        "has_ergative": has_in, "verb_slot": verb_slot,
        "suffix": suffix, "parts": parts,
    }


def generate_from_pattern(
    pattern: dict[str, Any], rng: random.Random,
) -> dict[str, str] | None:
    info = classify_pattern(pattern["pattern"])
    parts = info["parts"]
    subject_zo = ""
    subject_en = ""
    object_zo = ""
    object_en = ""
    verb_zo = ""
    verb_en_parts: list[str] = []

    if info["has_subject"]:
        if rng.random() < 0.6:
            sm = rng.choice(list(SUBJECT_MARKERS.keys()))
            subject_zo = sm
            subject_en = SUBJECT_MARKERS[sm]
        else:
            noun = rng.choice(COMMON_NOUNS)
            subject_zo = noun["zo"]
            subject_en = noun["en"]

    if info["has_object"]:
        candidates = [n for n in COMMON_NOUNS if n["zo"] != subject_zo]
        noun = rng.choice(candidates or COMMON_NOUNS)
        object_zo = noun["zo"]
        object_en = noun["en"]

    non_slot = [p for p in parts if p not in ("S", "O")]
    for part in non_slot:
        if part == "in":
            continue
        elif part in SUBJECT_MARKERS:
            if not subject_zo:
                subject_zo = part
                subject_en = SUBJECT_MARKERS[part]
        elif part in VERB_ROOTS:
            verb_zo = part
            verb_en_parts.append(VERB_ROOTS[part])
        elif part in ("hi", "hiam"):
            continue
        elif part == "ding":
            verb_en_parts.insert(0, "will")
        elif part == "ciangin":
            verb_en_parts.insert(0, "did")
        elif part == "sak":
            verb_en_parts.append("(completed)")
        elif part == "ah":
            verb_en_parts.append("(ongoing)")
        elif part == "hen":
            verb_en_parts.append("(finished)")
        elif part == "kei":
            verb_en_parts.insert(0, "do not")
        elif part == "lo":
            verb_en_parts.insert(0, "does not")
        elif part == "leh":
            verb_en_parts.append("and then")
        elif part in ("amah", "amaute"):
            if "did" not in " ".join(verb_en_parts):
                verb_en_parts.insert(0, "did")
        elif part in ("pia", "nei", "ci", "thei", "bawl", "thu"):
            if not verb_zo:
                verb_zo = part
                verb_en_parts.append(VERB_ROOTS.get(part, part))

    # Build Zolai
    zo_parts: list[str] = []
    if subject_zo:
        zo_parts.append(subject_zo)
    if info["has_ergative"]:
        zo_parts.append("in")
    if object_zo:
        zo_parts.append(object_zo)
    if verb_zo:
        zo_parts.append(verb_zo)
    for part in non_slot:
        if part not in ("in", subject_zo, object_zo, verb_zo) and part not in (
            "hi", "hiam", "kei", "lo", "ding", "ciangin", "sak", "ah",
            "hen", "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
            "amah", "amaute",
        ) and part not in SUBJECT_MARKERS:
            if part not in zo_parts:
                zo_parts.append(part)
    if info["suffix"] in ("hi", "hiam", "kei", "lo"):
        zo_parts.append(info["suffix"])
    zolai = " ".join(zo_parts)

    # Build English
    en_parts: list[str] = []
    if subject_en:
        en_parts.append(subject_en)
    if object_en:
        en_parts.append(object_en)
    en_parts.extend(verb_en_parts)
    if info["type"] == "question":
        en_parts.append("?")
    else:
        en_parts.append(".")
    english = " ".join(en_parts)
    if english:
        english = english[0].upper() + english[1:]
    english = english.replace("  ", " ").strip()
    english = english.rstrip(" .") + ("?" if info["type"] == "question" else ".")

    if not zolai.strip():
        return None
    return {"zolai": zolai, "english": english, "pattern": pattern["pattern"], "source": "generated"}


def step_generate(max_sentences: int, seed: int, verbose: bool) -> list[dict[str, str]]:
    """Step 1: Generate sentences."""
    if verbose:
        print("  Step 1: Loading grammar patterns + vocabulary...")
    patterns = _load_jsonl(GRAMMAR_PATH)
    generable = [p for p in patterns if "S" in p["pattern"] or "O" in p["pattern"]]
    if not generable:
        generable = patterns
    if verbose:
        print(f"    {len(generable)} generable patterns from {len(patterns)} total")

    rng = random.Random(seed)
    sentences: list[dict[str, str]] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = max_sentences * 5

    while len(sentences) < max_sentences and attempts < max_attempts:
        attempts += 1
        pattern = rng.choices(generable, weights=[p.get("frequency", 1) for p in generable])[0]
        result = generate_from_pattern(pattern, rng)
        if result is None:
            continue
        key = result["zolai"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(result)
        if verbose and len(sentences) % 1000 == 0:
            print(f"    Generated {len(sentences)}/{max_sentences}...")

    if verbose:
        print(f"    Done: {len(sentences)} sentences ({attempts} attempts)")
    return sentences


# ---------------------------------------------------------------------------
# Step 2: Validate (inline)
# ---------------------------------------------------------------------------


def check_zvs_compliance(text: str) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for word in text.lower().split():
        clean = word.strip(".,;:!?\"'()[]{}")
        if clean in ZVS_CORRECTIONS:
            violations.append({"form": clean, "correct": ZVS_CORRECTIONS[clean]})
    return violations


def score_sentence(zolai: str, english: str) -> int:
    score = 100
    zvs = check_zvs_compliance(zolai)
    if zvs:
        score -= min(40, len(zvs) * 20)
    en_zvs = check_zvs_compliance(english)
    if en_zvs:
        score -= 10
    words = zolai.split()
    has_verb = any(w in VALID_VERB_ENDINGS for w in words)
    if not has_verb:
        score -= 15
    has_subject = any(w in SUBJECT_MARKERS or w == "in" for w in words)
    if not has_subject:
        score -= 15
    if len(words) < 2:
        score -= 10
    if not english or len(english.split()) < 2:
        score -= 5
    return max(0, min(100, score))


def step_validate(
    sentences: list[dict[str, str]], min_score: int, verbose: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Step 2: Validate sentences."""
    if verbose:
        print(f"  Step 2: Validating {len(sentences)} sentences...")
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for s in sentences:
        score = score_sentence(s.get("zolai", ""), s.get("english", ""))
        entry = {**s, "score": score}
        if score >= min_score:
            valid.append(entry)
        else:
            invalid.append(entry)
    if verbose:
        print(f"    Valid: {len(valid)} ({len(valid) * 100 // max(len(sentences), 1)}%)")
        print(f"    Invalid: {len(invalid)}")
    return valid, invalid


# ---------------------------------------------------------------------------
# Step 3: Correct (inline)
# ---------------------------------------------------------------------------


def fix_zvs_forms(text: str) -> tuple[str, list[dict[str, str]]]:
    corrections: list[dict[str, str]] = []
    words = text.split()
    new_words: list[str] = []
    for word in words:
        clean = word.strip(".,;:!?\"'()[]{}")
        prefix = word[: len(word) - len(word.lstrip(".,;:!?\"'()[]{}"))]
        suffix = word[len(word.rstrip(".,;:!?\"'()[]{}")) :]
        if clean.lower() in ZVS_CORRECTIONS:
            correct = ZVS_CORRECTIONS[clean.lower()]
            if clean and clean[0].isupper():
                correct = correct[0].upper() + correct[1:]
            new_words.append(prefix + correct + suffix)
            corrections.append({"type": "zvs", "from": clean, "to": correct})
        else:
            new_words.append(word)
    return " ".join(new_words), corrections


def fix_proper_nouns_en(text: str) -> tuple[str, list[dict[str, str]]]:
    corrections: list[dict[str, str]] = []
    words = text.split()
    new_words: list[str] = []
    for word in words:
        clean = word.lower().strip(".,;:!?\"'()[]{}")
        if clean in PROPER_NOUNS_EN:
            correct = PROPER_NOUNS_EN[clean]
            new_words.append(correct)
            if word != correct:
                corrections.append({"type": "proper_noun", "from": word, "to": correct})
        else:
            new_words.append(word)
    return " ".join(new_words), corrections


def correct_sentence(entry: dict[str, Any]) -> dict[str, Any]:
    zolai = entry.get("zolai", "")
    english = entry.get("english", "")
    all_corr: list[dict[str, str]] = []

    zolai, c = fix_zvs_forms(zolai)
    all_corr.extend(c)
    english, c = fix_zvs_forms(english)
    all_corr.extend(c)
    english, c = fix_proper_nouns_en(english)
    all_corr.extend(c)

    # Fix duplicate particles
    words = zolai.split()
    if len(words) >= 2:
        new_words = [words[0]]
        for w in words[1:]:
            if w != new_words[-1]:
                new_words.append(w)
            else:
                all_corr.append({"type": "duplicate", "from": w, "to": ""})
        zolai = " ".join(new_words)

    # Fix missing verb ending
    words = zolai.split()
    if words and words[-1].lower() not in VALID_VERB_ENDINGS:
        words.append("hi")
        all_corr.append({"type": "missing_verb", "from": "", "to": "hi"})
        zolai = " ".join(words)

    result = dict(entry)
    result["zolai"] = zolai
    result["english"] = english
    result["corrections"] = all_corr
    result["corrected"] = len(all_corr) > 0
    return result


def step_correct(
    invalid: list[dict[str, Any]], verbose: bool,
) -> list[dict[str, Any]]:
    """Step 3: Auto-correct invalid sentences."""
    if verbose:
        print(f"  Step 3: Correcting {len(invalid)} invalid sentences...")
    corrected: list[dict[str, Any]] = []
    fix_count = 0
    for s in invalid:
        result = correct_sentence(s)
        corrected.append(result)
        if result["corrected"]:
            fix_count += 1
    if verbose:
        print(f"    Corrected: {fix_count}/{len(invalid)}")
    return corrected


# ---------------------------------------------------------------------------
# Step 4: Re-validate (inline)
# ---------------------------------------------------------------------------


def step_revalidate(
    corrected: list[dict[str, Any]], min_score: int, verbose: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Step 4: Re-validate corrected sentences."""
    if verbose:
        print(f"  Step 4: Re-validating {len(corrected)} corrected sentences...")
    valid: list[dict[str, Any]] = []
    still_invalid: list[dict[str, Any]] = []
    for s in corrected:
        score = score_sentence(s.get("zolai", ""), s.get("english", ""))
        s["score"] = score
        if score >= min_score:
            valid.append(s)
        else:
            still_invalid.append(s)
    if verbose:
        print(f"    Now valid: {len(valid)}")
        print(f"    Still invalid: {len(still_invalid)}")
    return valid, still_invalid


# ---------------------------------------------------------------------------
# Step 5: Export to Qwen3 format (inline)
# ---------------------------------------------------------------------------


def step_export(
    valid: list[dict[str, Any]], output_dir: Path, verbose: bool,
) -> dict[str, Any]:
    """Step 5: Export to Qwen3 chat template format."""
    if verbose:
        print(f"  Step 5: Exporting {len(valid)} sentences to Qwen3 format...")

    chat_messages: list[dict[str, Any]] = []
    for s in valid:
        zolai = s.get("zolai", "")
        english = s.get("english", "")
        pattern = s.get("pattern", "")
        source = s.get("source", "generated")

        # Build different task types
        # Type 1: Zolai → English translation
        user_msg = (
            f"Translate the following Tedim Zolai sentence into English.\n\n"
            f"Zolai: {zolai}"
        )
        assistant_msg = english
        chat_messages.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
            "task": "translation_zo_en",
            "pattern": pattern,
            "source": source,
        })

        # Type 2: English → Zolai translation
        user_msg2 = (
            f"Translate the following English sentence into Tedim Zolai.\n\n"
            f"English: {english}"
        )
        assistant_msg2 = zolai
        chat_messages.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg2},
                {"role": "assistant", "content": assistant_msg2},
            ],
            "task": "translation_en_zo",
            "pattern": pattern,
            "source": source,
        })

    # Save to JSONL
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "training_corpus_qwen3.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(msg, ensure_ascii=False) + "\n" for msg in chat_messages)

    if verbose:
        print(f"    Saved {len(chat_messages)} chat messages to {output_path}")

    # Also save raw valid sentences
    raw_path = output_dir / "valid_sentences.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for s in valid:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    return {
        "chat_messages": len(chat_messages),
        "raw_sentences": len(valid),
        "output_path": str(output_path),
        "raw_path": str(raw_path),
    }


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    max_sentences: int = 5000,
    output_dir: Path | None = None,
    seed: int = 42,
    min_score: int = 70,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the full training corpus pipeline.

    Returns summary stats.
    """
    if output_dir is None:
        output_dir = WORKSPACE / "data/training/pipeline_output"

    start_time = time.time()

    print()
    print("=" * 60)
    print("  TRAINING CORPUS PIPELINE")
    print("  generate → validate → correct → re-validate → export")
    print("=" * 60)
    print()

    # Step 1: Generate
    sentences = step_generate(max_sentences, seed, verbose)
    print()

    # Step 2: Validate
    valid_v1, invalid = step_validate(sentences, min_score, verbose)
    print()

    # Step 3: Correct
    corrected = step_correct(invalid, verbose)
    print()

    # Step 4: Re-validate
    valid_v2, still_invalid = step_revalidate(corrected, min_score, verbose)
    print()

    # Combine valid from step 2 and step 4
    all_valid = valid_v1 + valid_v2
    print(f"  Combined valid: {len(all_valid)} (step2: {len(valid_v1)} + step4: {len(valid_v2)})")
    print()

    # Step 5: Export
    export_stats = step_export(all_valid, output_dir, verbose)
    print()

    elapsed = time.time() - start_time

    # Save pipeline stats
    stats = {
        "max_sentences": max_sentences,
        "seed": seed,
        "min_score": min_score,
        "generated": len(sentences),
        "valid_after_validate": len(valid_v1),
        "invalid_after_validate": len(invalid),
        "corrected": sum(1 for s in corrected if s.get("corrected")),
        "valid_after_revalidate": len(valid_v2),
        "still_invalid": len(still_invalid),
        "final_valid": len(all_valid),
        "final_chat_messages": export_stats["chat_messages"],
        "output_path": export_stats["output_path"],
        "elapsed_seconds": round(elapsed, 2),
    }

    # Save stats
    stats_path = output_dir / "pipeline_stats.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Print final summary
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Generated:    {stats['generated']:>8,}")
    print(f"  Valid (v1):   {stats['valid_after_validate']:>8,}")
    print(f"  Invalid:      {stats['invalid_after_validate']:>8,}")
    print(f"  Corrected:    {stats['corrected']:>8,}")
    print(f"  Valid (v2):   {stats['valid_after_revalidate']:>8,}")
    print(f"  Still invalid:{stats['still_invalid']:>8,}")
    print("  ─────────────────────────────")
    print(f"  Final valid:  {stats['final_valid']:>8,}")
    print(f"  Chat messages:{stats['final_chat_messages']:>8,}")
    print(f"  Time:         {stats['elapsed_seconds']:>8.1f}s")
    print()
    print(f"  Output dir: {output_dir}")
    print(f"  Stats:      {stats_path}")
    print()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Full training corpus pipeline: generate → validate → correct → export."
    )
    parser.add_argument(
        "--max-sentences", type=int, default=5000,
        help="Maximum sentences to generate (default: 5000)",
    )
    parser.add_argument(
        "--output-dir", type=str,
        default=str(WORKSPACE / "data/training/pipeline_output"),
        help="Output directory for all pipeline artifacts",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--min-score", type=int, default=70,
        help="Minimum validation score (default: 70)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    run_pipeline(
        max_sentences=args.max_sentences,
        output_dir=Path(args.output_dir),
        seed=args.seed,
        min_score=args.min_score,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
