#!/usr/bin/env python3
"""Bible-template Zolai sentence generation with semantic variation.

Loads real Bible sentences from data/bible/parallel_corpus_v1.jsonl and
creates training variations by:

  1. REPLACING SUBJECT: swap pronoun/noun with same-type alternative
  2. REPLACING OBJECT: swap with noun from same semantic category
  3. CHANGING TENSE: add/change tense markers (-sak, -ah, -hen, ding)
  4. MAKING NEGATIVE: add kei/lo negation
  5. MAKING QUESTION: add hiam question marker

The verb and its argument structure are kept intact — never swapped randomly.

Usage:
    python generate_sentences.py --max-sentences 5000 --output data/training/generated_sentences.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]
PARALLEL_PATH = WORKSPACE / "data/bible/parallel_corpus_v1.jsonl"
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

# ---------------------------------------------------------------------------
# Semantic categories (from Bible data analysis)
# ---------------------------------------------------------------------------

# Subjects — animate beings (use as S or in ergative position)
ANIMATE_SUBJECTS: dict[str, str] = {
    "pasian": "God",
    "topa": "the Lord",
    "mi": "a person",
    "numei": "a woman",
    "nupi": "a man",
    "pi": "a child",
    "kumpipa": "an angel",
    "david": "David",
    "adam": "Adam",
    "noah": "Noah",
    "israel": "Israel",
    "jesuh": "Jesus",
    "moses": "Moses",
    "abraham": "Abraham",
    "eli": "Eli",
    "samuel": "Samuel",
    "solomon": "Solomon",
    "isaac": "Isaac",
    "jacob": "Jacob",
}

# Subjects — inanimate forces / natural elements
INANIMATE_SUBJECTS: dict[str, str] = {
    "lebung": "the earth",
    "vantung": "the sky",
    "khuavak": "light",
    "khuamial": "darkness",
    "tui": "water",
    "sing": "the tree",
    "tapa": "fire",
    "kuang": "wind",
    "siang": "sound",
    "pua": "rain",
    "lung": "the mountain",
    "kawm": "death",
}

# Subjects — abstract concepts
ABSTRACT_SUBJECTS: dict[str, str] = {
    "nuntakna": "knowledge",
    "suahtakna": "fear of God",
    "thu": "the word",
    "hong": "work",
    "ci": "speech",
    "pau": "faith",
    "sim": "love",
    "gen": "obedience",
    "zat": "goodness",
    "lam": "the way",
    "cung": "truth",
    "piangzat": "holiness",
}

# Objects — people / beings (can be direct object)
PEOPLE_OBJECTS: dict[str, str] = {
    "mi": "a person",
    "numei": "a woman",
    "nupi": "a man",
    "pi": "a child",
    "suante": "sons",
    "tapate": "sons",
    "pasian": "God",
    "topa": "the Lord",
    "kumpipa": "an angel",
    "david": "David",
    "israel": "Israel",
    "jesuh": "Jesus",
    "moses": "Moses",
    "abraham": "Abraham",
}

# Objects — concrete / physical
CONCRETE_OBJECTS: dict[str, str] = {
    "vantung": "the sky",
    "lebung": "the earth",
    "tui": "water",
    "sing": "the tree",
    "tapa": "fire",
    "lam": "the road",
    "lung": "the mountain",
    "sung": "the house",
    "kung": "the village",
    "song": "the house",
    "khat": "a book",
    "hong": "work",
    "cuang": "clothes",
    "nekna": "food",
    "thu": "the word",
}

# Objects — abstract
ABSTRACT_OBJECTS: dict[str, str] = {
    "nuntakna": "knowledge",
    "suahtakna": "fear",
    "thu": "the word",
    "ci": "speech",
    "pau": "faith",
    "sim": "love",
    "gen": "obedience",
    "zat": "goodness",
    "cung": "truth",
    "hong": "work",
    "piangzat": "holiness",
    "piangtung": "the kingdom",
}

# Verb → valid object categories (what objects make sense with this verb)
VERB_OBJECT_COMPAT: dict[str, list[str]] = {
    "nek": ["nekna", "tui"],  # eat → food/drink
    "sung": ["nekna", "tui"],  # eat → food/drink
    "in": ["tui"],  # drink → liquid
    "hoih": ["mi", "numei", "nupi", "pi", "vantung", "lebung"],  # see → visual
    "kia": ["mi", "numei", "nupi", "pi", "vantung", "lebung"],  # see → visual
    "chang": ["thu", "ci"],  # hear → audio
    "ci": ["thu"],  # say → speech
    "bawl": ["mi", "numei", "vantung", "lebung", "sing"],  # create → created things
    "piangsak": ["mi", "numei", "vantung", "lebung", "sing"],  # created → created things
    "piang": ["mi", "numei", "vantung", "lebung", "sing"],  # create → created things
    "thupha": ["mi", "numei", "nupi", "pi", "topa"],  # bless → people
    "pia": ["mi", "numei", "nupi", "pi", "topa"],  # bless → people
    "pau": ["pasian", "topa"],  # trust → God/Lord
    "gen": ["pasian", "topa"],  # obey → God/Lord
    "sim": ["pasian", "topa", "mi"],  # love → God/people
    "thei": ["thu", "ci"],  # know → words/things
    "mu": ["thu", "ci"],  # know → words/things
    "nei": ["mi", "numei", "hong"],  # have → people/work
    "lei": ["mi", "numei", "hong"],  # take → people/work
    "gam": ["lam"],  # go → road/path
    "hei": ["lam"],  # go → road/path
    "tung": ["sung", "kung"],  # come → house/village
    "na": ["pasian", "topa"],  # fear → God/Lord
    "uh": [],  # do → any object
}

# Subject pronouns and their English
SUBJECT_PRONOUNS: dict[str, str] = {
    "ka": "I",
    "na": "you",
    "a": "he/she/it",
    "i": "she",
    "ki": "we",
    "they": "they",
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


def load_parallel_corpus(limit: int | None = None) -> list[dict[str, str]]:
    """Load Bible parallel corpus."""
    return _load_jsonl(PARALLEL_PATH, limit)


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
# Token utilities
# ---------------------------------------------------------------------------


def tokenize_zolai(text: str) -> list[str]:
    """Split Zolai text into whitespace-separated tokens."""
    return text.split()


def detokenize_zolai(tokens: list[str]) -> str:
    """Join tokens back into Zolai text."""
    return " ".join(tokens)


def word_root(word: str) -> str:
    """Get the base root of a Zolai word (strip common suffixes)."""
    # Strip possessive suffix '
    w = word.rstrip("'")
    # Strip common suffixes
    for suffix in ("na", "te", "tung", "kawm", "zat"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            candidate = w[: -len(suffix)]
            if len(candidate) >= 3:
                return candidate
    return w


def lookup_english(word: str, d: dict[str, dict[str, str]]) -> str:
    """Look up English translation for a Zolai word."""
    w = word.rstrip("'").lower()
    if w in d:
        return d[w]["english"]
    # Try root
    root = word_root(w)
    if root in d:
        return d[root]["english"]
    return w


def is_pronoun(token: str) -> bool:
    """Check if token is a subject pronoun."""
    return token.rstrip("'") in SUBJECT_PRONOUNS


def is_ergative(token: str) -> bool:
    """Check if token is the ergative particle."""
    return token == "in"


def classify_zolai_noun(word: str) -> str:
    """Classify a Zolai noun into a semantic category.

    Returns: 'animate', 'inanimate', 'abstract', 'people_object',
             'concrete_object', 'abstract_object', or 'unknown'.
    """
    w = word.rstrip("'").lower()
    root = word_root(w).lower()

    for d in (
        ANIMATE_SUBJECTS,
        INANIMATE_SUBJECTS,
        ABSTRACT_SUBJECTS,
        PEOPLE_OBJECTS,
        CONCRETE_OBJECTS,
        ABSTRACT_OBJECTS,
    ):
        for key in d:
            if key.lower() == w or key.lower() == root:
                if d is ANIMATE_SUBJECTS or d is PEOPLE_OBJECTS:
                    return "animate"
                if d is INANIMATE_SUBJECTS or d is CONCRETE_OBJECTS:
                    return "inanimate"
                return "abstract"
    return "unknown"


def pick_replacement(word: str, category: str, rng: random.Random) -> str:
    """Pick a replacement noun from the same semantic category."""
    w = word.rstrip("'").lower()
    root = word_root(w).lower()

    if category == "animate":
        candidates = [k for k in ANIMATE_SUBJECTS if k.lower() != w and k.lower() != root]
    elif category == "inanimate":
        candidates = [k for k in INANIMATE_SUBJECTS if k.lower() != w and k.lower() != root]
    elif category == "abstract":
        candidates = [k for k in ABSTRACT_SUBJECTS if k.lower() != w and k.lower() != root]
    else:
        # Fallback — try people objects for animate, concrete for inanimate
        if category == "animate":
            candidates = [k for k in PEOPLE_OBJECTS if k.lower() != w and k.lower() != root]
        else:
            candidates = [k for k in CONCRETE_OBJECTS if k.lower() != w and k.lower() != root]

    if not candidates:
        return word  # keep original if no replacement found

    return rng.choice(candidates)


# ---------------------------------------------------------------------------
# Verb extraction and analysis
# ---------------------------------------------------------------------------

# All known verb roots (from verb database + common verbs)
VERB_ROOTS: set[str] = {
    "ci", "hei", "tung", "hoih", "nei", "piang", "bawl", "lei", "sung", "in",
    "om", "kawm", "phat", "mu", "sim", "thupha", "na", "pau", "gen", "tampi",
    "uh", "piangsak", "pia", "chang", "kia", "thei", "gam",
}

# Subject pronouns → English mapping (used for English reconstruction)
PRONOUN_ENGLISH: dict[str, str] = {
    "ka": "I", "ka": "I",
    "na": "you", "na": "you",
    "a": "he", "a": "she", "a": "it",
    "i": "she",
    "ki": "we", "ki": "they",
    "amah": "he", "amah": "she",
}

# Named entities in Bible (Zolai form → English)
NAMED_ENTITIES: dict[str, str] = {
    "pasian": "God", "topa": "the Lord",
    "david": "David", "adam": "Adam", "noah": "Noah",
    "israel": "Israel", "jesuh": "Jesus", "moses": "Moses",
    "abraham": "Abraham", "eli": "Eli", "samuel": "Samuel",
    "solomon": "Solomon", "isaac": "Isaac", "jacob": "Jacob",
    "seth": "Seth", "enosh": "Enosh", "kenan": "Kenan",
    "jared": "Jared", "enok": "Enoch", "methuselah": "Methuselah",
    "lamek": "Lamech",
}


def extract_verb_from_sentence(tokens: list[str]) -> str | None:
    """Extract the main verb from a Zolai sentence.

    Searches for known verbs from the verb database. Returns the verb root
    or None if no verb is found.
    """
    # Check from end (verb usually comes last in SOV)
    for token in reversed(tokens):
        w = token.rstrip("'").lower()
        root = word_root(w)
        if w in VERB_ROOTS or root in VERB_ROOTS:
            return root

    return None


def find_object_in_sentence(
    tokens: list[str], verb_pos: int | None, d: dict[str, dict[str, str]]
) -> tuple[int, str] | None:
    """Find the object in the sentence relative to verb position.

    Returns (index, word) or None.
    """
    if verb_pos is None or verb_pos < 1:
        return None

    # In SOV: S + in + O + V — object is typically just before verb
    for i in range(verb_pos - 1, max(verb_pos - 3, 0) - 1, -1):
        if i < 0:
            break
        candidate = tokens[i].rstrip("'").lower()
        # Skip particles and pronouns
        if candidate in SUBJECT_PRONOUNS or candidate in ("in", "hi", "hiam", "a"):
            continue
        # Skip tense/negation markers
        if candidate in ("kei", "lo", "ding", "sak", "ah", "hen"):
            continue
        return i, candidate

    return None


def find_subject_in_sentence(tokens: list[str]) -> tuple[int, str] | None:
    """Find the subject in the sentence.

    Returns (index, word) or None.
    """
    if not tokens:
        return None

    # Check first token — could be pronoun or noun
    first = tokens[0].rstrip("'").lower()
    if first in SUBJECT_PRONOUNS:
        return 0, first
    if first in ANIMATE_SUBJECTS or first in INANIMATE_SUBJECTS or first in NAMED_ENTITIES:
        return 0, first

    # Check second token (after potential possessive)
    if len(tokens) > 1:
        second = tokens[1].rstrip("'").lower()
        if second in ("in", "ta", "tate", "suante"):
            # "X in..." or "X' ta..." pattern — X is subject
            return 0, first

    return None


# ---------------------------------------------------------------------------
# Variation generation
# ---------------------------------------------------------------------------


def _tense_marker_for_verb(verb: str, tense: str) -> str:
    """Get the appropriate tense-marked form of a verb."""
    markers = {
        "past": "sak",
        "progressive": "ah",
        "completive": "hen",
        "future": "ding",
    }
    marker = markers.get(tense, "")
    if not marker:
        return verb
    # For future, the marker goes before the verb
    if tense == "future":
        return f"{marker} {verb}"
    # For other tenses, it attaches to the verb
    return f"{verb}{marker}"


def create_negation(tokens: list[str], verb_pos: int) -> list[str]:
    """Add kei negation before the verb."""
    new_tokens = list(tokens)
    new_tokens.insert(verb_pos, "kei")
    return new_tokens


def create_question(tokens: list[str]) -> list[str]:
    """Add hiam question marker at end."""
    new_tokens = list(tokens)
    if new_tokens and new_tokens[-1].rstrip("'").lower() in ("hi", "a"):
        new_tokens[-1] = "hiam"
    elif new_tokens and new_tokens[-1].rstrip("'").lower() != "hiam":
        new_tokens.append("hiam")
    return new_tokens


def create_tense_variation(tokens: list[str], verb_pos: int, tense: str) -> list[str]:
    """Change tense of the verb."""
    new_tokens = list(tokens)
    verb = new_tokens[verb_pos].rstrip("'")
    marked = _tense_marker_for_verb(verb, tense)
    new_tokens[verb_pos] = marked
    return new_tokens


def _pick_subject_replacement(subject_word: str, rng: random.Random) -> str:
    """Pick a replacement subject from the same semantic category."""
    w = subject_word.rstrip("'").lower()
    category = classify_zolai_noun(w)

    if category in ("animate", "unknown"):
        candidates = [k for k in ANIMATE_SUBJECTS if k.lower() != w]
    elif category == "inanimate":
        candidates = [k for k in INANIMATE_SUBJECTS if k.lower() != w]
    else:
        candidates = [k for k in ABSTRACT_SUBJECTS if k.lower() != w]

    if not candidates:
        return subject_word
    return rng.choice(candidates)


def _pick_object_replacement(object_word: str, verb: str, rng: random.Random) -> str:
    """Pick a replacement object compatible with the verb."""
    w = object_word.rstrip("'").lower()
    compat = VERB_OBJECT_COMPAT.get(verb, [])

    if compat:
        candidates = [o for o in compat if o.lower() != w]
        if candidates:
            return rng.choice(candidates)

    # Fallback: category match
    category = classify_zolai_noun(w)
    if category == "animate":
        candidates = [k for k in PEOPLE_OBJECTS if k.lower() != w]
    elif category == "inanimate":
        candidates = [k for k in CONCRETE_OBJECTS if k.lower() != w]
    else:
        candidates = [k for k in ABSTRACT_OBJECTS if k.lower() != w]

    if not candidates:
        return object_word
    return rng.choice(candidates)


def _zo_to_english_word(word: str, d: dict[str, dict[str, str]]) -> str:
    """Convert a Zolai word to English for translation."""
    w = word.rstrip("'").lower()

    # Check named entities first
    if w in NAMED_ENTITIES:
        return NAMED_ENTITIES[w]

    # Check animate subjects
    if w in ANIMATE_SUBJECTS:
        return ANIMATE_SUBJECTS[w]
    if w in INANIMATE_SUBJECTS:
        return INANIMATE_SUBJECTS[w]
    if w in ABSTRACT_SUBJECTS:
        return ABSTRACT_SUBJECTS[w]
    if w in PEOPLE_OBJECTS:
        return PEOPLE_OBJECTS[w]
    if w in CONCRETE_OBJECTS:
        return CONCRETE_OBJECTS[w]
    if w in ABSTRACT_OBJECTS:
        return ABSTRACT_OBJECTS[w]

    # Dictionary lookup
    if w in d:
        return d[w]["english"]

    # Root lookup
    root = word_root(w)
    if root in d:
        return d[root]["english"]

    return w


def rebuild_english_from_variations(
    original_en: str,
    variation_type: str,
    old_zo: str,
    new_zo: str,
    d: dict[str, dict[str, str]],
) -> str:
    """Rebuild English translation from the original.

    For subject/object replacement: find and replace the corresponding
    English word in the original translation.
    For tense/negation/question: apply simple transformations.
    """
    en = original_en

    if variation_type == "subject":
        # Find the English word for the old subject and replace with new
        old_en = _zo_to_english_word(old_zo, d)
        new_en = _zo_to_english_word(new_zo, d)
        if old_en.lower() in en.lower():
            # Case-insensitive replacement preserving case
            pattern = re.compile(re.escape(old_en), re.IGNORECASE)
            en = pattern.sub(new_en, en, count=1)
        elif en.split():
            # Fallback: replace first word (subject position in English)
            words = en.split()
            words[0] = new_en
            en = " ".join(words)

    elif variation_type == "object":
        old_en = _zo_to_english_word(old_zo, d)
        new_en = _zo_to_english_word(new_zo, d)
        if old_en.lower() in en.lower():
            pattern = re.compile(re.escape(old_en), re.IGNORECASE)
            en = pattern.sub(new_en, en, count=1)

    elif variation_type == "tense_past":
        if " did " not in en.lower():
            en = f"{en} (in the past)"

    elif variation_type == "tense_future":
        if "will" not in en.lower():
            en = f"will {en}"

    elif variation_type == "tense_progressive":
        en = f"{en} (ongoing)"

    elif variation_type == "negation":
        en_lower = en.lower()
        if en_lower.startswith("will "):
            en = "will not " + en[5:]
        elif en_lower.startswith("do "):
            en = "do not " + en[3:]
        elif en_lower.startswith("does "):
            en = "does not " + en[5:]
        else:
            en = f"do not {en}"

    elif variation_type == "question":
        en = en.rstrip(".")
        en = en.rstrip()
        en += "?"

    # Capitalize first letter
    if en:
        en = en[0].upper() + en[1:]

    # Clean up
    en = en.replace("  ", " ").strip()
    if "?" in en:
        en = en.rstrip(".") + "?"
    elif not en.endswith(".") and not en.endswith("?") and not en.endswith(";"):
        en += "."

    return en


# ---------------------------------------------------------------------------
# Main variation pipeline
# ---------------------------------------------------------------------------


def generate_variations_from_verse(
    verse: dict[str, str],
    d: dict[str, dict[str, str]],
    rng: random.Random,
    max_variations: int = 3,
) -> list[dict[str, str]]:
    """Generate training variations from a single Bible verse.

    Creates multiple variations by applying controlled transformations
    to the real Bible sentence while keeping the verb structure intact.

    Returns list of {zolai, english, pattern, source} dicts.
    """
    zo_raw = verse.get("zo_tdb77")
    en_raw = verse.get("en_kJV")
    zo = zo_raw.strip() if isinstance(zo_raw, str) else ""
    en = en_raw.strip() if isinstance(en_raw, str) else ""
    ref_raw = verse.get("ref")
    ref = ref_raw.strip() if isinstance(ref_raw, str) else ""

    if not zo or not en:
        return []

    tokens = tokenize_zolai(zo)
    if len(tokens) < 3:
        return []

    is_short = len(tokens) <= 8  # Only do subject/object swap on short sentences

    variations: list[dict[str, str]] = []

    # 1. Original sentence (if it's a complete sentence with verb)
    verb = extract_verb_from_sentence(tokens)
    if verb:
        variations.append(
            {
                "zolai": zo,
                "english": en,
                "pattern": "bible_original",
                "source": ref,
            }
        )

    # Find structural positions
    verb_pos = None
    known_verbs = VERB_ROOTS
    for i, t in enumerate(reversed(tokens)):
        idx = len(tokens) - 1 - i
        w = t.rstrip("'").lower()
        if w in known_verbs or word_root(w) in known_verbs:
            verb_pos = idx
            break

    subject_info = find_subject_in_sentence(tokens)
    object_info = find_object_in_sentence(tokens, verb_pos, d) if verb_pos is not None else None

    # Determine allowed variation types based on sentence length
    if is_short:
        allowed_types = ["subject", "object", "tense_past", "tense_future",
                         "tense_progressive", "negation", "question"]
    else:
        # Long sentences: only tense/negation/question (no word swapping)
        allowed_types = ["tense_past", "tense_future",
                         "tense_progressive", "negation", "question"]

    # Generate up to max_variations variations
    attempts = 0
    seen = {zo.lower().strip()}

    while len(variations) < max_variations and attempts < max_variations * 3:
        attempts += 1
        variation_type = rng.choice(allowed_types)

        new_tokens = list(tokens)
        new_en = en
        pattern = ""
        changed = False
        old_zo_word = ""

        if variation_type == "subject" and subject_info and is_short:
            pos, word = subject_info
            old_zo_word = word
            replacement = _pick_subject_replacement(word, rng)
            new_tokens[pos] = replacement
            new_en = rebuild_english_from_variations(
                en, "subject", word, replacement, d
            )
            pattern = "subject_replacement"
            changed = True

        elif variation_type == "object" and object_info and verb and is_short:
            pos, word = object_info
            old_zo_word = word
            replacement = _pick_object_replacement(word, verb, rng)
            new_tokens[pos] = replacement
            new_en = rebuild_english_from_variations(
                en, "object", word, replacement, d
            )
            pattern = "object_replacement"
            changed = True

        elif variation_type == "tense_past" and verb_pos is not None:
            new_tokens = create_tense_variation(new_tokens, verb_pos, "past")
            new_en = f"{en} [past tense]"
            pattern = "tense_past"
            changed = True

        elif variation_type == "tense_future" and verb_pos is not None:
            new_tokens = create_tense_variation(new_tokens, verb_pos, "future")
            new_en = f"{en} [future]"
            pattern = "tense_future"
            changed = True

        elif variation_type == "tense_progressive" and verb_pos is not None:
            new_tokens = create_tense_variation(new_tokens, verb_pos, "progressive")
            new_en = f"{en} [ongoing]"
            pattern = "tense_progressive"
            changed = True

        elif variation_type == "negation" and verb_pos is not None:
            new_tokens = create_negation(new_tokens, verb_pos)
            new_en = f"{en} [not]"
            pattern = "negation"
            changed = True

        elif variation_type == "question":
            new_tokens = create_question(new_tokens)
            new_en = f"{en}?"
            pattern = "question"
            changed = True

        if not changed:
            continue

        new_zo = detokenize_zolai(new_tokens)
        key = new_zo.lower().strip()

        if key in seen:
            continue
        seen.add(key)

        variations.append(
            {
                "zolai": new_zo,
                "english": new_en,
                "pattern": pattern,
                "source": ref,
            }
        )

    return variations[:max_variations]


# ---------------------------------------------------------------------------
# Main generation pipeline
# ---------------------------------------------------------------------------


def generate_sentences(
    max_sentences: int = 5000,
    seed: int = 42,
    verbose: bool = True,
) -> list[dict[str, str]]:
    """Generate Zolai training sentences from Bible templates.

    Args:
        max_sentences: Maximum number of sentences to generate.
        seed: Random seed for reproducibility.
        verbose: Print progress.

    Returns:
        List of sentence dicts with zolai, english, pattern, source.
    """
    rng = random.Random(seed)

    if verbose:
        print("Loading Bible parallel corpus...")
    corpus = load_parallel_corpus()
    if verbose:
        print(f"  Loaded {len(corpus)} Bible verses")

    if verbose:
        print("Loading dictionary...")
    d = load_dictionary()
    if verbose:
        print(f"  Loaded {len(d)} dictionary entries")

    # Filter: only keep verses with 3-12 Zolai words (short, clear sentences)
    filtered = []
    for v in corpus:
        zo = v.get("zo_tdb77")
        if zo and isinstance(zo, str):
            zo_strip = zo.strip()
            if 3 <= len(zo_strip.split()) <= 12:
                filtered.append(v)
    if verbose:
        print(f"  Filtered to {len(filtered)} verses (3-12 words)")

    # Shuffle with seed for reproducibility
    rng.shuffle(filtered)

    # Generate variations from Bible verses
    all_variations: list[dict[str, str]] = []
    seen: set[str] = set()

    # Process ALL filtered verses, limit to 3 variations per verse
    if verbose:
        print(f"Processing {len(filtered)} filtered verses (max 3 variations each)...")

    for i, verse in enumerate(filtered):
        variations = generate_variations_from_verse(verse, d, rng, max_variations=3)

        for v in variations:
            key = v["zolai"].lower().strip()
            if key not in seen:
                seen.add(key)
                all_variations.append(v)

        if len(all_variations) >= max_sentences:
            break

        if verbose and (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(filtered)} verses, "
                  f"generated {len(all_variations)} variations...")

    # Trim to max_sentences
    sentences = all_variations[:max_sentences]

    if verbose:
        print(f"  Done: {len(sentences)} unique sentences from "
              f"{len(filtered)} filtered Bible verses")

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
        description="Generate Zolai sentences from Bible templates with semantic variation."
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
    print("  Bible-template semantic variation")
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
        print(f"  {s['zolai']:60s} → {s['english'][:50]:50s}  [{s['pattern']}]")

    # Stats
    patterns: dict[str, int] = {}
    sources: dict[str, int] = {}
    for s in sentences:
        p = s["pattern"]
        patterns[p] = patterns.get(p, 0) + 1
        src = s["source"]
        sources[src] = sources.get(src, 0) + 1

    print()
    print("Pattern type distribution:")
    for t, c in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {t:25s} {c:6d} ({c * 100 // len(sentences)}%)")

    print()
    print(f"Unique source verses: {len(sources)}")


if __name__ == "__main__":
    main()
