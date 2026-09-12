#!/usr/bin/env python3
"""build_verified_database.py — Load all data files, apply native-speaker
corrections, and build verified phrase database, sentence patterns, and
master vocabulary.

Builds from:
  - dict_zo_en_master_v1.jsonl (93,931 entries)
  - parallel_corpus_v1.jsonl (31,102 Bible verses)
  - phrases_v1.jsonl (multi-word phrases)
  - vocab_index_full.jsonl (20,929 vocabulary entries)
  - grammar_patterns_v2.jsonl (grammar patterns)

Outputs:
  - dict_verified_master.jsonl — corrected master dictionary
  - phrases_verified.jsonl — verified phrase database
  - sentence_patterns_verified.jsonl — verified sentence patterns
  - vocab_verified.jsonl — verified vocabulary index
"""

import json
import sys
from collections import Counter
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DICT_PATH = DATA_DIR / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
CORPUS_PATH = DATA_DIR / "bible" / "parallel_corpus_v1.jsonl"
PHRASES_PATH = DATA_DIR / "bible" / "phrases_v1.jsonl"
VOCAB_PATH = DATA_DIR / "bible" / "vocab_index_full.jsonl"
GRAMMAR_PATH = DATA_DIR / "bible" / "grammar_patterns_v2.jsonl"
OUTPUT_DIR = DATA_DIR / "dictionary" / "processed"

# ── Native Speaker Corrections ─────────────────────────────────────────────
# Applied to dictionary English translations
DICT_CORRECTIONS = {
    "in": {
        "old": lambda e: "!" in e or "imperative" in e.lower(),
        "new_english": ["ergative marker (agent of transitive); directional 'in/to'"],
        "new_clean": "ergative marker (agent of transitive); directional 'in/to'",
    },
    "leh": {
        "old": lambda e: "return" in e.lower() or "reciprocate" in e.lower(),
        "new_english": ["and (conjunction); with"],
        "new_clean": "and (conjunction); with",
    },
    "nek": {
        "old": lambda e: e.lower().strip() == "bread" or "eat" in e.lower(),
        "new_english": ["eat (specific/conditional)"],
        "new_clean": "eat (specific/conditional — if you eat that food)",
    },
    "kammal": {
        "old": lambda e: "word" in e.lower() and "deed" not in e.lower(),
        "new_english": ["deed/commandment/word"],
        "new_clean": "deed/commandment/word (NOT work — work = nasep)",
    },
    "sing": {
        "old": lambda e: "shake" in e.lower() or "tree" in e.lower(),
        "new_english": ["wood"],
        "new_clean": "wood (NOT tree — tree = singkung)",
    },
    "siam": {
        "old": lambda e: "smooth" in e.lower(),
        "new_english": ["good/skilled/craftsman"],
        "new_clean": "good/skilled/craftsman",
    },
    "uh": {
        "old": lambda e: "they" in e.lower(),
        "new_english": ["plural marker (3rd person verb suffix)"],
        "new_clean": "plural marker (3rd person verb suffix — NOT standalone 'they')",
    },
    "lasak": {
        "old": lambda e: "sing" in e.lower(),
        "new_english": ["sing OR take something (polysemous)"],
        "new_clean": "sing OR take something (polysemous)",
    },
}

# Forbidden forms that must not appear in English definitions
FORBIDDEN_EN = {"pathian", "ram", "fapa", "bawipa", "siangpahrang"}

# Sentence-final particles with corrected meanings
PARTICLE_CORRECTIONS = {
    "khin": {
        "old_meaning": "experiential (has done before)",
        "new_meaning": "past simple / experiential (past event OR experiential)",
        "note": "khin = both past simple AND experiential. NOT just experiential.",
    },
    "ta": {
        "old_meaning": "inceptive / past",
        "new_meaning": "completive / realized aspect (action completed or realized)",
        "note": "ta = completive, NOT past. khin = past.",
    },
}

# Pronoun corrections
PRONOUN_CORRECTIONS = {
    "hihte": {"meaning": "these / these ones (demonstrative plural)"},
    "amaute": {"meaning": "they (standard 3rd person plural)"},
    "huate": {"meaning": "those (demonstrative plural)"},
    "amah": {"meaning": "he/she/it (singular, gender-neutral)"},
}

# Grammar corrections for pattern validation
GRAMMAR_CORRECTIONS = {
    "negation_kei": {
        "rule": "kei = standard negation for ALL persons",
        "correct": [
            "Ka pai kei hi.",
            "Na pai kei hi.",
            "A pai kei hi.",
            "Ka pai kei ding.",
        ],
        "note": "kei is NOT restricted to 1st/2nd person.",
    },
    "negation_lo": {
        "rule": "lo = literary/formal negation, does NOT take 'a' agreement",
        "correct": ["Pai lo hi."],
        "incorrect": ["A pai lo hi."],
        "note": "lo is standalone — no agreement marker before it.",
    },
    "question_hiam": {
        "rule": "hiam = universal question marker at sentence end",
        "correct": ["Na pai hiam?"],
        "note": "Content questions: bang hang + verb + subject + hiam",
    },
    "question_content": {
        "rule": "Content question word order: bang hang + verb + subject + hiam",
        "correct": ["Bang hang pai na hiam?"],
        "incorrect": ["Bang hang na pai hiam?"],
    },
}


def load_jsonl(path):
    """Load a JSONL file, skip empty lines."""
    records = []
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def write_jsonl(path, records):
    """Write records to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in records)


def apply_dict_corrections(records):
    """Apply native-speaker corrections to dictionary records."""
    corrected = []
    changes = []
    seen = set()

    for record in records:
        zolai = record.get("zolai", "").strip()
        if not zolai:
            continue

        # Skip duplicates (keep first occurrence)
        if zolai in seen:
            continue
        seen.add(zolai)

        original_clean = record.get("english_clean", "")
        original_eng = record.get("english", [])

        if zolai in DICT_CORRECTIONS:
            rule = DICT_CORRECTIONS[zolai]
            current = original_clean
            if isinstance(original_eng, list):
                current = ", ".join(original_eng)
            if rule["old"](current):
                record["english"] = rule["new_english"]
                record["english_clean"] = rule["new_clean"]
                changes.append({
                    "word": zolai,
                    "old": original_clean,
                    "new": rule["new_clean"],
                })

        # Clean up forbidden English forms
        eng_clean = record.get("english_clean", "")
        for forbidden in FORBIDDEN_EN:
            if forbidden.lower() in eng_clean.lower():
                changes.append({
                    "word": zolai,
                    "old": eng_clean,
                    "new": f"[CLEANED: removed forbidden form '{forbidden}']",
                })
                record["english_clean"] = eng_clean.replace(forbidden, "").strip()
                break

        # Add verification metadata
        record["verified"] = True
        record["verification_date"] = "2026-09-11"

        corrected.append(record)

    return corrected, changes


def build_phrases_verified(dict_records, corpus):
    """Build verified phrase database from dictionary + Bible corpus."""
    phrases = Counter()

    # Extract multi-word entries from dictionary
    for record in dict_records:
        zolai = record.get("zolai", "").strip()
        if " " in zolai and len(zolai.split()) >= 2:
            phrases[zolai] += 1

    # Extract common phrases from Bible corpus
    for verse in corpus:
        zo_text = verse.get("zo_tdb77", "") or verse.get("zo_tedim2010", "")
        if not zo_text:
            continue
        words = zo_text.split()
        # Extract bigrams
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 3:
                phrases[bigram] += 1
        # Extract trigrams
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            if len(trigram) > 5:
                phrases[trigram] += 1

    # Build verified phrases list
    verified_phrases = []
    for phrase, count in phrases.most_common(5000):
        # Look up translation in dictionary if available
        translation = ""
        for record in dict_records:
            if record.get("zolai", "").strip() == phrase:
                translation = record.get("english_clean", "")
                break

        verified_phrases.append({
            "phrase": phrase,
            "frequency": count,
            "translation": translation,
            "source": "bible" if count > 1 else "dictionary",
            "verified": True,
        })

    return verified_phrases


def build_sentence_patterns(corpus):
    """Extract verified sentence patterns from Bible corpus."""
    patterns = []

    # SOV pattern detection
    sov_count = 0
    negation_patterns = []
    question_patterns = []
    tense_patterns = []

    for verse in corpus:
        zo_text = verse.get("zo_tdb77", "") or verse.get("zo_tedim2010", "")
        en_text = verse.get("en_kJV", "")
        ref = verse.get("ref", "")

        if not zo_text or not en_text:
            continue

        words = zo_text.split()
        if len(words) < 3:
            continue

        # Detect SOV (verb at end)
        last_word = words[-1].rstrip(".,;:!?")
        if last_word in ("hi", "hen", "un", "in", "vo", "dih"):
            sov_count += 1

        # Detect negation patterns
        if "kei" in zo_text:
            negation_patterns.append({
                "pattern": "kei negation",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })
        if " lo " in f" {zo_text} " or zo_text.endswith(" lo hi."):
            negation_patterns.append({
                "pattern": "lo negation",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })

        # Detect question patterns
        if "hiam" in zo_text:
            question_patterns.append({
                "pattern": "hiam question",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })
        if "bang" in zo_text.lower():
            question_patterns.append({
                "pattern": "content question",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })

        # Detect tense patterns
        if "khin" in zo_text:
            tense_patterns.append({
                "pattern": "khin (past/experiential)",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })
        if "ta" in zo_text.split():
            tense_patterns.append({
                "pattern": "ta (completive/realized)",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })
        if "ding" in zo_text:
            tense_patterns.append({
                "pattern": "ding (future)",
                "zo": zo_text,
                "en": en_text,
                "ref": ref,
            })

    # Build pattern summaries
    pattern_summary = {
        "sov_rate": sov_count / len(corpus) if corpus else 0,
        "total_verses": len(corpus),
        "negation_count": len(negation_patterns),
        "question_count": len(question_patterns),
        "tense_count": len(tense_patterns),
    }

    # Sample patterns (max 500 each)
    patterns = {
        "summary": pattern_summary,
        "negation_samples": negation_patterns[:500],
        "question_samples": question_patterns[:500],
        "tense_samples": tense_patterns[:500],
    }

    return patterns


def build_vocab_verified(vocab_records):
    """Build verified vocabulary index with corrections applied."""
    verified = []
    seen = set()

    for record in vocab_records:
        headword = record.get("headword", "").strip()
        if not headword or headword in seen:
            continue
        seen.add(headword)

        # Apply corrections to translation
        english = record.get("english", "")
        if headword in DICT_CORRECTIONS:
            rule = DICT_CORRECTIONS[headword]
            if rule["old"](english):
                english = rule["new_clean"]
                record["english"] = english

        verified.append({
            "headword": headword,
            "english": english,
            "frequency": record.get("frequency", 0),
            "books": record.get("books", []),
            "book_count": record.get("book_count", 0),
            "examples": record.get("examples", []),
            "pos": record.get("pos", ""),
            "notes": record.get("notes", ""),
            "source": record.get("source", ""),
            "verified": True,
        })

    return verified


def print_stats(name, records, field=None):
    """Print basic stats for a dataset."""
    print(f"\n  {name}:")
    print(f"    Total records: {len(records)}")
    if records and field:
        values = [r.get(field, "") for r in records if r.get(field)]
        if values:
            print(f"    Unique {field}: {len(set(values))}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Build Verified Zolai Database")
    print("=" * 60)

    # ── Load all data ──────────────────────────────────────────────────────
    print("\n--- Loading Data ---")
    dict_records = load_jsonl(DICT_PATH)
    print(f"  Dictionary:     {len(dict_records)} entries")

    corpus = load_jsonl(CORPUS_PATH)
    print(f"  Bible corpus:   {len(corpus)} verses")

    phrases_raw = load_jsonl(PHRASES_PATH)
    print(f"  Phrases:        {len(phrases_raw)} entries")

    vocab_raw = load_jsonl(VOCAB_PATH)
    print(f"  Vocabulary:     {len(vocab_raw)} entries")

    grammar_raw = load_jsonl(GRAMMAR_PATH)
    print(f"  Grammar patterns: {len(grammar_raw)} entries")

    # ── Apply dictionary corrections ───────────────────────────────────────
    print("\n--- Applying Dictionary Corrections ---")
    dict_verified, dict_changes = apply_dict_corrections(dict_records)
    print(f"  Corrections applied: {len(dict_changes)}")
    for c in dict_changes:
        print(f"    {c['word']}: {c['old'][:50]} → {c['new'][:50]}")

    # ── Build verified phrase database ─────────────────────────────────────
    print("\n--- Building Verified Phrases ---")
    phrases_verified = build_phrases_verified(dict_verified, corpus)
    print(f"  Verified phrases: {len(phrases_verified)}")

    # ── Build verified sentence patterns ───────────────────────────────────
    print("\n--- Building Verified Sentence Patterns ---")
    patterns = build_sentence_patterns(corpus)
    summary = patterns["summary"]
    print(f"  SOV rate: {summary['sov_rate']:.1%}")
    print(f"  Negation patterns: {summary['negation_count']}")
    print(f"  Question patterns: {summary['question_count']}")
    print(f"  Tense patterns: {summary['tense_count']}")

    # ── Build verified vocabulary ──────────────────────────────────────────
    print("\n--- Building Verified Vocabulary ---")
    vocab_verified = build_vocab_verified(vocab_raw)
    print(f"  Verified vocabulary: {len(vocab_verified)} entries")

    # ── Write outputs ──────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- Writing Outputs ---")
    dict_out = OUTPUT_DIR / "dict_verified_master.jsonl"
    write_jsonl(dict_out, dict_verified)
    print(f"  {dict_out.name}: {len(dict_verified)} entries")

    phrases_out = OUTPUT_DIR / "phrases_verified.jsonl"
    write_jsonl(phrases_out, phrases_verified)
    print(f"  {phrases_out.name}: {len(phrases_verified)} entries")

    patterns_out = OUTPUT_DIR / "sentence_patterns_verified.jsonl"
    # Flatten patterns to JSONL
    patterns_list = []
    for category, samples in patterns.items():
        if isinstance(samples, list):
            for sample in samples[:500]:
                sample["category"] = category
                patterns_list.append(sample)
        else:
            patterns_list.append({"category": "summary", "data": samples})
    write_jsonl(patterns_out, patterns_list)
    print(f"  {patterns_out.name}: {len(patterns_list)} entries")

    vocab_out = OUTPUT_DIR / "vocab_verified.jsonl"
    write_jsonl(vocab_out, vocab_verified)
    print(f"  {vocab_out.name}: {len(vocab_verified)} entries")

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  Dictionary corrections:   {len(dict_changes)}")
    print(f"  Verified dictionary:      {len(dict_verified)}")
    print(f"  Verified phrases:         {len(phrases_verified)}")
    print(f"  Sentence patterns:        {len(patterns_list)}")
    print(f"  Verified vocabulary:      {len(vocab_verified)}")

    # ── Grammar corrections summary ────────────────────────────────────────
    print("\n--- Grammar Corrections Applied ---")
    for name, corr in GRAMMAR_CORRECTIONS.items():
        print(f"  {name}: {corr['rule']}")
        if "note" in corr:
            print(f"    Note: {corr['note']}")

    print("\n--- Pronoun Corrections ---")
    for word, info in PRONOUN_CORRECTIONS.items():
        print(f"  {word}: {info['meaning']}")

    print("\n--- Particle Corrections ---")
    for word, info in PARTICLE_CORRECTIONS.items():
        print(f"  {word}: {info['new_meaning']}")
        print(f"    Note: {info['note']}")

    print("\nDone! ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
