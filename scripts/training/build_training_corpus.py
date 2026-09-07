#!/usr/bin/env python3
"""Full training corpus pipeline: generate -> validate -> correct -> export.

Uses the Bible-template generator (generate_sentences.py) and deep
validator (deep_validate.py) for high-quality sentence generation.

Orchestrates the entire training data generation pipeline:
  Step 1: Generate sentences from Bible templates + semantic variation
  Step 2: Deep-validate (6 checks against real data sources)
  Step 3: Auto-correct invalid sentences (ZVS + proper nouns)
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
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent

# Add scripts dir to path for sibling imports
sys.path.insert(0, str(SCRIPTS_DIR))

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
    "- pathian -> pasian (God)\n"
    "- ram -> gam (earth)\n"
    "- fapa -> tapa (fire)\n"
    "- bawipa -> topa (lord)\n"
    "- siangpahrang -> kumpipa (angel)\n"
    "- cu/cun -> tua\n"
    "- suah -> chuak\n"
    "- zalenna -> suahtakna\n"
    "- nunnak -> nuntakna\n\n"
    "Respond only in the requested language. "
    "For translations, give the single best translation on the first line, "
    "then optionally a brief grammar note on the second line."
)

# ZVS corrections (used by fix_zvs_forms)
ZVS_CORRECTIONS: dict[str, str] = {
    "pathian": "pasian", "ram": "gam", "fapa": "tapa",
    "bawipa": "topa", "siangpahrang": "kumpipa",
    "cu": "tua", "cun": "tua", "suah": "chuak",
    "zalenna": "suahtakna", "nunnak": "nuntakna",
}

# Proper nouns for English capitalisation (used by fix_proper_nouns_en)
PROPER_NOUNS_EN: dict[str, str] = {
    "pasian": "Pasian", "topa": "Topa", "vantung": "Vantung",
    "kumpipa": "Kumpipa", "jesuh": "Jesuh", "david": "David",
    "israel": "Israel", "adam": "Adam", "noah": "Noah",
    "abraham": "Abraham", "moses": "Moses", "joshua": "Joshua",
    "solomon": "Solomon", "paul": "Paul", "peter": "Peter",
    "john": "John", "matthew": "Matthew", "luke": "Luke",
}

# Valid verb endings (used by correct_sentence for missing-verb detection)
VALID_VERB_ENDINGS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute",
})


# ---------------------------------------------------------------------------
# Import Bible-template generator and deep validator
# ---------------------------------------------------------------------------

from generate_sentences import generate_sentences
from deep_validate import DeepValidator


# ---------------------------------------------------------------------------
# Step 1: Generate sentences (Bible templates)
# ---------------------------------------------------------------------------


def step_generate(
    max_sentences: int, seed: int, verbose: bool,
) -> list[dict[str, str]]:
    """Step 1: Generate sentences from Bible templates."""
    if verbose:
        print("  Step 1: Generating sentences from Bible templates...")
    sentences = generate_sentences(
        max_sentences=max_sentences, seed=seed, verbose=verbose,
    )
    if verbose:
        print(f"    Generated {len(sentences)} sentences")
    return sentences


# ---------------------------------------------------------------------------
# Step 2: Deep validation
# ---------------------------------------------------------------------------


def step_validate(
    sentences: list[dict[str, str]], min_score: int, verbose: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Step 2: Validate sentences with deep validator (6 checks)."""
    if verbose:
        print(f"  Step 2: Deep-validating {len(sentences)} sentences...")
    validator = DeepValidator(verbose=verbose)
    results = validator.validate_batch(sentences)
    valid = [r for r in results if r["deep_score"] >= min_score]
    invalid = [r for r in results if r["deep_score"] < min_score]
    if verbose:
        print(f"    Valid: {len(valid)} ({len(valid) * 100 // max(len(sentences), 1)}%)")
        print(f"    Invalid: {len(invalid)}")
    return valid, invalid


# ---------------------------------------------------------------------------
# Step 3: Correct (ZVS + proper nouns)
# ---------------------------------------------------------------------------


def fix_zvs_forms(text: str) -> tuple[str, list[dict[str, str]]]:
    """Replace ZVS 2018 forbidden forms with correct equivalents."""
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
    """Capitalise proper nouns in English text."""
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
    """Apply ZVS and proper-noun corrections to a sentence."""
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
# Step 4: Re-validate (deep validator)
# ---------------------------------------------------------------------------


def step_revalidate(
    corrected: list[dict[str, Any]], min_score: int, verbose: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Step 4: Re-validate corrected sentences with deep validator."""
    if verbose:
        print(f"  Step 4: Re-validating {len(corrected)} corrected sentences...")
    validator = DeepValidator(verbose=False)  # suppress loader output on re-run
    results = validator.validate_batch(corrected)
    valid: list[dict[str, Any]] = []
    still_invalid: list[dict[str, Any]] = []
    for r in results:
        if r["deep_score"] >= min_score:
            valid.append(r)
        else:
            still_invalid.append(r)
    if verbose:
        print(f"    Now valid: {len(valid)}")
        print(f"    Still invalid: {len(still_invalid)}")
    return valid, still_invalid


# ---------------------------------------------------------------------------
# Step 5: Export to Qwen3 format (unchanged)
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
        # Type 1: Zolai -> English translation
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

        # Type 2: English -> Zolai translation
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
    print("  TRAINING CORPUS PIPELINE (Bible-template + Deep Validator)")
    print("  generate -> validate -> correct -> re-validate -> export")
    print("=" * 60)
    print()

    # Step 1: Generate
    sentences = step_generate(max_sentences, seed, verbose)
    print()

    # Step 2: Deep-validate
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

    # Print final summary with deep_validate breakdown
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Generated:    {stats['generated']:>8,}")
    print(f"  Valid (v1):   {stats['valid_after_validate']:>8,}")
    print(f"  Invalid:      {stats['invalid_after_validate']:>8,}")
    print(f"  Corrected:    {stats['corrected']:>8,}")
    print(f"  Valid (v2):   {stats['valid_after_revalidate']:>8,}")
    print(f"  Still invalid:{stats['still_invalid']:>8,}")
    print("  ---")
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
        description="Full training corpus pipeline: generate -> validate -> correct -> export."
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
        help="Minimum deep validation score (default: 70)",
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
