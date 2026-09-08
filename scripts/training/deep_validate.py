#!/usr/bin/env python3
"""Deep validation of generated Zolai sentences against real data sources.

Loads ALL data into memory at startup (dict ~80K, vocab ~20K, Bible ~31K,
patterns ~1.2K) and runs six validation checks:

  1. WORD EXISTS       — every word in dict or Bible vocab        (-5 / word)
  2. PATTERN MATCH     — structure matches Bible grammar patterns (-10)
  3. BIBLE PARALLEL    — verb usage consistent with Bible         (-15)
  4. WORD COLLOCATION  — word pairs attested in Bible             (-10)
  5. ZVS COMPLIANCE    — no forbidden forms                      (-20)
  6. SOV ORDER         — Subject before Verb before final particle(-15)

Outputs: valid.jsonl (>= min_score), invalid.jsonl (< min_score),
         deep_report.json (full statistics + examples).

Usage:
    python deep_validate.py --input sentences.jsonl
    python deep_validate.py --input sentences.jsonl --output-dir report --min-score 80
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]

DICT_PATH = WORKSPACE / "data" / "dictionary" / "processed" / "dict_zo_en_clean.jsonl"
VOCAB_PATH = WORKSPACE / "data" / "bible" / "vocab_index_full.jsonl"
CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
PATTERNS_PATH = WORKSPACE / "data" / "bible" / "grammar_patterns_text.jsonl"

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

# ---------------------------------------------------------------------------
# Linguistic helpers
# ---------------------------------------------------------------------------

# Subject markers / pronouns
SUBJECT_MARKERS = frozenset({
    "ka", "na", "a", "i", "ki", "amah", "kasi", "nasi",
    "keimani", "nisu", "asuo", "isuo", "kisuo",
})

# Verb-final particles / endings (sentence-closing)
VERB_FINALS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute", "a", "in",
})

# Particles that can precede the verb (object markers, etc.)
PRE_VERB_PARTICLES = frozenset({
    "in", "uh", "tua", "na", "ah", "leh",
})

# Ergative marker
ERGATIVE = "in"

# Content question words
CONTENT_QUESTIONS = frozenset({
    "banghang", "bang_hang", "bang hang", "diam", "kua",
})

# Yes/no question marker
YES_NO_QUEST = "hiam"


def tokenize(text: str) -> list[str]:
    """Tokenize Zolai text into words, handling hyphens and punctuation."""
    cleaned: list[str] = []
    for token in text.split():
        c = token.strip(".,;:!?\"'()[]{}").lower()
        if c:
            # Split hyphens: "pai-in" -> ["pai", "in"]
            for part in c.split("-"):
                if part:
                    cleaned.append(part)
    return cleaned


def clean_word(word: str) -> str:
    """Strip punctuation from a single word."""
    return word.strip(".,;:!?\"'()[]{}").lower()


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------

class DataLoader:
    """Load all data sources into memory at startup."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose

        # Sets for O(1) lookup
        self.dict_words: set[str] = set()
        self.dict_map: dict[str, str] = {}  # zolai -> english_clean

        self.vocab_words: set[str] = set()
        self.vocab_freq: dict[str, int] = {}
        self.vocab_translations: dict[str, list[str]] = {}

        # Bible parallel corpus: verb -> list of (zo_sentence, en_sentence)
        self.verb_contexts: dict[str, list[tuple[str, str]]] = defaultdict(list)
        # All bible words per verb for collocation
        self.verb_objects: dict[str, set[str]] = defaultdict(set)
        # Full verse store for substring search
        self.bible_verses: list[dict[str, str]] = []

        # Grammar patterns: set of known patterns
        self.pattern_set: set[str] = set()
        self.pattern_freq: dict[str, int] = {}
        self.pattern_examples: dict[str, list[str]] = {}

        self._load_dict()
        self._load_vocab()
        self._load_patterns()
        self._load_corpus()

    def _load_dict(self) -> None:
        t0 = time.time()
        count = 0
        with open(DICT_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                zolai = obj.get("zolai", "").strip().lower()
                english = obj.get("english_clean", "").strip()
                if zolai:
                    # Some entries have multi-word keys; index individual words too
                    self.dict_words.add(zolai)
                    if zolai not in self.dict_map:
                        self.dict_map[zolai] = english
                    for w in zolai.split():
                        self.dict_words.add(clean_word(w))
                    count += 1
        if self.verbose:
            print(f"  Dictionary:     {count:>8,} entries, {len(self.dict_words):>8,} unique words ({time.time()-t0:.1f}s)")

    def _load_vocab(self) -> None:
        t0 = time.time()
        count = 0
        with open(VOCAB_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                word = obj.get("word", "").strip().lower()
                if word:
                    self.vocab_words.add(word)
                    self.vocab_freq[word] = obj.get("frequency", 0)
                    self.vocab_translations[word] = obj.get("translations", [])
                    count += 1
        if self.verbose:
            print(f"  Bible vocab:    {count:>8,} words, {len(self.vocab_words):>8,} unique ({time.time()-t0:.1f}s)")

    def _load_patterns(self) -> None:
        t0 = time.time()
        count = 0
        with open(PATTERNS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pattern = obj.get("pattern", "")
                if pattern:
                    self.pattern_set.add(pattern)
                    self.pattern_freq[pattern] = obj.get("frequency", 0)
                    self.pattern_examples[pattern] = obj.get("examples", [])
                    count += 1
        if self.verbose:
            print(f"  Grammar patterns: {count:>6,} patterns ({time.time()-t0:.1f}s)")

    def _load_corpus(self) -> None:
        t0 = time.time()
        count = 0
        with open(CORPUS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                zo = obj.get("zo_tdb77", "")
                en = obj.get("en_kJV", "")
                ref = obj.get("ref", "")
                if zo:
                    self.bible_verses.append({
                        "zo": zo,
                        "en": en,
                        "ref": ref,
                    })
                    # Index verbs and their context
                    zo_words = tokenize(zo)
                    for i, w in enumerate(zo_words):
                        # Heuristic: verbs tend to be before hi/hiam/kei/lo/ding etc.
                        if w in VERB_FINALS and i > 0:
                            verb = zo_words[i - 1] if i > 0 else ""
                            if verb and verb not in VERB_FINALS and verb not in PRE_VERB_PARTICLES:
                                self.verb_contexts[verb].append((zo, en))
                                # Words around verb are likely objects/arguments
                                for j in range(max(0, i - 3), min(len(zo_words), i + 2)):
                                    ow = zo_words[j]
                                    if ow != verb and ow not in VERB_FINALS and ow not in PRE_VERB_PARTICLES:
                                        self.verb_objects[verb].add(ow)
                    count += 1
        if self.verbose:
            print(f"  Bible corpus:   {count:>8,} verses, {len(self.verb_contexts):>6,} verbs indexed ({time.time()-t0:.1f}s)")

    # Combined word set for existence check
    @property
    def all_known_words(self) -> set[str]:
        return self.dict_words | self.vocab_words


# ---------------------------------------------------------------------------
# Check 1: WORD EXISTS
# ---------------------------------------------------------------------------

def check_word_exists(
    words: list[str],
    known_words: set[str],
    verb_finals: frozenset[str],
    pre_verb: frozenset[str],
) -> tuple[int, list[dict[str, Any]]]:
    """Check every word exists in dict or Bible vocab.

    Returns (penalty, list of unknown word details).
    Particles, verb finals, and common Zolai function words are exempt.
    Hyphenated word components are also exempt (handled by HyphenRuleEngine).
    """
    unknown: list[dict[str, Any]] = []
    exempt = verb_finals | pre_verb | {
        "in", "hiam", "hi", "un", "ah", "a", "leh", "note", "tawh",
        "panin", "sungah", "tungah", "kiangah", "bangin", "hangin",
        "ciangin", "dingin", "khempeuh", "khat", "te", "ni", "na", "la",
        "la-in", "tu-in", "ni-in", "pai-in", "ma-in", "ci-in",
        "mai-ah", "lai-ah", "khua-ah",
    }

    for i, w in enumerate(words):
        if w in exempt:
            continue
        if w not in known_words:
            # Try common suffixes: -sak, -nak, -ah, -hen, -leh, -pia, etc.
            stripped = False
            for suffix in ("sak", "nak", "ah", "hen", "leh", "pia", "nei"):
                if w.endswith(suffix) and len(w) > len(suffix) + 2:
                    stem = w[: -len(suffix)]
                    if stem in known_words:
                        stripped = True
                        break
            if not stripped:
                unknown.append({
                    "word": w,
                    "position": i,
                    "context": " ".join(words[max(0, i - 1):i + 2]),
                })

    penalty = len(unknown) * 5
    return penalty, unknown


# ---------------------------------------------------------------------------
# Check 2: PATTERN MATCH
# ---------------------------------------------------------------------------

def extract_pattern(words: list[str]) -> str:
    """Extract a grammatical pattern from sentence words.

    Maps words to abstract tokens:
      - Subject markers -> S
      - 'in' -> in
      - Content words -> O (or other)
      - Pre-verb particles -> particle name
      - Verb finals -> hi/kei/lo/ding/etc.

    Returns pattern string like "S-in-O-uh-hi".
    """
    tokens: list[str] = []
    for w in words:
        if w in ("ka", "na", "i", "ki"):
            tokens.append("S")
        elif w == "a":
            tokens.append("S")  # 3rd person / article
        elif w == "in":
            tokens.append("in")
        elif w in ("uh",):
            tokens.append("uh")
        elif w in ("tua",):
            tokens.append("tua")
        elif w in VERB_FINALS:
            tokens.append(w)
        elif w in SUBJECT_MARKERS:
            tokens.append("S")
        elif w in CONTENT_QUESTIONS:
            tokens.append("Q")
        elif w == "kei":
            tokens.append("kei")
        else:
            tokens.append("O")

    # Collapse consecutive O tokens
    collapsed: list[str] = []
    for t in tokens:
        if t == "O" and collapsed and collapsed[-1] == "O":
            continue
        collapsed.append(t)

    return "-".join(collapsed)


def check_pattern_match(
    words: list[str],
    pattern_set: set[str],
    pattern_freq: dict[str, int],
) -> tuple[int, dict[str, Any]]:
    """Check if sentence structure matches a known Bible grammar pattern.

    Returns (penalty, details).
    """
    pattern = extract_pattern(words)
    details: dict[str, Any] = {"extracted_pattern": pattern}

    if pattern in pattern_set:
        details["found"] = True
        details["frequency"] = pattern_freq.get(pattern, 0)
        return 0, details

    # Try partial match: remove the O parts and check core
    core_parts: list[str] = []
    for t in pattern.split("-"):
        if t != "O":
            core_parts.append(t)
    core = "-".join(core_parts)

    if core in pattern_set:
        details["found"] = True
        details["partial_match"] = True
        details["core_pattern"] = core
        details["frequency"] = pattern_freq.get(core, 0)
        return 0, details

    details["found"] = False
    return 5, details


# ---------------------------------------------------------------------------
# Check 3: BIBLE PARALLEL (verb usage)
# ---------------------------------------------------------------------------

def check_bible_parallel(
    words: list[str],
    verb_contexts: dict[str, list[tuple[str, str]]],
) -> tuple[int, dict[str, Any]]:
    """Check if the main verb is used in a way attested in the Bible.

    Finds the verb (word before a verb-final particle) and checks
    if it appears in the Bible corpus with any context.

    Returns (penalty, details).
    """
    details: dict[str, Any] = {"verb": None, "bible_occurrences": 0}

    # Find the verb: first content word before a verb-final
    verb = None
    for i, w in enumerate(words):
        if w in VERB_FINALS and i > 0:
            candidate = words[i - 1]
            if candidate not in VERB_FINALS and candidate not in PRE_VERB_PARTICLES:
                verb = candidate
                break

    if verb is None:
        details["no_verb_found"] = True
        return 5, details  # Minor penalty for unparseable

    details["verb"] = verb

    if verb in verb_contexts:
        contexts = verb_contexts[verb]
        details["bible_occurrences"] = len(contexts)
        # Show a few examples
        details["bible_examples"] = [
            {"zo": c[0], "en": c[1]} for c in contexts[:3]
        ]
        return 0, details

    # Verb not in Bible at all
    details["bible_occurrences"] = 0
    return 15, details


# ---------------------------------------------------------------------------
# Check 4: WORD COLLOCATION
# ---------------------------------------------------------------------------

def check_collocation(
    words: list[str],
    verb_objects: dict[str, set[str]],
) -> tuple[int, dict[str, Any]]:
    """Check if verb-object pairs appear together in the Bible.

    Returns (penalty, details).
    """
    details: dict[str, Any] = {"checked_pairs": []}

    # Find verb
    verb = None
    verb_idx = -1
    for i, w in enumerate(words):
        if w in VERB_FINALS and i > 0:
            candidate = words[i - 1]
            if candidate not in VERB_FINALS and candidate not in PRE_VERB_PARTICLES:
                verb = candidate
                verb_idx = i
                break

    if verb is None or verb_idx < 0:
        return 0, details  # No verb found, skip

    # Collect candidate objects (content words before verb)
    objects_found: list[str] = []
    for w in words[:verb_idx]:
        if w not in SUBJECT_MARKERS and w not in PRE_VERB_PARTICLES and w not in VERB_FINALS:
            if w != "in":
                objects_found.append(w)

    if not objects_found or verb not in verb_objects:
        return 0, details  # No objects to check

    bible_objects = verb_objects[verb]
    penalty = 0
    for obj in objects_found:
        pair_info: dict[str, Any] = {"verb": verb, "object": obj}
        if obj in bible_objects:
            pair_info["attested"] = True
        else:
            pair_info["attested"] = False
            penalty += 10  # One pair not found
        details["checked_pairs"].append(pair_info)

    details["total_pairs"] = len(objects_found)
    details["attested_pairs"] = sum(
        1 for p in details["checked_pairs"] if p.get("attested")
    )

    return min(penalty, 10), details  # Cap at -10


# ---------------------------------------------------------------------------
# Check 5: ZVS COMPLIANCE
# ---------------------------------------------------------------------------

def check_zvs(text: str) -> tuple[int, list[dict[str, str]]]:
    """Check for ZVS 2018 forbidden forms.

    Returns (penalty, list of violations).
    """
    violations: list[dict[str, str]] = []
    words = text.lower().split()
    for i, word in enumerate(words):
        c = clean_word(word)
        if c in ZVS_FORBIDDEN:
            context = " ".join(words[max(0, i - 2):i + 3])
            violations.append({
                "form": c,
                "correct": ZVS_FORBIDDEN[c],
                "context": context,
            })

    penalty = len(violations) * 20
    return penalty, violations


# ---------------------------------------------------------------------------
# Check 6: SOV ORDER
# ---------------------------------------------------------------------------

# Verb roots that commonly appear in Zolai (before the final particle)
COMMON_VERBS = frozenset({
    "nek", "gam", "piang", "sak", "ci", "mu", "om", "dam", "tua",
    "topa", "pasian", "sang", "lei", "kia", "thu", "thei", "pia",
    "bawl", "a", "hi", "teng", "sel", "sun", "tah", "lem", "zang",
    "tui", "khu", "kha", "uan", "suah", "lo", "ngai",
})


def check_sov_order(
    words: list[str],
    known_words: set[str],
    original_text: str = "",
) -> tuple[int, dict[str, Any]]:
    """Verify Subject-Object-Verb order.

    Heuristic: subject marker or pronoun should appear before verb-final
    particle. Verb root should be before the final particle.
    Sentences with quoted speech are exempt from SOV penalty.

    Returns (penalty, details).
    """
    details: dict[str, Any] = {
        "subject_position": -1,
        "verb_position": -1,
        "final_particle_position": -1,
    }

    if len(words) < 2:
        return 0, details  # Too short to judge

    # Exempt sentences with quoted speech (contain quotation marks)
    if original_text and any(c in original_text for c in "\u201c\u201d\u2018\u2019\"'"):
        details["quoted_speech"] = True
        return 0, details

    # Find final verb particle (last one in sentence)
    final_pos = -1
    for i in range(len(words) - 1, -1, -1):
        if words[i] in VERB_FINALS:
            final_pos = i
            details["final_particle_position"] = i
            break

    if final_pos < 0:
        return 0, details  # No verb-final particle

    # Find subject marker (first occurrence)
    for i, w in enumerate(words):
        if w in SUBJECT_MARKERS or w in ("ka", "na", "a", "i", "ki"):
            details["subject_position"] = i
            break

    # Find verb root (word just before final particle)
    verb_pos = final_pos - 1
    details["verb_position"] = verb_pos

    # Check SOV: subject before verb
    subj = details["subject_position"]
    if subj >= 0 and verb_pos >= 0:
        if subj < verb_pos:
            return 0, details  # Correct SOV
        else:
            # Subject after verb — might be VOS or wrong order
            return 5, details

    # No subject found — might be imperative or pro-drop
    return 0, details


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

def validate_one(
    zolai: str,
    english: str,
    loader: DataLoader,
    source_ref: str = "",
) -> dict[str, Any]:
    """Run all six checks on a single sentence. Returns full result dict."""
    words = tokenize(zolai)

    # Start at 100, deduct per check
    score = 100
    checks: dict[str, Any] = {}

    # Detect if sentence is from Bible (has book:chapter:verse ref)
    is_bible_sourced = bool(source_ref and ":" in source_ref)

    # 1. WORD EXISTS
    penalty_1, unknown = check_word_exists(
        words, loader.all_known_words, VERB_FINALS, PRE_VERB_PARTICLES,
    )
    score -= penalty_1
    checks["word_exists"] = {
        "passed": penalty_1 == 0,
        "penalty": penalty_1,
        "unknown_words": unknown,
    }

    # 2. PATTERN MATCH
    # Bible-sourced sentences get 0 penalty regardless of pattern match
    if is_bible_sourced:
        penalty_2 = 0
        pattern_details = {"found": True, "bible_sourced": True}
    else:
        penalty_2, pattern_details = check_pattern_match(words, loader.pattern_set, loader.pattern_freq)
    score -= penalty_2
    checks["pattern_match"] = {
        "passed": penalty_2 == 0,
        "penalty": penalty_2,
        **pattern_details,
    }

    # 3. BIBLE PARALLEL
    penalty_3, parallel_details = check_bible_parallel(words, loader.verb_contexts)
    score -= penalty_3
    checks["bible_parallel"] = {
        "passed": penalty_3 == 0,
        "penalty": penalty_3,
        **parallel_details,
    }

    # 4. WORD COLLOCATION
    penalty_4, coll_details = check_collocation(words, loader.verb_objects)
    score -= penalty_4
    checks["word_collocation"] = {
        "passed": penalty_4 == 0,
        "penalty": penalty_4,
        **coll_details,
    }

    # 5. ZVS COMPLIANCE
    penalty_5, zvs_violations = check_zvs(zolai)
    score -= penalty_5
    checks["zvs_compliance"] = {
        "passed": penalty_5 == 0,
        "penalty": penalty_5,
        "violations": zvs_violations,
    }

    # 6. SOV ORDER
    penalty_6, sov_details = check_sov_order(words, loader.all_known_words, zolai)
    score -= penalty_6
    checks["sov_order"] = {
        "passed": penalty_6 == 0,
        "penalty": penalty_6,
        **sov_details,
    }

    score = max(0, min(100, score))

    return {
        "zolai": zolai,
        "english": english,
        "score": score,
        "checks": checks,
        "tokens": words,
        "pattern": extract_pattern(words),
    }


# ---------------------------------------------------------------------------
# High-level validator (used by build_training_corpus.py)
# ---------------------------------------------------------------------------


class DeepValidator:
    """High-level validator wrapping DataLoader + validate_one."""

    def __init__(self, verbose: bool = True) -> None:
        self.loader = DataLoader(verbose=verbose)

    def validate_batch(
        self, sentences: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Validate a batch of sentence dicts.

        Each dict must have at least 'zolai' and 'english' keys.
        Returns list with 'deep_score' and 'checks' added to each entry.
        """
        results: list[dict[str, Any]] = []
        for sent in sentences:
            zolai = sent.get("zolai", "")
            english = sent.get("english", "")
            result = validate_one(zolai, english, self.loader)
            entry: dict[str, Any] = {
                **sent,
                "deep_score": result["score"],
                "checks": result["checks"],
            }
            results.append(entry)
        return results


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def deep_validate(
    input_path: Path,
    output_dir: Path,
    min_score: int = 70,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run deep validation on all sentences in input_path.

    Returns summary stats dict.
    """
    # Load all data
    if verbose:
        print("Loading data sources...")
    loader = DataLoader(verbose=verbose)
    if verbose:
        print()

    # Load sentences
    if verbose:
        print(f"Loading sentences from {input_path}...")
    sentences: list[dict[str, str]] = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sentences.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if verbose:
        print(f"  Loaded {len(sentences)} sentences")
        print()

    # Validate each sentence
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    check_stats = {
        "word_exists_pass": 0,
        "word_exists_fail": 0,
        "pattern_match_pass": 0,
        "pattern_match_fail": 0,
        "bible_parallel_pass": 0,
        "bible_parallel_fail": 0,
        "word_collocation_pass": 0,
        "word_collocation_fail": 0,
        "zvs_compliance_pass": 0,
        "zvs_compliance_fail": 0,
        "sov_order_pass": 0,
        "sov_order_fail": 0,
    }
    unknown_word_counter: dict[str, int] = defaultdict(int)
    pattern_counter: dict[str, int] = defaultdict(int)

    t0 = time.time()
    for i, sent in enumerate(sentences):
        zolai = sent.get("zolai", "")
        english = sent.get("english", "") or sent.get("english_clean", "")
        source_ref = sent.get("source", "") or sent.get("ref", "")
        result = validate_one(zolai, english, loader, source_ref)

        entry = {**sent, "deep_score": result["score"], "checks": result["checks"], "pattern": result["pattern"]}

        if result["score"] >= min_score:
            valid.append(entry)
        else:
            invalid.append(entry)

        # Accumulate stats
        for key in check_stats:
            check_name = key.rsplit("_", 1)[0]  # e.g. "word_exists"
            if result["checks"].get(check_name, {}).get("passed"):
                check_stats[f"{check_name}_pass"] += 1
            else:
                check_stats[f"{check_name}_fail"] += 1

        for uw in result["checks"]["word_exists"]["unknown_words"]:
            unknown_word_counter[uw["word"]] += 1

        pat = result["pattern"]
        pattern_counter[pat] += 1

        if verbose and (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(f"  Validated {i + 1}/{len(sentences)} ({rate:.0f}/s)...")

    elapsed = time.time() - t0
    if verbose:
        print(f"  Done in {elapsed:.1f}s ({len(sentences)/max(elapsed,0.01):.0f}/s)")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_path = output_dir / "valid.jsonl"
    with open(valid_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(v, ensure_ascii=False) + "\n" for v in valid)

    invalid_path = output_dir / "invalid.jsonl"
    with open(invalid_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(inv, ensure_ascii=False) + "\n" for inv in invalid)

    # Score distribution
    score_dist: dict[str, int] = {}
    for bucket in range(0, 101, 10):
        lo, hi = bucket, bucket + 10
        score_dist[f"{lo:03d}-{hi:03d}"] = sum(
            1 for s in valid + invalid if lo <= s["deep_score"] < hi
        )

    # Build report
    total = len(sentences)
    report: dict[str, Any] = {
        "summary": {
            "total": total,
            "valid": len(valid),
            "invalid": len(invalid),
            "min_score": min_score,
            "avg_score": sum(s["deep_score"] for s in valid + invalid) / max(total, 1),
            "valid_rate": f"{len(valid) * 100 / max(total, 1):.1f}%",
            "elapsed_seconds": round(elapsed, 1),
        },
        "check_stats": check_stats,
        "score_distribution": score_dist,
        "top_unknown_words": sorted(unknown_word_counter.items(), key=lambda x: -x[1])[:30],
        "top_patterns": sorted(pattern_counter.items(), key=lambda x: -x[1])[:20],
        "sample_valid": [
            {"zolai": v["zolai"], "score": v["deep_score"], "pattern": v.get("pattern", "")}
            for v in valid[:5]
        ],
        "sample_invalid": [
            {"zolai": inv["zolai"], "score": inv["deep_score"], "checks": {
                k: v for k, v in inv["checks"].items() if not v.get("passed")
            }}
            for inv in invalid[:10]
        ],
    }

    report_path = output_dir / "deep_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deep validation of Zolai sentences against real data sources.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(WORKSPACE / "data" / "training" / "generated_sentences.jsonl"),
        help="Input JSONL with generated sentences",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(WORKSPACE / "data" / "training" / "deep_validated"),
        help="Output directory for valid.jsonl, invalid.jsonl, deep_report.json",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum deep_score to consider valid (default: 70)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print progress (default: True)",
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
        sys.exit(1)

    verbose = not args.quiet

    print("=" * 60)
    print("  Zolai Deep Sentence Validator")
    print("  6 checks against real data sources")
    print("=" * 60)
    print()

    report = deep_validate(
        input_path=input_path,
        output_dir=output_dir,
        min_score=args.min_score,
        verbose=verbose,
    )

    # Print summary
    s = report["summary"]
    print()
    print("=" * 60)
    print("  DEEP VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total sentences:      {s['total']}")
    print(f"  Valid  (>= {s['min_score']}):     {s['valid']} ({s['valid_rate']})")
    print(f"  Invalid (< {s['min_score']}):    {s['invalid']}")
    print(f"  Average score:        {s['avg_score']:.1f}")
    print(f"  Time:                 {s['elapsed_seconds']}s")
    print()

    cs = report["check_stats"]
    print("  Check pass rates:")
    checks_display = [
        ("Word Exists", "word_exists"),
        ("Pattern Match", "pattern_match"),
        ("Bible Parallel", "bible_parallel"),
        ("Collocation", "word_collocation"),
        ("ZVS Compliance", "zvs_compliance"),
        ("SOV Order", "sov_order"),
    ]
    for label, key in checks_display:
        p = cs[f"{key}_pass"]
        f_ = cs[f"{key}_fail"]
        total_ = p + f_
        rate = p * 100 / max(total_, 1)
        print(f"    {label:>20s}: {p:5d}/{total_:5d} ({rate:5.1f}%)")
    print()

    print("  Score distribution:")
    for bucket, count in report["score_distribution"].items():
        bar = "#" * min(count * 40 // max(s["total"], 1), 40)
        print(f"    {bucket}: {count:6d} {bar}")
    print()

    if report["sample_valid"]:
        print("  Sample valid sentences:")
        for v in report["sample_valid"]:
            print(f"    [{v['score']:3d}] {v['zolai']}")
        print()

    if report["sample_invalid"]:
        print("  Sample invalid sentences:")
        for inv in report["sample_invalid"]:
            print(f"    [{inv['score']:3d}] {inv['zolai']}")
            for check_name, check_data in inv.get("checks", {}).items():
                if isinstance(check_data, dict) and not check_data.get("passed"):
                    print(f"         -> {check_name}: penalty -{check_data.get('penalty', 0)}")
        print()

    print(f"  Output: {output_dir / 'valid.jsonl'}")
    print(f"  Output: {output_dir / 'invalid.jsonl'}")
    print(f"  Report: {output_dir / 'deep_report.json'}")
    print()


if __name__ == "__main__":
    main()
