#!/usr/bin/env python3
"""Grammar + ZVS 2018 validation for generated Zolai sentences.

Loads generated sentences from input JSONL, checks:
  1. ZVS 2018 compliance (forbidden forms)
  2. Basic grammar structure (verb ending, subject marker)
  3. Vocabulary usage quality

Scores each sentence 0-100 and splits into valid (>= min_score) and invalid.

Usage:
    python validate_sentences.py --input data/training/generated_sentences.jsonl
    python validate_sentences.py --input data/training/generated_sentences.jsonl --min-score 60
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[4]

# ---------------------------------------------------------------------------
# ZVS 2018 forbidden forms
# ---------------------------------------------------------------------------

ZVS_FORBIDDEN: dict[str, str] = {
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

# Valid verb endings / particles
VALID_VERB_ENDINGS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute",
})

# Valid subject markers
VALID_SUBJECT_MARKERS = frozenset({
    "ka", "na", "a", "i", "ki",
})

# Common proper nouns (should be capitalized in English)
PROPER_NOUNS = frozenset({
    "pasian", "topa", "vantung", "kumpipa", "jesuh", "david",
    "israel", "adam", "seth", "enosh", "kenan", "noah",
})

# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------


def check_zvs_compliance(text: str) -> list[dict[str, str]]:
    """Check for ZVS 2018 forbidden forms in text.

    Returns list of {form, correct, context} for each violation found.
    """
    violations: list[dict[str, str]] = []
    words = text.lower().split()
    for i, word in enumerate(words):
        # Strip punctuation for matching
        clean = word.strip(".,;:!?\"'()[]{}")
        if clean in ZVS_FORBIDDEN:
            context = " ".join(words[max(0, i - 2):i + 3])
            violations.append({
                "form": clean,
                "correct": ZVS_FORBIDDEN[clean],
                "context": context,
            })
    return violations


def check_grammar_structure(zolai: str) -> dict[str, Any]:
    """Check basic grammar structure of a Zolai sentence.

    Returns dict with:
      - has_verb_ending: bool
      - has_subject: bool
      - issues: list of issue descriptions
    """
    words = zolai.lower().split()
    issues: list[str] = []

    # Check for verb ending / sentence-final particle
    has_verb = False
    for word in words:
        clean = word.strip(".,;:!?")
        if clean in VALID_VERB_ENDINGS:
            has_verb = True
            break

    if not has_verb:
        issues.append("No verb ending found (hi/hiam/kei/lo/ding/sak/etc.)")

    # Check for subject marker or noun
    has_subject = False
    for word in words:
        clean = word.strip(".,;:!?")
        if clean in VALID_SUBJECT_MARKERS or clean == "in":
            has_subject = True
            break
        # Check if it's a known noun (rough heuristic: >2 chars, not a particle)
        if len(clean) > 2 and clean not in VALID_VERB_ENDINGS:
            has_subject = True
            break

    if not has_subject:
        issues.append("No subject marker or noun found")

    # Check SOV order (rough heuristic)
    if len(words) >= 3:
        verb_pos = -1
        for i, w in enumerate(words):
            if w in VALID_VERB_ENDINGS:
                verb_pos = i
                break
        if verb_pos >= 0 and verb_pos < len(words) - 2:
            issues.append(f"Verb ending '{words[verb_pos]}' not at end of sentence")

    return {
        "has_verb_ending": has_verb,
        "has_subject": has_subject,
        "issues": issues,
    }


def score_sentence(zolai: str, english: str) -> tuple[int, list[str]]:
    """Score a sentence 0-100 based on multiple quality factors.

    Returns (score, list of issues).
    """
    score = 100
    issues: list[str] = []

    # ZVS compliance (0-40 points)
    zvs_violations = check_zvs_compliance(zolai)
    if zvs_violations:
        penalty = min(40, len(zvs_violations) * 20)
        score -= penalty
        for v in zvs_violations:
            issues.append(f"ZVS: '{v['form']}' → '{v['correct']}'")

    # Also check English for forbidden forms
    en_violations = check_zvs_compliance(english)
    if en_violations:
        score -= 10
        for v in en_violations:
            issues.append(f"EN ZVS: '{v['form']}'")

    # Grammar structure (0-30 points)
    grammar = check_grammar_structure(zolai)
    if not grammar["has_verb_ending"]:
        score -= 15
        issues.append("Missing verb ending")
    if not grammar["has_subject"]:
        score -= 15
        issues.append("Missing subject")
    for issue in grammar["issues"]:
        if "not at end" in issue:
            score -= 5
            issues.append(issue)

    # Vocabulary quality (0-20 points)
    words = zolai.split()
    if len(words) < 2:
        score -= 10
        issues.append("Too few words")
    elif len(words) > 15:
        score -= 5
        issues.append("Too many words")

    # English translation quality (0-10 points)
    if not english or english.strip() == "":
        score -= 10
        issues.append("Missing English translation")
    elif len(english.split()) < 2:
        score -= 5
        issues.append("English translation too short")

    # Ensure score is 0-100
    score = max(0, min(100, score))

    return score, issues


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------


def validate_sentences(
    input_path: Path,
    output_dir: Path,
    min_score: int = 70,
    verbose: bool = True,
) -> dict[str, Any]:
    """Validate a batch of generated sentences.

    Args:
        input_path: Path to input JSONL with generated sentences.
        output_dir: Directory for valid.jsonl and invalid.jsonl.
        min_score: Minimum score to consider valid.
        verbose: Print progress.

    Returns:
        Summary stats dict.
    """
    if verbose:
        print(f"Loading sentences from {input_path}...")

    sentences: list[dict[str, str]] = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(json.loads(line))

    if verbose:
        print(f"  Loaded {len(sentences)} sentences")

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []

    for i, sent in enumerate(sentences):
        zolai = sent.get("zolai", "")
        english = sent.get("english", "")
        score, issues = score_sentence(zolai, english)

        entry = {**sent, "score": score, "issues": issues}

        if score >= min_score:
            valid.append(entry)
        else:
            invalid.append(entry)

        if verbose and (i + 1) % 1000 == 0:
            print(f"  Validated {i + 1}/{len(sentences)} sentences...")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_path = output_dir / "valid.jsonl"
    with open(valid_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(v, ensure_ascii=False) + "\n" for v in valid)

    invalid_path = output_dir / "invalid.jsonl"
    with open(invalid_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(inv, ensure_ascii=False) + "\n" for inv in invalid)

    # Stats
    total = len(sentences)
    stats = {
        "total": total,
        "valid": len(valid),
        "invalid": len(invalid),
        "min_score": min_score,
        "avg_score": sum(s["score"] for s in valid + invalid) / max(total, 1),
        "valid_rate": f"{len(valid) * 100 / max(total, 1):.1f}%",
        "score_distribution": {},
    }

    # Score distribution
    for bucket in range(0, 101, 10):
        lo, hi = bucket, bucket + 10
        count = sum(1 for s in valid + invalid if lo <= s["score"] < hi)
        stats["score_distribution"][f"{lo}-{hi}"] = count

    # Top issues
    issue_counts: dict[str, int] = {}
    for s in invalid:
        for issue in s.get("issues", []):
            key = issue.split(":")[0] if ":" in issue else issue
            issue_counts[key] = issue_counts.get(key, 0) + 1
    stats["top_issues"] = sorted(issue_counts.items(), key=lambda x: -x[1])[:10]

    return stats, valid, invalid


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Zolai sentences (grammar + ZVS 2018)."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(WORKSPACE / "data/training/generated_sentences.jsonl"),
        help="Input JSONL with generated sentences",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(WORKSPACE / "data/training/validated"),
        help="Output directory for valid.jsonl and invalid.jsonl",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum score to consider valid (default: 70)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        print("Run generate_sentences.py first to create the input.")
        return

    print("=" * 60)
    print("  Zolai Sentence Validator")
    print("  Grammar + ZVS 2018 Compliance")
    print("=" * 60)
    print()

    stats, _valid, _invalid = validate_sentences(
        input_path=input_path,
        output_dir=output_dir,
        min_score=args.min_score,
        verbose=not args.quiet,
    )

    # Print summary
    print()
    print("=" * 60)
    print("  VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total sentences: {stats['total']}")
    print(f"  Valid (>= {stats['min_score']}):  {stats['valid']} ({stats['valid_rate']})")
    print(f"  Invalid (< {stats['min_score']}): {stats['invalid']}")
    print(f"  Average score:  {stats['avg_score']:.1f}")
    print()

    print("  Score distribution:")
    for bucket, count in stats["score_distribution"].items():
        bar = "#" * min(count * 40 // max(stats["total"], 1), 40)
        print(f"    {bucket:>6s}: {count:6d} {bar}")

    print()
    print("  Top issues (invalid sentences):")
    for issue, count in stats["top_issues"]:
        print(f"    {count:6d}  {issue}")

    print()
    print(f"  Output: {output_dir / 'valid.jsonl'}")
    print(f"  Output: {output_dir / 'invalid.jsonl'}")
    print()

    # Print some invalid examples
    if _invalid:
        print("  Sample invalid sentences:")
        for s in _invalid[:5]:
            print(f"    [{s['score']:3d}] {s['zolai']}")
            for issue in s.get("issues", [])[:2]:
                print(f"         → {issue}")
        print()


if __name__ == "__main__":
    main()
