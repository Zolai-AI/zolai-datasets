#!/usr/bin/env python3
"""
Phase 3: Grammar Pattern Extractor.

Reads word_alignments_v1.jsonl and parallel_corpus_v1.jsonl, identifies
grammatical patterns (SOV, tense markers, negation, aspect, agreement).

Usage:
    python3 scripts/bible/extract_grammar_patterns.py

Input:
    ../data/bible/parallel_corpus_v1.jsonl
    ../data/bible/word_alignments_v1.jsonl

Output:
    ../data/bible/grammar_patterns_v1.jsonl
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
ALIGNMENTS_PATH = WORKSPACE / "data" / "bible" / "word_alignments_v1.jsonl"
OUTPUT_PATH = WORKSPACE / "data" / "bible" / "grammar_patterns_v1.jsonl"

# ── Pattern definitions ──────────────────────────────────────────────────────

# Tense markers (ZVS 2018)
TENSE_MARKERS = {
    "khin": {"meaning": "past tense", "structure": "Verb + khin", "function": "past perfective"},
    "ngei": {"meaning": "experiential past", "structure": "Verb + ngei", "function": "experiential"},
    "ding": {"meaning": "future tense", "structure": "Verb + ding", "function": "future/intentional"},
    "ta":   {"meaning": "inchoative", "structure": "Verb + ta", "function": "beginning of action"},
    "pah":  {"meaning": "inchoative/continuative", "structure": "Verb + pah", "function": "action beginning or continuing"},
}

# Negation patterns
NEGATION_PATTERNS = {
    "kei":       {"meaning": "negative", "structure": "kei + Verb", "function": "general negation"},
    "lo":        {"meaning": "negative", "structure": "Verb + lo", "function": "prohibitive/resultative negation"},
    "kei_lo":    {"meaning": "negative", "structure": "kei + Verb + lo", "function": "strong negation"},
    "kei_a_leh": {"meaning": "negative", "structure": "kei + Verb + a leh", "function": "negation with contrast"},
}

# Aspect markers
ASPECT_MARKERS = {
    "zo":  {"meaning": "completive", "structure": "Verb + zo", "function": "action completed"},
    "lai": {"meaning": "progressive", "structure": "Verb + lai", "function": "action in progress"},
    "sak": {"meaning": "causative", "structure": "Verb + sak", "function": "causative/benefactive"},
    "khia": {"meaning": "resultative", "structure": "Verb + khia", "function": "resultative"},
}

# Agreement markers (person/number)
AGREEMENT_MARKERS = {
    "ka":  {"meaning": "1st person singular", "structure": "ka + Verb", "function": "subject agreement (I)"},
    "na":  {"meaning": "2nd person singular", "structure": "na + Verb", "function": "subject agreement (you)"},
    "a":   {"meaning": "3rd person singular", "structure": "a + Verb", "function": "subject agreement (he/she/it)"},
    "i":   {"meaning": "1st person plural inclusive", "structure": "i + Verb", "function": "subject agreement (we inclusive)"},
    "uh":  {"meaning": "2nd/3rd person plural", "structure": "uh + Verb", "function": "subject agreement (you/they plural)"},
}

# SOV-related words
SOV_MARKERS = {
    "in":  {"meaning": "ergative case marker", "function": "marks ergative/subject"},
    "hi":  {"meaning": "declarative sentence-final", "function": "sentence-final particle"},
}


def load_corpus() -> list[dict]:
    """Load the parallel corpus."""
    corpus = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            corpus.append(json.loads(line))
    return corpus


def load_alignments() -> dict[str, list[dict]]:
    """Load alignments grouped by ref."""
    by_ref: dict[str, list[dict]] = defaultdict(list)
    with open(ALIGNMENTS_PATH, encoding="utf-8") as f:
        for line in f:
            a = json.loads(line)
            by_ref[a["ref"]].append(a)
    return by_ref


def tokenize(text: str) -> list[str]:
    """Tokenize Zolai text."""
    return re.findall(r"[a-z']+", text.lower())


def find_pattern(zo_tokens: list[str], en_tokens: list[str], en_text: str,
                 ref: str) -> list[dict]:
    """Find grammar patterns in a verse."""
    patterns = []
    zo_set = set(zo_tokens)
    zo_str = " ".join(zo_tokens)
    en_str = en_text.lower()

    # ── SOV pattern detection ────────────────────────────────────────────────
    # Look for Subject + in + Object + Verb + hi
    if "in" in zo_set and "hi" in zo_set:
        # Find "in" position
        in_pos = next((i for i, t in enumerate(zo_tokens) if t == "in"), -1)
        hi_pos = next((i for i, t in enumerate(zo_tokens) if t == "hi"), -1)
        if in_pos >= 0 and hi_pos > in_pos:
            subject = " ".join(zo_tokens[:in_pos]) if in_pos > 0 else "(implicit)"
            verb_area = zo_tokens[in_pos + 1 : hi_pos] if hi_pos > in_pos + 1 else []
            patterns.append({
                "pattern": "SOV",
                "meaning": "Subject + in + Verb/Complement + hi (declarative)",
                "structure": "Subject + in + ... + hi",
                "function": "ergative SOV declarative",
                "frequency": 1,
                "confidence": 0.85,
                "notes": f"Subject='{subject}', Verb area={' '.join(verb_area[:3])}",
            })

    # ── Tense markers ────────────────────────────────────────────────────────
    for marker, info in TENSE_MARKERS.items():
        if marker in zo_set:
            # Find the word before the marker (likely the verb)
            idx = next((i for i, t in enumerate(zo_tokens) if t == marker), -1)
            if idx > 0:
                verb = zo_tokens[idx - 1]
                patterns.append({
                    "pattern": f"tense_{marker}",
                    "meaning": info["meaning"],
                    "structure": f"{verb} + {marker}",
                    "function": info["function"],
                    "frequency": 1,
                    "confidence": 0.8,
                    "notes": f"verb='{verb}', marker='{marker}'",
                })

    # ── Negation patterns ────────────────────────────────────────────────────
    # kei + Verb + lo
    if "kei" in zo_set and "lo" in zo_set:
        kei_pos = next((i for i, t in enumerate(zo_tokens) if t == "kei"), -1)
        lo_pos = next((i for i, t in enumerate(zo_tokens) if t == "lo"), -1)
        if kei_pos >= 0 and lo_pos > kei_pos:
            verb_between = zo_tokens[kei_pos + 1 : lo_pos]
            patterns.append({
                "pattern": "negation_kei_lo",
                "meaning": "strong negation",
                "structure": f"kei + {' '.join(verb_between)} + lo",
                "function": "strong negation with resultative",
                "frequency": 1,
                "confidence": 0.9,
                "notes": f"verb='{verb_between[0] if verb_between else '?'}'",
            })
    elif "kei" in zo_set:
        kei_pos = next((i for i, t in enumerate(zo_tokens) if t == "kei"), -1)
        if kei_pos >= 0 and kei_pos + 1 < len(zo_tokens):
            verb = zo_tokens[kei_pos + 1]
            patterns.append({
                "pattern": "negation_kei",
                "meaning": "negative",
                "structure": f"kei + {verb}",
                "function": "general negation",
                "frequency": 1,
                "confidence": 0.8,
                "notes": f"verb='{verb}'",
            })
    elif "lo" in zo_set and not "kei" in zo_set:
        lo_pos = next((i for i, t in enumerate(zo_tokens) if t == "lo"), -1)
        if lo_pos > 0:
            verb = zo_tokens[lo_pos - 1]
            patterns.append({
                "pattern": "negation_lo",
                "meaning": "negative/prohibitive",
                "structure": f"{verb} + lo",
                "function": "prohibitive/resultative negation",
                "frequency": 1,
                "confidence": 0.7,
                "notes": f"verb='{verb}'",
            })

    # ── Aspect markers ───────────────────────────────────────────────────────
    for marker, info in ASPECT_MARKERS.items():
        if marker in zo_set:
            idx = next((i for i, t in enumerate(zo_tokens) if t == marker), -1)
            if idx > 0:
                verb = zo_tokens[idx - 1]
                patterns.append({
                    "pattern": f"aspect_{marker}",
                    "meaning": info["meaning"],
                    "structure": f"{verb} + {marker}",
                    "function": info["function"],
                    "frequency": 1,
                    "confidence": 0.8,
                    "notes": f"verb='{verb}'",
                })

    # ── Agreement markers ────────────────────────────────────────────────────
    for marker, info in AGREEMENT_MARKERS.items():
        if marker in zo_set:
            # Check context: agreement before verb is common
            idx = next((i for i, t in enumerate(zo_tokens) if t == marker), -1)
            if idx >= 0:
                patterns.append({
                    "pattern": f"agreement_{marker}",
                    "meaning": info["meaning"],
                    "structure": f"{marker} + Verb",
                    "function": info["function"],
                    "frequency": 1,
                    "confidence": 0.7,
                    "notes": f"marker='{marker}' in position {idx}",
                })

    # Tag each pattern with ref
    for p in patterns:
        p["ref"] = ref

    return patterns


def aggregate_patterns(all_patterns: list[dict]) -> list[dict]:
    """Aggregate individual pattern occurrences into summary patterns."""
    # Group by (pattern, structure, function)
    groups: dict[str, dict] = {}
    for p in all_patterns:
        key = f"{p['pattern']}|{p['structure']}|{p['function']}"
        if key not in groups:
            groups[key] = {
                "id": f"pat_{len(groups) + 1:04d}",
                "pattern": p["pattern"],
                "meaning": p["meaning"],
                "structure": p["structure"],
                "function": p["function"],
                "frequency": 0,
                "confidence": p["confidence"],
                "notes": p["notes"],
                "refs": [],
            }
        groups[key]["frequency"] += 1
        if len(groups[key]["refs"]) < 5:
            groups[key]["refs"].append(p["ref"])

    # Sort by frequency descending
    result = sorted(groups.values(), key=lambda x: -x["frequency"])
    for i, p in enumerate(result):
        p["id"] = f"pat_{i + 1:04d}"
        p["refs"] = "; ".join(p["refs"])

    return result


def build_grammar_patterns():
    """Build grammar pattern database."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not CORPUS_PATH.exists():
        print(f"ERROR: Corpus not found: {CORPUS_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Loading corpus...")
    corpus = load_corpus()
    print(f"  Verses: {len(corpus):,}")

    print("Extracting grammar patterns...")
    all_patterns = []
    verses_with_patterns = 0

    for v in corpus:
        zo_text = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
        en_text = v.get("en_kJV") or ""
        if not zo_text or not en_text:
            continue

        zo_tokens = tokenize(zo_text)
        en_tokens = tokenize(en_text)
        patterns = find_pattern(zo_tokens, en_tokens, en_text, v["ref"])
        if patterns:
            verses_with_patterns += 1
            all_patterns.extend(patterns)

    print(f"  Raw pattern hits: {len(all_patterns):,}")
    print(f"  Verses with patterns: {verses_with_patterns:,}")

    print("Aggregating patterns...")
    aggregated = aggregate_patterns(all_patterns)
    print(f"  Unique patterns: {len(aggregated):,}")

    # Write output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in aggregated)

    # Print summary
    pattern_counts = Counter(p["pattern"] for p in aggregated)
    print(f"\n✅ Grammar patterns built: {OUTPUT_PATH.name}")
    print(f"   Total unique patterns: {len(aggregated):,}")
    print(f"   Pattern types: {dict(pattern_counts.most_common())}")
    print(f"   Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_grammar_patterns()
