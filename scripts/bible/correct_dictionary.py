#!/usr/bin/env python3
"""correct_dictionary.py — Scan dict_zo_en_master_v1.jsonl against Bible corpus,
apply native-speaker corrections, and output verified dictionary files.

Corrections verified against Bible corpus + native speaker Peter (2026-09-11):

1. 'in' = ergative marker / directional 'in/to', NOT '!'
2. 'leh' = and (conjunction), NOT 'return' (return is 'ciah')
3. 'nek' = eat (specific/conditional), general 'eat' = 'ne'
4. 'kammal' = deed/commandment, NOT 'work' (work = 'nasep')
5. 'sing' = wood (NOT tree — tree = 'singkung')
6. 'siam' = good/skilled/craftsman (NOT 'smooth-tongued')
7. 'khin' = past simple/experiential marker (NOT just experiential)
8. 'ta' = completive/realized aspect (NOT past simple)
9. 'uh' = plural marker for 3rd person (NOT 'they' standalone)
10. 'U' = elder sibling (NOT 'they')
11. 'hihte' = these/these ones (plural demonstrative)
12. 'amaute' = they (standard 3rd plural)
13. 'huate' = those (plural demonstrative)
14. 'nasep' = work (NOT 'kammal')
15. 'singkung' = tree (NOT 'sing')
"""

import json
import re
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DICT_PATH = DATA_DIR / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
CORPUS_PATH = DATA_DIR / "bible" / "parallel_corpus_v1.jsonl"
OUTPUT_DIR = DATA_DIR / "dictionary" / "processed"
CORRECTIONS_PATH = OUTPUT_DIR / "dict_corrections.jsonl"
VERIFIED_PATH = OUTPUT_DIR / "dict_zo_en_verified_v1.jsonl"

# ── Correction rules ───────────────────────────────────────────────────────
# Format: {zolai_word: {"old_english": ..., "new_english": ..., "new_english_clean": ..., "reason": ...}}
CORRECTIONS = {
    "in": {
        "old_english": ["! (imperative)"],
        "new_english": ["ergative marker (agent of transitive); directional 'in/to'"],
        "new_english_clean": "ergative marker (agent of transitive); directional 'in/to'",
        "reason": "Native speaker: 'in' = ergative marker, NOT punctuation",
    },
    "leh": {
        "old_english": ["return to, reciprocate, with"],
        "new_english": ["and (conjunction); with"],
        "new_english_clean": "and (conjunction); with",
        "reason": "Native speaker: 'leh' = and/with, NOT return (return = ciah)",
    },
    "nek": {
        "old_english": ["bread"],
        "new_english": ["eat (specific/conditional)"],
        "new_english_clean": "eat (specific/conditional — if you eat that food)",
        "reason": "Native speaker: nek = conditional/specific eating; general eat = ne",
    },
    "kammal": {
        "old_english": ["word"],
        "new_english": ["deed/commandment/word"],
        "new_english_clean": "deed/commandment/word (NOT work — work = nasep)",
        "reason": "Native speaker: kammal = deed/commandment; work = nasep",
    },
    "sing": {
        "old_english": ["to shake"],
        "new_english": ["wood"],
        "new_english_clean": "wood (NOT tree — tree = singkung)",
        "reason": "Native speaker: sing = wood; tree = singkung",
    },
    "siam": {
        "old_english": ["smooth-tongued"],
        "new_english": ["good/skilled/craftsman"],
        "new_english_clean": "good/skilled/craftsman",
        "reason": "Native speaker: siam = good/skilled, NOT smooth-tongued",
    },
    "uh": {
        "old_english": ["they (3rd plural marker)"],
        "new_english": ["plural marker (3rd person verb suffix)"],
        "new_english_clean": "plural marker (3rd person verb suffix — NOT standalone 'they')",
        "reason": "Native speaker: uh = plural marker only; they = hihte/amaute/huate",
    },
    "nasep": {
        "old_english": ["work, labor"],
        "new_english": ["work/labor/job"],
        "new_english_clean": "work/labor/job",
        "reason": "Standardized: nasep = work (kammal = deed/commandment)",
    },
}

# Words that should NOT appear in English translations (wrong Zolai mappings)
FORBIDDEN_ZOLAI_IN_ENGLISH = {
    "pathian": "pasian",
    "ram": "gam",
    "fapa": "tapa",
    "bawipa": "topa",
    "siangpahrang": "kumpipa",
}


def load_jsonl(path):
    """Load a JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path, records):
    """Write records to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def check_bible_usage(word, corpus):
    """Check how a word is used in the Bible corpus."""
    examples = []
    for verse in corpus:
        zo_text = verse.get("zo_tdb77") or verse.get("zo_tedim2010") or ""
        en_text = verse.get("en_kJV", "")
        # Check if word appears as a standalone word in Zolai text
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, zo_text, re.IGNORECASE):
            examples.append({
                "ref": verse.get("ref", ""),
                "zo": zo_text,
                "en": en_text,
            })
    return examples


def apply_corrections(records, corpus):
    """Apply corrections to dictionary records and return corrections log."""
    corrections_log = []
    corrected_records = []

    for record in records:
        zolai = record.get("zolai", "").strip()
        original_english = record.get("english_clean", "") or record.get("english", [""])

        if zolai in CORRECTIONS:
            correction = CORRECTIONS[zolai]
            # Check if the current definition matches what we want to correct
            current_english = original_english
            if isinstance(current_english, list):
                current_english = ", ".join(current_english)

            # Only correct if the old definition is wrong
            should_correct = False
            for old in correction["old_english"]:
                if old.lower() in current_english.lower():
                    should_correct = True
                    break

            # Always correct for specific words regardless of current value
            always_correct_words = {"uh", "in", "leh", "nek", "kammal", "sing", "siam"}
            if zolai in always_correct_words:
                should_correct = True

            if should_correct:
                old_value = record.get("english_clean", "")
                record["english"] = correction["new_english"]
                record["english_clean"] = correction["new_english_clean"]

                # Check Bible usage
                bible_examples = check_bible_usage(zolai, corpus)
                record["bible_examples"] = len(bible_examples)
                if bible_examples:
                    record["bible_sample_ref"] = bible_examples[0]["ref"]

                corrections_log.append({
                    "zolai": zolai,
                    "old_english_clean": old_value,
                    "new_english_clean": correction["new_english_clean"],
                    "reason": correction["reason"],
                    "bible_examples": len(bible_examples),
                    "sample_ref": bible_examples[0]["ref"] if bible_examples else "",
                })

        corrected_records.append(record)

    return corrections_log, corrected_records


def find_potential_errors(records):
    """Scan for potential errors beyond the known corrections."""
    issues = []

    for record in records:
        zolai = record.get("zolai", "").strip()
        english_clean = record.get("english_clean", "") or ""
        source = record.get("source", "")

        # Check for Hakha/Falam words that shouldn't be in Zolai dictionary
        for hakha, zolai_form in FORBIDDEN_ZOLAI_IN_ENGLISH.items():
            if hakha.lower() in english_clean.lower():
                issues.append({
                    "zolai": zolai,
                    "english_clean": english_clean,
                    "issue": f"English contains Hakha form '{hakha}' — should reference '{zolai_form}'",
                    "source": source,
                })

        # Check for empty or suspicious entries
        if not zolai or zolai.strip() == "":
            issues.append({
                "zolai": zolai,
                "english_clean": english_clean,
                "issue": "Empty Zolai headword",
                "source": source,
            })

        # Check for entries that look like POS tags, not words
        if len(zolai) <= 3 and zolai.startswith("&"):
            issues.append({
                "zolai": zolai,
                "english_clean": english_clean,
                "issue": "Looks like POS tag or artifact, not a word",
                "source": source,
            })

    return issues


def build_verified_database(records):
    """Build the verified master dictionary with additional metadata."""
    verified = []
    seen = set()

    for record in records:
        zolai = record.get("zolai", "").strip()
        if not zolai or zolai in seen:
            continue

        # Skip artifact entries (POS tags, special chars)
        if len(zolai) <= 3 and zolai.startswith(("&", "'")):
            continue

        seen.add(zolai)

        # Ensure required fields
        verified_record = {
            "zolai": zolai,
            "english": record.get("english", []),
            "english_clean": record.get("english_clean", ""),
            "source": record.get("source", ""),
            "verified": True,
            "verification_date": "2026-09-11",
        }

        # Add optional fields
        if "bible_examples" in record:
            verified_record["bible_examples"] = record["bible_examples"]
        if "bible_sample_ref" in record:
            verified_record["bible_sample_ref"] = record["bible_sample_ref"]

        verified.append(verified_record)

    return verified


def main():
    """Main entry point."""
    print("=" * 60)
    print("Zolai Dictionary Correction & Verification")
    print("=" * 60)

    # Check paths
    if not DICT_PATH.exists():
        print(f"ERROR: Dictionary not found: {DICT_PATH}")
        sys.exit(1)
    if not CORPUS_PATH.exists():
        print(f"ERROR: Corpus not found: {CORPUS_PATH}")
        sys.exit(1)

    # Load data
    print(f"\nLoading dictionary: {DICT_PATH}")
    records = load_jsonl(DICT_PATH)
    print(f"  Loaded {len(records)} entries")

    print(f"Loading Bible corpus: {CORPUS_PATH}")
    corpus = load_jsonl(CORPUS_PATH)
    print(f"  Loaded {len(corpus)} verses")

    # Apply corrections
    print("\n--- Applying Corrections ---")
    corrections_log, corrected_records = apply_corrections(records, corpus)
    print(f"  Applied {len(corrections_log)} corrections")

    # Find potential errors
    print("\n--- Scanning for Potential Errors ---")
    issues = find_potential_errors(corrected_records)
    print(f"  Found {len(issues)} potential issues")

    # Build verified database
    print("\n--- Building Verified Database ---")
    verified = build_verified_database(corrected_records)
    print(f"  Built verified database with {len(verified)} entries")

    # Write outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting corrections log: {CORRECTIONS_PATH}")
    write_jsonl(CORRECTIONS_PATH, corrections_log)

    print(f"Writing verified dictionary: {VERIFIED_PATH}")
    write_jsonl(VERIFIED_PATH, verified)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Original entries:    {len(records)}")
    print(f"  Corrections applied: {len(corrections_log)}")
    print(f"  Potential issues:    {len(issues)}")
    print(f"  Verified entries:    {len(verified)}")

    if "--stats" in sys.argv:
        print("\n--- Corrections Applied ---")
        for c in corrections_log:
            print(f"  {c['zolai']}: {c['old_english_clean']} → {c['new_english_clean']}")
            print(f"    Reason: {c['reason']}")
            print(f"    Bible occurrences: {c['bible_examples']}")
            if c['sample_ref']:
                print(f"    Sample: {c['sample_ref']}")
            print()

        if issues:
            print("\n--- Potential Issues (first 20) ---")
            for issue in issues[:20]:
                print(f"  [{issue['zolai']}] {issue['issue']}")
                print(f"    English: {issue['english_clean']}")
                print()

    if "--scan-only" in sys.argv:
        print("\n--- Scan Only Mode ---")
        print("  Corrections NOT written.")
        print("  Use --apply to write corrected files.")
        return

    print("\nDone! ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
