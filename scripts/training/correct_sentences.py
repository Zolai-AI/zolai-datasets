#!/usr/bin/env python3
"""Auto-fix invalid Zolai sentences.

Fixes:
  1. ZVS 2018 forbidden forms (replace with correct forms)
  2. Capitalization of proper nouns
  3. Common particle issues
  4. Duplicate/missing particles

Reports how many were corrected and what corrections were made.

Usage:
    python correct_sentences.py --input data/training/validated/invalid.jsonl
    python correct_sentences.py --input data/training/validated/invalid.jsonl --report report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]

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

# Proper nouns that should be capitalized in English
PROPER_NOUNS_EN: dict[str, str] = {
    "pasian": "Pasian",
    "topa": "Topa",
    "vantung": "Vantung",
    "kumpipa": "Kumpipa",
    "jesuh": "Jesuh",
    "david": "David",
    "israel": "Israel",
    "adam": "Adam",
    "seth": "Seth",
    "enosh": "Enosh",
    "kenan": "Kenan",
    "noah": "Noah",
    "abraham": "Abraham",
    "isaac": "Isaac",
    "jacob": "Jacob",
    "moses": "Moses",
    "aaron": "Aaron",
    "joshua": "Joshua",
    "samuel": "Samuel",
    "solomon": "Solomon",
    "elijah": "Elijah",
    "isaiah": "Isaiah",
    "jeremiah": "Jeremiah",
    "daniel": "Daniel",
    "paul": "Paul",
    "peter": "Peter",
    "john": "John",
    "matthew": "Matthew",
    "luke": "Luke",
    "mark": "Mark",
}

# Valid verb endings
VALID_VERB_ENDINGS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute",
})

# Valid subject markers
VALID_SUBJECT_MARKERS = frozenset({"ka", "na", "a", "i", "ki"})

# ---------------------------------------------------------------------------
# Correction functions
# ---------------------------------------------------------------------------


def fix_zvs_forms(text: str) -> tuple[str, list[dict[str, str]]]:
    """Replace ZVS forbidden forms with correct forms.

    Returns (corrected_text, list of corrections made).
    """
    corrections: list[dict[str, str]] = []
    words = text.split()
    new_words: list[str] = []

    for word in words:
        # Strip punctuation for matching
        clean = word.strip(".,;:!?\"'()[]{}")
        prefix = word[: len(word) - len(word.lstrip(".,;:!?\"'()[]{}"))]
        suffix = word[len(word.rstrip(".,;:!?\"'()[]{}")) :]

        if clean.lower() in ZVS_CORRECTIONS:
            correct = ZVS_CORRECTIONS[clean.lower()]
            # Preserve case
            if clean[0].isupper():
                correct = correct[0].upper() + correct[1:]
            new_word = prefix + correct + suffix
            new_words.append(new_word)
            if new_word != word:
                corrections.append({
                    "type": "zvs_form",
                    "from": clean,
                    "to": correct,
                    "context": text,
                })
        else:
            new_words.append(word)

    return " ".join(new_words), corrections


def fix_proper_nouns_en(text: str) -> tuple[str, list[dict[str, str]]]:
    """Capitalize proper nouns in English text.

    Returns (corrected_text, list of corrections made).
    """
    corrections: list[dict[str, str]] = []
    words = text.split()
    new_words: list[str] = []

    for word in words:
        clean = word.lower().strip(".,;:!?\"'()[]{}")
        if clean in PROPER_NOUNS_EN:
            correct = PROPER_NOUNS_EN[clean]
            if word != correct:
                new_words.append(correct)
                corrections.append({
                    "type": "proper_noun",
                    "from": word,
                    "to": correct,
                })
            else:
                new_words.append(word)
        else:
            new_words.append(word)

    return " ".join(new_words), corrections


def fix_duplicate_particles(text: str) -> tuple[str, list[dict[str, str]]]:
    """Remove duplicate consecutive particles.

    Returns (corrected_text, list of corrections made).
    """
    corrections: list[dict[str, str]] = []
    words = text.split()
    if len(words) < 2:
        return text, corrections

    new_words: list[str] = [words[0]]
    for word in words[1:]:
        if word == new_words[-1]:
            corrections.append({
                "type": "duplicate_particle",
                "from": f"{word} {word}",
                "to": word,
            })
            continue
        new_words.append(word)

    return " ".join(new_words), corrections


def fix_missing_verb_ending(words: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Add a verb ending if missing.

    Returns (corrected_words, list of corrections made).
    """
    corrections: list[dict[str, str]] = []
    if not words:
        return words, corrections

    # Check if last word is a verb ending
    last = words[-1].lower().strip(".,;:!?")
    if last not in VALID_VERB_ENDINGS:
        # Add 'hi' (declarative) as default
        corrections.append({
            "type": "missing_verb",
            "from": " ".join(words),
            "to": " ".join(words) + " hi",
        })
        words.append("hi")

    return words, corrections


def fix_particle_order(words: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Ensure verb ending is at the end of the sentence.

    Returns (corrected_words, list of corrections made).
    """
    corrections: list[dict[str, str]] = []
    if len(words) < 3:
        return words, corrections

    # Find verb ending position
    verb_idx = -1
    for i, w in enumerate(words):
        clean = w.lower().strip(".,;:!?")
        if clean in VALID_VERB_ENDINGS:
            verb_idx = i
            break

    # If verb ending is not at the end, move it
    if verb_idx >= 0 and verb_idx < len(words) - 1:
        verb_word = words[verb_idx]
        remaining = words[verb_idx + 1:]
        new_words = words[:verb_idx] + remaining + [verb_word]
        corrections.append({
            "type": "particle_order",
            "from": " ".join(words),
            "to": " ".join(new_words),
        })
        return new_words, corrections

    return words, corrections


# ---------------------------------------------------------------------------
# Main correction pipeline
# ---------------------------------------------------------------------------


def correct_sentence(entry: dict[str, Any]) -> dict[str, Any]:
    """Apply all corrections to a single sentence entry.

    Returns updated entry with corrected zolai/english and correction details.
    """
    zolai = entry.get("zolai", "")
    english = entry.get("english", "")
    all_corrections: list[dict[str, str]] = []

    # 1. Fix ZVS forms in Zolai
    zolai, corrections = fix_zvs_forms(zolai)
    all_corrections.extend(corrections)

    # 2. Fix ZVS forms in English
    english, corrections = fix_zvs_forms(english)
    all_corrections.extend(corrections)

    # 3. Fix proper nouns in English
    english, corrections = fix_proper_nouns_en(english)
    all_corrections.extend(corrections)

    # 4. Fix duplicate particles in Zolai
    zolai, corrections = fix_duplicate_particles(zolai)
    all_corrections.extend(corrections)

    # 5. Fix missing verb ending
    words = zolai.split()
    words, corrections = fix_missing_verb_ending(words)
    all_corrections.extend(corrections)

    # 6. Fix particle order
    words, corrections = fix_particle_order(words)
    all_corrections.extend(corrections)

    zolai = " ".join(words)

    # Build result
    result = dict(entry)
    result["zolai"] = zolai
    result["english"] = english
    result["corrections"] = all_corrections
    result["corrected"] = len(all_corrections) > 0

    return result


def correct_all_sentences(
    input_path: Path,
    output_path: Path,
    report_path: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Correct all invalid sentences and generate a report.

    Args:
        input_path: Path to invalid.jsonl.
        output_path: Path for corrected.jsonl.
        report_path: Path for correction_report.json.
        verbose: Print progress.

    Returns:
        Summary stats dict.
    """
    if verbose:
        print(f"Loading invalid sentences from {input_path}...")

    sentences: list[dict[str, Any]] = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(json.loads(line))

    if verbose:
        print(f"  Loaded {len(sentences)} invalid sentences")

    corrected: list[dict[str, Any]] = []
    correction_counts: dict[str, int] = {}
    total_corrections = 0

    for i, sent in enumerate(sentences):
        result = correct_sentence(sent)
        corrected.append(result)

        if result["corrected"]:
            total_corrections += 1
            for c in result["corrections"]:
                ctype = c.get("type", "unknown")
                correction_counts[ctype] = correction_counts.get(ctype, 0) + 1

        if verbose and (i + 1) % 500 == 0:
            print(f"  Corrected {i + 1}/{len(sentences)} sentences...")

    # Save corrected sentences
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in corrected)

    # Build report
    report = {
        "input": str(input_path),
        "output": str(output_path),
        "total_processed": len(sentences),
        "corrected_count": total_corrections,
        "correction_rate": f"{total_corrections * 100 / max(len(sentences), 1):.1f}%",
        "correction_types": correction_counts,
        "total_individual_corrections": sum(correction_counts.values()),
        "sample_corrections": [],
    }

    # Add sample corrections
    for s in corrected:
        if s.get("corrected") and s.get("corrections"):
            report["sample_corrections"].append({
                "original_zolai": s.get("zolai", ""),
                "corrections": s["corrections"][:3],
            })
            if len(report["sample_corrections"]) >= 10:
                break

    # Save report
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        if verbose:
            print(f"  Report saved to {report_path}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-fix invalid Zolai sentences (ZVS 2018 + grammar)."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(WORKSPACE / "data/training/validated/invalid.jsonl"),
        help="Input JSONL with invalid sentences",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(WORKSPACE / "data/training/corrected.jsonl"),
        help="Output JSONL for corrected sentences",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=str(WORKSPACE / "data/training/correction_report.json"),
        help="Output path for correction report JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        print("Run validate_sentences.py first to create invalid.jsonl.")
        return

    print("=" * 60)
    print("  Zolai Sentence Corrector")
    print("  ZVS 2018 + Grammar Fixes")
    print("=" * 60)
    print()

    report = correct_all_sentences(
        input_path=input_path,
        output_path=output_path,
        report_path=report_path,
        verbose=not args.quiet,
    )

    # Print summary
    print()
    print("=" * 60)
    print("  CORRECTION SUMMARY")
    print("=" * 60)
    print(f"  Total processed: {report['total_processed']}")
    print(f"  Corrected:       {report['corrected_count']} ({report['correction_rate']})")
    print(f"  Individual fixes: {report['total_individual_corrections']}")
    print()

    if report["correction_types"]:
        print("  Correction types:")
        for ctype, count in sorted(report["correction_types"].items(), key=lambda x: -x[1]):
            print(f"    {ctype:25s} {count:6d}")
        print()

    if report["sample_corrections"]:
        print("  Sample corrections:")
        for s in report["sample_corrections"][:5]:
            print(f"    {s['original_zolai']}")
            for c in s["corrections"][:2]:
                print(f"      → {c['type']}: {c['from']} → {c['to']}")
        print()

    print(f"  Output: {output_path}")
    print(f"  Report: {report_path}")


if __name__ == "__main__":
    main()
