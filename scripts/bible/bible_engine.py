#!/usr/bin/env python3
"""
ZOLAI BIBLE ENGINE — Comprehensive Language Learning & Grammar Engine
Full verse analysis • Progressive learning • Spaced repetition • Corpus search
Dictionary-first • Evidence-scoring • No external NLP libs
"""

import json
import re
import argparse
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

# ══════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent.parent  # zolai-ai root
DATA = WORKSPACE / "data"
DICT_ZO_EN = DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
SUPPLEMENT_DICT = DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"
CORPUS = DATA / "bible" / "parallel_corpus_v1.jsonl"
GRAMMAR_PATTERNS = DATA / "bible" / "grammar_patterns_text.jsonl"
VOCAB_INDEX = DATA / "bible" / "vocab_index_full.jsonl"
WORD_COLLOCATIONS = DATA / "bible" / "word_collocations.jsonl"
SENTENCE_STRUCTURES = DATA / "bible" / "sentence_structures.jsonl"
VERB_DB = DATA / "bible" / "verb_database_v1.jsonl"
PARTICLE_DB = DATA / "bible" / "particle_database_v1.jsonl"
PHRASES_DB = DATA / "bible" / "phrases_v1.jsonl"
WORD_ALIGNMENTS = DATA / "bible" / "word_alignments_v1.jsonl"
KB_DIR = DATA / "bible" / "knowledge_base"

# ══════════════════════════════════════════════════════════════════════
# COLORS
# ══════════════════════════════════════════════════════════════════════
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
B = "\033[0;34m"
C = "\033[0;36m"
M = "\033[0;35m"
NC = "\033[0m"

# ══════════════════════════════════════════════════════════════════════
# EVIDENCE LEVELS
# ══════════════════════════════════════════════════════════════════════
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
UNCERTAIN = "UNCERTAIN"

# ══════════════════════════════════════════════════════════════════════
# LEARNING LEVELS
# ══════════════════════════════════════════════════════════════════════
LEVEL_NAMES = {
    1: "Beginner — Common words (top 100)",
    2: "Elementary — Basic phrases (200 words)",
    3: "Intermediate — Sentence patterns (500 words)",
    4: "Upper-Intermediate — Grammar structures (1000 words)",
    5: "Advanced — Complex sentences (2000 words)",
    6: "Proficient — Idiomatic usage (3500 words)",
    7: "Fluent — Literary analysis (5000 words)",
    8: "Mastery — Full Bible vocabulary (all words)",
}

LEVEL_THRESHOLDS = {
    1: 100, 2: 200, 3: 500, 4: 1000,
    5: 2000, 6: 3500, 7: 5000, 8: 999999,
}

# ══════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════
def load_zo_en_dict() -> dict[str, list[str]]:
    """Load Zolai→English master dictionary."""
    d: dict[str, list[str]] = {}
    for path in [SUPPLEMENT_DICT, DICT_ZO_EN]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    hw = (rec.get("zolai") or rec.get("headword") or "").strip().lower()
                    if not hw:
                        continue
                    eng = rec.get("english") or rec.get("translations") or []
                    if isinstance(eng, str):
                        eng = [eng]
                    if hw not in d:
                        d[hw] = eng
    return d


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    items = []
    if path.exists():
        with open(path) as f:
            for line in f:
                items.append(json.loads(line))
    return items


def load_corpus_by_book(book: str) -> list[dict]:
    """Load parallel corpus filtered to a single book."""
    verses = []
    if CORPUS.exists():
        with open(CORPUS) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("book") == book:
                    verses.append(rec)
    return verses


def load_grammar_patterns() -> list[dict]:
    """Load grammar patterns."""
    return load_jsonl(GRAMMAR_PATTERNS)


def load_verb_database() -> dict[str, dict]:
    """Load verb database indexed by verb."""
    vdb = {}
    for rec in load_jsonl(VERB_DB):
        v = rec.get("verb", "").strip().lower()
        if v:
            vdb[v] = rec
    return vdb


def load_particle_database() -> dict[str, dict]:
    """Load particle database indexed by particle."""
    pdb = {}
    for rec in load_jsonl(PARTICLE_DB):
        p = rec.get("particle", "").strip().lower()
        if p:
            pdb[p] = rec
    return pdb


def load_phrase_database() -> list[dict]:
    """Load phrase database."""
    return load_jsonl(PHRASES_DB)


def load_phrase_dict() -> dict[str, str]:
    """Build phrase dictionary from supplement dict (multi-word headwords).

    Maps multi-word Zolai phrases to their English meanings.
    Example: "a kipat cilin" → "in the beginning"
    """
    phrase_dict: dict[str, str] = {}
    # Load from supplement dictionary (curated phrases)
    supp_path = DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"
    if supp_path.exists():
        with open(supp_path) as f:
            for line in f:
                rec = json.loads(line)
                hw = rec.get("headword", "").strip().lower()
                trans = rec.get("translations", [])
                if isinstance(trans, list):
                    eng = trans[0] if trans else ""
                else:
                    eng = str(trans)
                if hw and " " in hw and eng:
                    phrase_dict[hw] = eng
    # Also load from ZO→EN master (multi-word entries)
    master_path = DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
    if master_path.exists():
        with open(master_path) as f:
            for line in f:
                rec = json.loads(line)
                hw = rec.get("zolai", "").strip().lower()
                eng = rec.get("english", [])
                if isinstance(eng, list):
                    eng = eng[0] if eng else ""
                if hw and " " in hw and eng and hw not in phrase_dict:
                    phrase_dict[hw] = eng
    return phrase_dict


def load_collocations() -> dict[str, int]:
    """Load word collocations as {phrase: frequency}."""
    coll = {}
    for rec in load_jsonl(WORD_COLLOCATIONS):
        ph = rec.get("collocation", "").strip().lower()
        freq = rec.get("frequency", 0)
        if ph:
            coll[ph] = freq
    return coll


def load_vocab_index() -> dict[str, dict]:
    """Load vocab index indexed by word."""
    vidx = {}
    for rec in load_jsonl(VOCAB_INDEX):
        w = rec.get("word", "").strip().lower()
        if w:
            vidx[w] = rec
    return vidx


# ══════════════════════════════════════════════════════════════════════
# EVIDENCE SCORER
# ══════════════════════════════════════════════════════════════════════
class EvidenceScorer:
    """Score the strength of linguistic evidence."""

    @staticmethod
    def score_dict_hit(freq: int) -> str:
        if freq > 1000:
            return HIGH
        if freq > 100:
            return MEDIUM
        if freq > 10:
            return LOW
        return UNCERTAIN

    @staticmethod
    def score_pattern(freq: int, example_count: int) -> str:
        if freq > 500 and example_count >= 5:
            return HIGH
        if freq > 100 and example_count >= 3:
            return MEDIUM
        if freq > 10:
            return LOW
        return UNCERTAIN

    @staticmethod
    def score_corpus_match(match_count: int, total: int) -> str:
        if total == 0:
            return UNCERTAIN
        ratio = match_count / total
        if ratio > 0.8:
            return HIGH
        if ratio > 0.5:
            return MEDIUM
        if ratio > 0.2:
            return LOW
        return UNCERTAIN


# ══════════════════════════════════════════════════════════════════════
# GLOSSING ENGINE
# ══════════════════════════════════════════════════════════════════════
class GlossingEngine:
    """Enhanced word alignment using dictionary + corpus + phrase lookup."""

    def __init__(self, zo_en: dict[str, list[str]], vocab: dict[str, dict],
                 phrases: list[dict], collocations: dict[str, int],
                 phrase_dict: dict[str, str] | None = None):
        self.zo_en = zo_en
        self.vocab = vocab
        self.phrases = phrases
        self.collocations = collocations
        # Build phrase dictionary: multi-word headword → English meaning
        self.phrase_dict: dict[str, str] = phrase_dict or {}
        self.stats = {"dict_hit": 0, "vocab_hit": 0, "phrase_hit": 0, "miss": 0}

    def gloss_word(self, word: str) -> dict:
        """Gloss a single Zolai word."""
        w = word.strip().lower()

        # 1. Check ZO→EN dictionary (highest priority)
        if w in self.zo_en:
            self.stats["dict_hit"] += 1
            return {
                "word": word,
                "gloss": self.zo_en[w][0] if self.zo_en[w] else "?",
                "alternatives": self.zo_en[w][1:3],
                "source": "dict_zo_en",
                "confidence": HIGH,
            }

        # 2. Check vocab index (frequency + translations)
        if w in self.vocab:
            entry = self.vocab[w]
            freq = entry.get("frequency", 0)
            trans = entry.get("translations", [])
            self.stats["vocab_hit"] += 1
            return {
                "word": word,
                "gloss": trans[0] if trans else "?",
                "alternatives": trans[1:3],
                "source": "vocab_index",
                "confidence": EvidenceScorer.score_dict_hit(freq),
                "frequency": freq,
            }

        # 3. Miss
        self.stats["miss"] += 1
        return {
            "word": word,
            "gloss": "?",
            "alternatives": [],
            "source": "miss",
            "confidence": UNCERTAIN,
        }

    def gloss_verse(self, zo_text: str) -> list[dict]:
        """Gloss a verse with phrase-first, then word-by-word fallback.

        Strategy:
        1. Try to match multi-word phrases (2-5 words, longest first)
        2. For unmatched segments, fall back to single-word lookup
        """
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        if not words:
            return []

        result: list[dict] = []
        i = 0
        while i < len(words):
            matched = False
            # Try multi-word phrases (2-5 words, longest first)
            for length in range(min(5, len(words) - i), 1, -1):
                candidate = " ".join(w.lower() for w in words[i:i + length])
                if candidate in self.phrase_dict:
                    self.stats["phrase_hit"] += 1
                    result.append({
                        "word": " ".join(words[i:i + length]),
                        "gloss": self.phrase_dict[candidate],
                        "alternatives": [],
                        "source": "phrase_dict",
                        "confidence": HIGH,
                        "phrase": True,
                    })
                    i += length
                    matched = True
                    break
            if not matched:
                result.append(self.gloss_word(words[i]))
                i += 1
        return result

    def get_stats(self) -> dict:
        return dict(self.stats)


# ══════════════════════════════════════════════════════════════════════
# PHRASE EXTRACTOR
# ══════════════════════════════════════════════════════════════════════
class PhraseExtractor:
    """Extract NP/VP/ADJ/ADV phrases + idioms + collocations."""

    # Known phrase markers
    NP_MARKERS: ClassVar[set[str]] = {"ta", "mite", "pen", "a", "hih", "kei"}
    VP_MARKERS: ClassVar[set[str]] = {
        "ci", "hei", "om", "nek", "mu", "gal", "thlak", "topa"
    }
    ADJ_MARKERS: ClassVar[set[str]] = {"hih", "kha", "sang"}
    CONJ_MARKERS: ClassVar[set[str]] = {"leh", "hang", "cih", "sung"}

    def __init__(self, phrases_db: list[dict], collocations: dict[str, int],
                 zo_en: dict[str, list[str]]):
        self.phrases_db = phrases_db
        self.collocations = collocations
        self.zo_en = zo_en

    def extract_collocations(self, words: list[str]) -> list[dict]:
        """Find known collocations in a word sequence."""
        found = []
        lower_words = [w.lower() for w in words]
        for length in range(2, min(5, len(lower_words) + 1)):
            for i in range(len(lower_words) - length + 1):
                phrase = " ".join(lower_words[i:i + length])
                if phrase in self.collocations:
                    found.append({
                        "phrase": phrase,
                        "words": words[i:i + length],
                        "frequency": self.collocations[phrase],
                        "type": "collocation",
                        "confidence": HIGH,
                    })
        return found

    def extract_phrases_from_db(self, zo_text: str) -> list[dict]:
        """Find known phrases from the phrase database."""
        found = []
        lower = zo_text.lower()
        for rec in self.phrases_db:
            phrase_zo = rec.get("zo", "").strip().lower()
            if phrase_zo and phrase_zo in lower:
                found.append({
                    "phrase": phrase_zo,
                    "frequency": rec.get("frequency", 0),
                    "type": rec.get("type", "phrase"),
                    "confidence": rec.get("confidence", MEDIUM),
                    "examples": rec.get("examples", [])[:2],
                })
        return found

    def classify_phrase(self, words: list[str]) -> str:
        """Classify a phrase by its dominant marker."""
        lower_words = [w.lower() for w in words]
        last = lower_words[-1] if lower_words else ""
        if last in self.VP_MARKERS:
            return "VP"
        if last in self.ADJ_MARKERS:
            return "ADJ"
        if last in self.NP_MARKERS or any(w in self.NP_MARKERS for w in lower_words):
            return "NP"
        if last in self.CONJ_MARKERS:
            return "CONJ"
        return "PHRASE"

    def extract_all(self, zo_text: str) -> list[dict]:
        """Extract all phrases from a verse."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        collocations = self.extract_collocations(words)
        db_phrases = self.extract_phrases_from_db(zo_text)
        return collocations + db_phrases


# ══════════════════════════════════════════════════════════════════════
# MORPHOLOGY ANALYZER
# ══════════════════════════════════════════════════════════════════════
class MorphologyAnalyzer:
    """Root + prefix (ka-/na-/a-/uh-) + suffix (-hi/-leh/-te/-in) decomposition."""

    PREFIXES: ClassVar[list[str]] = ["ka", "na", "uh", "a", "ki", "si", "tu"]
    SUFFIXES: ClassVar[list[str]] = ["hi", "leh", "te", "in", "in", "na", "pi", "te"]
    # Common inflectional endings
    INFLECTIONS: ClassVar[dict[str, str]] = {
        "ing": "progressive",
        "ed": "past",
        "s": "plural",
        "hi": "declarative",
        "leh": "conjunction",
        "te": "imperative",
        "in": "ergative/imperative",
        "na": "nominalizer",
    }

    def analyze(self, word: str) -> dict:
        """Decompose a word into morphemes."""
        w = word.strip().lower()
        result = {
            "word": word,
            "root": w,
            "prefix": None,
            "suffix": None,
            "morphemes": [w],
            "confidence": UNCERTAIN,
        }

        # Check prefix
        for pfx in sorted(self.PREFIXES, key=len, reverse=True):
            if w.startswith(pfx) and len(w) > len(pfx) + 1:
                root_candidate = w[len(pfx):]
                result["prefix"] = pfx
                result["root"] = root_candidate
                result["morphemes"] = [pfx, root_candidate]
                break

        # Check suffix
        root = result["root"]
        for sfx in sorted(self.SUFFIXES, key=len, reverse=True):
            if root.endswith(sfx) and len(root) > len(sfx) + 1:
                root_stem = root[:-len(sfx)]
                result["suffix"] = sfx
                result["root"] = root_stem
                result["morphemes"] = result["morphemes"][:1] + [root_stem, sfx]
                break

        # Classify inflection
        for ending, tag in self.INFLECTIONS.items():
            if w.endswith(ending):
                result["inflection"] = tag
                break

        # Confidence based on whether decomposition produced multiple morphemes
        if len(result["morphemes"]) > 1:
            result["confidence"] = LOW  # heuristic, needs corpus validation
        else:
            result["confidence"] = UNCERTAIN

        return result


# ══════════════════════════════════════════════════════════════════════
# GRAMMAR MATCHER
# ══════════════════════════════════════════════════════════════════════
class GrammarMatcher:
    """Pattern matching from grammar_patterns_text.jsonl."""

    # Common Zolai grammar patterns (SOV-related)
    PATTERNS: ClassVar[dict[str, dict]] = {
        "SOV": {
            "pattern": r"\b(\w+)\s+(?:(?:ki|si|tu|a|in)\s+)?(\w+)\s+([a-zA-Z']+)\b",
            "description": "Subject + Object + Verb (SOV order)",
            "confidence": HIGH,
    
        "negation_kei": {
            "pattern": r"\b(\w+)\s+kei\s+(?:hi|ding|un|leh)\b",
            "description": "1st/2nd person negation (kei)",
            "confidence": HIGH,
        },
        "negation_lo": {
            "pattern": r"\b(\w+)\s+lo\s+(?:hi|ding|un|leh)\b",
            "description": "3rd person negation (lo)",
            "confidence": HIGH,
        },
        "question_diam": {
            "pattern": r"\bdiam\b",
            "description": "Future question marker",
            "confidence": HIGH,
        },
        "question_bang_hang": {
            "pattern": r"\bbang\s+hang\b",
            "description": "Content question (why/how)",
            "confidence": HIGH,
        },
        "future_ding": {
            "pattern": r"\bding\s+(?:hi|uh|a)\b",
            "description": "Future tense marker (ding)",
            "confidence": HIGH,
        },
        "past_ciangin": {
            "pattern": r"\bciangin\s+",
            "description": "Past tense marker (ciangin)",
            "confidence": HIGH,
        },
        "completive_ta": {
            "pattern": r"\b(\w+)\s+ta\s+",
            "description": "Completive aspect (ta)",
            "confidence": HIGH,
        },
        "progressive_lai": {
            "pattern": r"\b(?:tua|hih)\s+lai\b",
            "description": "Progressive aspect (lai)",
            "confidence": HIGH,
        },
        "person_ka": {
            "pattern": r"\bka\s+\w+",
            "description": "1st person singular agreement",
            "confidence": HIGH,
        },
        "person_na": {
            "pattern": r"\bna\s+\w+",
            "description": "2nd person singular agreement",
            "confidence": HIGH,
        },
        "person_a": {
            "pattern": r"\ba\s+\w+",
            "description": "3rd person singular agreement",
            "confidence": HIGH,
        },
        "person_i": {
            "pattern": r"\bi\s+\w+",
            "description": "1st person plural agreement",
            "confidence": HIGH,
        },
        "person_ki": {
            "pattern": r"\bki\s+\w+",
            "description": "Reflexive/middle voice",
            "confidence": HIGH,
        },    },
        "negation": {
            "pattern": r"\b(\w+)\s+(?:lo|si|tu)\b",
            "description": "Negation particle (lo/si/tu)",
            "confidence": HIGH,
        },
        "question_hiam": {
            "pattern": r"\bhiam\b",
            "description": "Universal question marker",
            "confidence": HIGH,
        },
        "question_bang": {
            "pattern": r"\bbang\s+ci\b",
            "description": "Content question (what/how)",
            "confidence": MEDIUM,
        },
        "declarative_hi": {
            "pattern": r"\b(\w+)\s+hi\b",
            "description": "Declarative sentence-final particle",
            "confidence": HIGH,
        },
        "ergative_in": {
            "pattern": r"\b\w+\s+in\s+\w+\b",
            "description": "Ergative case marker (in)",
            "confidence": HIGH,
        },
        "possessive_ta": {
            "pattern": r"\b(\w+)[\u0027\u2019]\s*ta\b",
            "description": "Possessive marker (ta)",
            "confidence": HIGH,
        },
        "jussive_kei": {
            "pattern": r"\b\w+\s+kei\b",
            "description": "Jussive/hortative (let...)",
            "confidence": MEDIUM,
        },
        "quotative_sung": {
            "pattern": r"\b\w+\s+sung\s+",
            "description": "Quotative/inside marker",
            "confidence": MEDIUM,
        },
        "conjunction_leh": {
            "pattern": r"\bleh\b",
            "description": "Coordinating conjunction (and)",
            "confidence": HIGH,
        },
        "conjunction_hang": {
            "pattern": r"\bhang\b",
            "description": "Conjunction (but/however)",
            "confidence": MEDIUM,
        },
    }

    def __init__(self, patterns_db: list[dict]):
        self.patterns_db = patterns_db
        self.pattern_counts = Counter()
        for rec in patterns_db:
            p = rec.get("pattern", "")
            if p:
                self.pattern_counts[p] += rec.get("frequency", 0)

    def match_all(self, zo_text: str) -> list[dict]:
        """Match all known patterns in a verse."""
        matches = []
        lower = zo_text.lower()
        for name, info in self.PATTERNS.items():
            regex = info["pattern"]
            found = re.findall(regex, zo_text)
            if found:
                matches.append({
                    "pattern": name,
                    "description": info["description"],
                    "matches": found[:5],
                    "confidence": info["confidence"],
                    "corpus_freq": self.pattern_counts.get(name, 0),
                })
        return matches

    def check_negation(self, zo_text: str) -> dict:
        """Check negation patterns with person-specific rules."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        
        # Check for person markers
        has_ka = "ka" in words
        has_na = "na" in words
        has_a = "a" in words
        
        # Check for negation particles
        has_kei = "kei" in words
        has_lo = "lo" in words
        
        # Determine person
        person = None
        if has_ka or has_na:
            person = "1st/2nd"
        elif has_a:
            person = "3rd"
        
        # Check negation pattern
        if has_kei and person == "1st/2nd":
            return {
                "correct": True,
                "person": person,
                "negation": "kei",
                "reason": "1st/2nd person uses kei",
            }
        elif has_lo and person == "3rd":
            return {
                "correct": True,
                "person": person,
                "negation": "lo",
                "reason": "3rd person uses lo",
            }
        elif has_kei and person == "3rd":
            return {
                "correct": False,
                "person": person,
                "negation": "kei",
                "reason": "3rd person should use lo, not kei",
            }
        elif has_lo and person == "1st/2nd":
            return {
                "correct": False,
                "person": person,
                "negation": "lo",
                "reason": "1st/2nd person should use kei, not lo",
            }
        
        return {
            "correct": None,
            "person": person,
            "negation": None,
            "reason": "no negation pattern found",
        }

    def check_question(self, zo_text: str) -> dict:
        """Check question patterns."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        
        if "hiam" in words:
            return {"type": "yes/no", "marker": "hiam", "correct": True}
        elif "diam" in words:
            return {"type": "future", "marker": "diam", "correct": True}
        elif "bang" in words and "hang" in words:
            return {"type": "content", "marker": "bang hang", "correct": True}
        elif "bang" in words and "ci" in words:
            return {"type": "content", "marker": "bang ci", "correct": True}
        
        return {"type": None, "marker": None, "correct": None}

    def check_verb_conjugation(self, zo_text: str) -> dict:
        """Check verb conjugation patterns."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        
        # Check for incorrect "an ne" pattern
        if "an" in words and "ne" in words:
            return {
                "correct": False,
                "issue": "an ne",
                "reason": "Use 'ne' directly, not 'an ne'",
                "suggestion": "ka ne hi",
            }
        
        # Check for incorrect "nek" usage
        if "nek" in words:
            # Check if it's in correct construction
            for i, word in enumerate(words):
                if word == "nek" and i > 0:
                    prev = words[i-1]
                    if prev in ["ka", "na", "a", "i"]:
                        return {
                            "correct": False,
                            "issue": "nek after pronoun",
                            "reason": "Use 'ne' directly after pronoun",
                            "suggestion": f"{prev} ne hi",
                        }
        
        return {"correct": None, "issue": None, "reason": None}

    def match_sov(self, zo_text: str) -> dict:
        """Check for SOV word order in a sentence."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        if len(words) < 3:
            return {"sov": False, "confidence": UNCERTAIN, "reason": "too_short"}

        # Heuristic: if last word could be a verb → SOV
        last = words[-1].lower()
        verb_markers = {"ci", "hei", "om", "nek", "mu", "gal", "thlak", "bawl",
                        "piangsak", "kia", "thei", "hong", "sung", "khawh"}
        if last in verb_markers:
            return {
                "sov": True,
                "confidence": HIGH,
                "subject": words[0],
                "verb": last,
                "reason": "verb_final",
            }
        return {"sov": False, "confidence": LOW, "reason": "no_verb_final"}


# ══════════════════════════════════════════════════════════════════════
# CLAUSE ANALYZER
# ══════════════════════════════════════════════════════════════════════
class ClauseAnalyzer:
    """Split sentences on coordinating conjunctions (leh, hang, cih)."""

    COORDINATORS: ClassVar[list[str]] = ["leh", "hang", "cih"]
    SUBORDINATORS: ClassVar[list[str]] = ["sung", "zat", "hih", "kia"]

    def split_clauses(self, zo_text: str) -> list[dict]:
        """Split verse into clauses."""
        clauses = []
        # Split on coordinators
        parts = re.split(r"\s+(?:leh|hang|cih)\s+", zo_text)
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            conj = None
            if i > 0:
                # Find which coordinator was used
                before = zo_text[:zo_text.find(part)]
                for c in self.COORDINATORS:
                    if c in before.split()[-2:]:
                        conj = c
                        break
            clauses.append({
                "text": part,
                "position": i,
                "conjunction": conj,
                "word_count": len(re.findall(r"[a-zA-Z\u0027\u2019]+", part)),
            })
        return clauses


# ══════════════════════════════════════════════════════════════════════
# CONTRASTIVE ANALYZER
# ══════════════════════════════════════════════════════════════════════
class ContrastiveAnalyzer:
    """Compare EN SVO vs ZO SOV, negation, questions, tense."""

    @staticmethod
    def analyze_order(zo_words: list[str], en_text: str) -> dict:
        """Compare ZO word order with EN word order."""
        en_words = re.findall(r"\b\w+\b", en_text.lower())
        zo_lower = [w.lower() for w in zo_words]

        differences = []
        # SOV vs SVO check
        if len(zo_lower) >= 3:
            last = zo_lower[-1]
            verb_candidates = {"ci", "hei", "om", "nek", "mu", "gal", "thlak",
                               "bawl", "piangsak", "kia", "thei", "hong", "sung"}
            if last in verb_candidates:
                differences.append({
                    "feature": "word_order",
                    "zo": "SOV",
                    "en": "SVO",
                    "confidence": HIGH,
                    "evidence": f"verb '{last}' is sentence-final",
                })

        return {
            "zo_order": "SOV" if differences else "unclear",
            "en_order": "SVO",
            "differences": differences,
        }

    @staticmethod
    def analyze_negation(zo_text: str) -> dict:
        """Analyze negation patterns."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text.lower())
        neg_words = {"lo", "si", "tu", "awi", "kha"}
        found_neg = [w for w in words if w in neg_words]
        return {
            "negation_present": bool(found_neg),
            "negation_words": found_neg,
            "pattern": "post-verbal negation (V + lo)" if "lo" in found_neg else "other",
            "confidence": HIGH if "lo" in found_neg else LOW,
        }

    @staticmethod
    def analyze_question(zo_text: str) -> dict:
        """Analyze question patterns."""
        lower = zo_text.lower()
        if "hiam" in re.findall(r"\b\w+\b", lower):
            return {"is_question": True, "type": "yes/no", "marker": "hiam", "confidence": HIGH}
        if "bang ci" in lower:
            return {"is_question": True, "type": "content", "marker": "bang ci", "confidence": MEDIUM}
        if "kua" in lower:
            return {"is_question": True, "type": "content", "marker": "kua", "confidence": MEDIUM}
        if lower.rstrip().endswith("?"):
            return {"is_question": True, "type": "unmarked", "marker": "?", "confidence": LOW}
        return {"is_question": False, "confidence": HIGH}

    @staticmethod
    def analyze_tense(zo_text: str, en_text: str) -> dict:
        """Analyze tense/aspect patterns."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text.lower())
        en_lower = en_text.lower()

        tense_markers = {
            "ding": "future",
            "uh": "perfective",
            "hi": "declarative",
            "in": "imperative",
        }
        found = []
        for w in words:
            if w in tense_markers:
                found.append({"marker": w, "tense": tense_markers[w]})

        # EN tense detection
        en_tense = "unknown"
        if any(w in en_lower for w in ["will", "shall"]):
            en_tense = "future"
        elif any(w in en_lower for w in ["was", "were", "did"]):
            en_tense = "past"
        elif any(w in en_lower for w in ["is", "are", "am"]):
            en_tense = "present"

        return {
            "zo_tense_markers": found,
            "en_tense": en_tense,
            "confidence": HIGH if found else LOW,
        }


# ══════════════════════════════════════════════════════════════════════
# VERB DATABASE (expanded)
# ══════════════════════════════════════════════════════════════════════
class VerbDatabase:
    """Expanded verb database with argument structure."""

    # Built-in common verbs (supplement to file)
    BUILTIN_VERBS: ClassVar[dict[str, dict]] = {
        "ci": {"english": ["say", "speak", "tell"], "transitivity": "transitive",
               "argument": "S + O + ci"},
        "hei": {"english": ["go", "walk"], "transitivity": "intransitive",
                "argument": "S + place + hei"},
        "om": {"english": ["be", "exist"], "transitivity": "copula",
               "argument": "S + om + complement"},
        "nek": {"english": ["eat", "consume"], "transitivity": "transitive",
                "argument": "S + O + nek"},
        "mu": {"english": ["see", "look"], "transitivity": "transitive",
               "argument": "S + O + mu"},
        "gal": {"english": ["can", "able"], "transitivity": "auxiliary",
                "argument": "S + gal + V"},
        "thlak": {"english": ["hit", "strike"], "transitivity": "transitive",
                  "argument": "S + O + thlak"},
        "topa": {"english": ["give"], "transitivity": "ditransitive",
                 "argument": "S + IO + DO + topa"},
        "bawl": {"english": ["create", "make"], "transitivity": "transitive",
                 "argument": "S + O + bawl"},
        "piangsak": {"english": ["create", "made"], "transitivity": "transitive",
                     "argument": "S + O + piangsak"},
        "kia": {"english": ["die", "perish"], "transitivity": "intransitive",
                "argument": "S + kia"},
        "thei": {"english": ["know", "understand"], "transitivity": "transitive",
                 "argument": "S + O + thei"},
        "hong": {"english": ["hear", "listen"], "transitivity": "transitive",
                 "argument": "S + O + hong"},
        "sung": {"english": ["give"], "transitivity": "ditransitive",
                 "argument": "S + IO + DO + sung"},
        "khawh": {"english": ["want", "desire"], "transitivity": "transitive",
                  "argument": "S + O + khawh"},
        "phat": {"english": ["take", "carry"], "transitivity": "transitive",
                 "argument": "S + O + phat"},
        "tleh": {"english": ["bring", "carry"], "transitivity": "transitive",
                 "argument": "S + O + tleh"},
        "kuh": {"english": ["kill", "destroy"], "transitivity": "transitive",
                "argument": "S + O + kuh"},
        "siang": {"english": ["sing", "praise"], "transitivity": "transitive",
                  "argument": "S + O + siang"},
        "tah": {"english": ["fear", "be afraid"], "transitivity": "intransitive",
                "argument": "S + tah"},
        "thupha": {"english": ["bless"], "transitivity": "transitive",
                   "argument": "S + O + thupha"},
        "kuankhiat": {"english": ["deliver", "rescue"], "transitivity": "transitive",
                      "argument": "S + O + kuankhiat"},
        "kumpi": {"english": ["king", "rule"], "transitivity": "intransitive",
                  "argument": "S + kumpi"},
        "ciah": {"english": ["send"], "transitivity": "transitive",
                 "argument": "S + O + ciah"},
        "khuah": {"english": ["wash", "clean"], "transitivity": "transitive",
                  "argument": "S + O + khuah"},
        "leng": {"english": ["run"], "transitivity": "intransitive",
                 "argument": "S + leng"},
        "phun": {"english": ["plant", "sow"], "transitivity": "transitive",
                 "argument": "S + O + phun"},
    }

    def __init__(self, verbs_db: list[dict]):
        self.verbs = dict(self.BUILTIN_VERBS)
        for rec in verbs_db:
            v = rec.get("verb", "").strip().lower()
            if v and v not in self.verbs:
                self.verbs[v] = rec

    def lookup(self, word: str) -> dict | None:
        return self.verbs.get(word.strip().lower())

    def is_verb(self, word: str) -> bool:
        return word.strip().lower() in self.verbs

    def get_all_verbs(self) -> dict:
        return dict(self.verbs)

    def count(self) -> int:
        return len(self.verbs)


# ══════════════════════════════════════════════════════════════════════
# PARTICLE DATABASE (expanded)
# ══════════════════════════════════════════════════════════════════════
class ParticleDatabase:
    """Expanded particle database."""

    BUILTIN_PARTICLES: ClassVar[dict[str, dict]] = {
        "hi": {"position": "sentence-final", "function": "declarative",
               "meaning": "marks statement"},
        "in": {"position": "post-verbal", "function": "ergative/imperative",
               "meaning": "ergative case marker or imperative"},
        "leh": {"position": "inter-clausal", "function": "conjunction",
                "meaning": "and"},
        "hang": {"position": "inter-clausal", "function": "conjunction",
                 "meaning": "but/however"},
        "ta": {"position": "post-nominal", "function": "possessive",
               "meaning": "possessive marker"},
        "pen": {"position": "post-nominal", "function": "focus",
                "meaning": "focus/emphasis"},
        "kei": {"position": "sentence-medial", "function": "jussive",
                "meaning": "let/hortative"},
        "lo": {"position": "post-verbal", "function": "negation",
               "meaning": "not/negation"},
        "si": {"position": "post-verbal", "function": "negation",
               "meaning": "not (negative)"},
        "tu": {"position": "post-verbal", "function": "negation",
               "meaning": "not (negative)"},
        "ding": {"position": "pre-verbal", "function": "future",
                 "meaning": "future tense marker"},
        "uh": {"position": "pre-verbal", "function": "perfective",
               "meaning": "perfective aspect"},
        "hiam": {"position": "sentence-final", "function": "question",
                 "meaning": "question marker (yes/no)"},
        "a": {"position": "pre-nominal", "function": "article",
              "meaning": "the/possessive"},
        "ki": {"position": "pre-verbal", "function": "reflexive",
               "meaning": "reflexive marker"},
        "sung": {"position": "post-nominal", "function": "quotative",
                 "meaning": "inside/quotative"},
        "cih": {"position": "inter-clausal", "function": "conjunction",
                "meaning": "then/and then"},
        "kua": {"position": "sentence-final", "function": "question",
                "meaning": "question marker (content)"},
        "bang": {"position": "pre-verbal", "function": "question",
                 "meaning": "what/how (question word)"},
        "thei": {"position": "pre-verbal", "function": "auxiliary",
                 "meaning": "know/understand"},
        "gal": {"position": "pre-verbal", "function": "auxiliary",
                "meaning": "can/able"},
        "mai": {"position": "sentence-final", "function": "focus",
                "meaning": "focus/emphasis"},
        "te": {"position": "post-nominal", "function": "locative",
               "meaning": "place/location"},
        "na": {"position": "post-nominal", "function": "nominalizer",
               "meaning": "nominalizer"},
        "pi": {"position": "post-nominal", "function": "plural",
               "meaning": "plural marker"},
        "hih": {"position": "sentence-medial", "function": "relative",
                "meaning": "which/that (relative clause marker)"},
        "zat": {"position": "sentence-medial", "function": "temporal",
                "meaning": "when/at the time of"},
        "kia": {"position": "pre-verbal", "function": "adversative",
                "meaning": "only/but"},
        "ang": {"position": "pre-verbal", "function": "imperative",
                "meaning": "do (imperative)"},
        "khi": {"position": "post-verbal", "function": "exclamative",
                "meaning": "exclamative particle"},
        "le": {"position": "post-nominal", "function": "locative",
               "meaning": "at/on/in"},
        "ah": {"position": "post-nominal", "function": "locative",
               "meaning": "at (locative)"},
        "ci": {"position": "pre-verbal", "function": "subordinator",
               "meaning": "that (complementizer)"},
        "than": {"position": "pre-verbal", "function": "comparative",
                 "meaning": "more than (comparative)"},
        "lah": {"position": "sentence-final", "function": "emphatic",
                "meaning": "emphatic particle"},
    }

    def __init__(self, particles_db: list[dict]):
        self.particles = dict(self.BUILTIN_PARTICLES)
        for rec in particles_db:
            p = rec.get("particle", "").strip().lower()
            if p and p not in self.particles:
                self.particles[p] = rec

    def lookup(self, word: str) -> dict | None:
        return self.particles.get(word.strip().lower())

    def is_particle(self, word: str) -> bool:
        return word.strip().lower() in self.particles

    def count(self) -> int:
        return len(self.particles)


# ══════════════════════════════════════════════════════════════════════
# VERSE ANALYZER (per-verse pipeline)
# ══════════════════════════════════════════════════════════════════════
class VerseAnalyzer:
    """Full per-verse analysis pipeline."""

    def __init__(self, glossing: GlossingEngine, phrases: PhraseExtractor,
                 morphology: MorphologyAnalyzer, grammar: GrammarMatcher,
                 clauses: ClauseAnalyzer, contrastive: ContrastiveAnalyzer,
                 verbs: VerbDatabase, particles: ParticleDatabase):
        self.glossing = glossing
        self.phrases = phrases
        self.morphology = morphology
        self.grammar = grammar
        self.clauses = clauses
        self.contrastive = contrastive
        self.verbs = verbs
        self.particles = particles

    def analyze_verse(self, verse: dict) -> dict:
        """Full analysis of a single verse with comprehensive study output."""
        ref = verse.get("ref", "")
        zo = verse.get("zo_tedim2010") or verse.get("zo_tdb77") or ""
        en = verse.get("en_kJV") or ""
        book = verse.get("book", "")
        chapter = verse.get("chapter", "")
        verse_num = verse.get("verse", "")

        if not zo:
            return {"ref": ref, "error": "no_zo_text"}

        # 1. Glossing (phrase-first, then word-by-word)
        glosses = self.glossing.gloss_verse(zo)
        dict_rate = sum(1 for g in glosses if g["source"] != "miss") / len(glosses) if glosses else 0

        # 2. Phrase extraction
        phrases_found = self.phrases.extract_all(zo)

        # 3. Morphology
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo)
        morphemes = [self.morphology.analyze(w) for w in words[:20]]

        # 4. Grammar patterns
        grammar_matches = self.grammar.match_all(zo)
        sov_check = self.grammar.match_sov(zo)

        # 5. Clause analysis
        clause_list = self.clauses.split_clauses(zo)

        # 6. Contrastive analysis
        en_words = re.findall(r"\b\w+\b", en)
        zo_words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo)
        order_analysis = self.contrastive.analyze_order(zo_words, en)
        negation_analysis = self.contrastive.analyze_negation(zo)
        question_analysis = self.contrastive.analyze_question(zo)
        tense_analysis = self.contrastive.analyze_tense(zo, en)

        # 7. Identify verbs and particles
        found_verbs = [w for w in zo_words if self.verbs.is_verb(w)]
        found_particles = [w for w in zo_words if self.particles.is_particle(w)]

        # 8. Sentence structure breakdown (Subject + Object + Verb)
        sentence_structure = self._analyze_sentence_structure(zo, glosses)

        # 9. Word combination analysis (how words combine to change meaning)
        word_combinations = self._analyze_word_combinations(glosses)

        # 10. Key vocabulary with frequency
        vocabulary = self._extract_vocabulary(glosses, words)

        # 11. Reusable sentence pattern
        sentence_pattern = self._extract_sentence_pattern(zo, en, sentence_structure)

        return {
            "ref": ref,
            "book": book,
            "chapter": chapter,
            "verse": verse_num,
            "zo": zo,
            "en": en,
            "glosses": glosses,
            "dict_rate": round(dict_rate * 100, 1),
            "phrases": phrases_found,
            "morphemes": morphemes,
            "grammar_patterns": grammar_matches,
            "sov_check": sov_check,
            "clauses": clause_list,
            "contrastive": {
                "order": order_analysis,
                "negation": negation_analysis,
                "question": question_analysis,
                "tense": tense_analysis,
            },
            "verbs_found": found_verbs,
            "particles_found": found_particles,
            "sentence_structure": sentence_structure,
            "word_combinations": word_combinations,
            "vocabulary": vocabulary,
            "sentence_pattern": sentence_pattern,
            "word_count": len(zo_words),
            "analysis_timestamp": datetime.now().isoformat(),
        }

    def _analyze_sentence_structure(self, zo: str, glosses: list[dict]) -> dict:
        """Analyze sentence structure: Subject + Object + Verb."""
        # Simple heuristic: find ergative "in" for subject, verb at end
        structure = {"subject": "", "object": "", "verb": "", "pattern": "SOV"}
        zo_words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo)

        # Find ergative marker "in" — word before it is likely subject
        for i, w in enumerate(zo_words):
            if w.lower() == "in" and i > 0:
                # Check if previous word is a noun (not a particle)
                prev = zo_words[i - 1].lower()
                if prev not in ("a", "the", "leh", "hang"):
                    structure["subject"] = " ".join(zo_words[max(0, i - 2):i + 1])
                    break

        # Find verb — usually last content word before "hi" or sentence end
        for i in range(len(zo_words) - 1, -1, -1):
            w = zo_words[i].lower()
            if w in ("hi", "hen", "ah"):
                if i > 0:
                    verb_word = zo_words[i - 1]
                    for g in glosses:
                        if g["word"].lower() == verb_word.lower():
                            if g["source"] in ("dict_zo_en", "vocab_index"):
                                structure["verb"] = verb_word
                                break
                break

        # Object = everything between subject and verb
        if structure["subject"] and structure["verb"]:
            subj_end = zo.lower().find(structure["subject"].lower().split()[0])
            verb_start = zo.lower().rfind(structure["verb"].lower())
            if subj_end >= 0 and verb_start > subj_end:
                obj_text = zo[subj_end + len(structure["subject"]):verb_start].strip()
                if obj_text:
                    structure["object"] = obj_text

        return structure

    def _analyze_word_combinations(self, glosses: list[dict]) -> list[dict]:
        """Analyze how word combinations change meaning."""
        combinations = []
        for i in range(len(glosses) - 1):
            g1 = glosses[i]
            g2 = glosses[i + 1]
            # Skip if either is a miss
            if g1["source"] == "miss" or g2["source"] == "miss":
                continue
            # Check if this is a meaningful combination
            w1 = g1["word"].lower()
            w2 = g2["word"].lower()
            combo = f"{w1} {w2}"
            # Known meaningful combinations
            known_combos = {
                "a hi": "is/am/are (copula)",
                "ci hi": "said (quotative + declarative)",
                "leh leh": "and (coordination)",
                "in a": "ergative + 3rd person",
                "a in": "3rd person + ergative",
                "in in": "ergative + ergative (emphasis)",
                "lo hi": "not (negation + declarative)",
                "hen hi": "let it be (hortative + declarative)",
            }
            for pattern, meaning in known_combos.items():
                if w1 in pattern and w2 in pattern:
                    combinations.append({
                        "words": combo,
                        "meaning": meaning,
                        "type": "grammatical",
                    })
                    break
        return combinations

    def _extract_vocabulary(self, glosses: list[dict], words: list[str]) -> list[dict]:
        """Extract key vocabulary with frequency info."""
        vocab = []
        seen = set()
        for g in glosses:
            w = g["word"].lower()
            if w in seen or g["source"] == "miss":
                continue
            seen.add(w)
            vocab.append({
                "word": g["word"],
                "meaning": g["gloss"],
                "source": g["source"],
                "confidence": g.get("confidence", "low"),
            })
        return vocab[:20]  # Limit to 20 words

    def _extract_sentence_pattern(self, zo: str, en: str, structure: dict) -> dict:
        """Extract reusable sentence pattern."""
        pattern = {
            "zo_pattern": "",
            "en_pattern": "",
            "template": "",
            "substitutions": [],
        }
        if structure["subject"] and structure["verb"]:
            pattern["template"] = f"Subject + [Object] + {structure['verb']}"
            pattern["zo_pattern"] = f"[Subject] + [Object] + {structure['verb']}"
            pattern["en_pattern"] = "[Subject] + [Object] + [verb]"
        return pattern


# ══════════════════════════════════════════════════════════════════════
# PATTERN MATCHER
# ══════════════════════════════════════════════════════════════════════
class PatternMatcher:
    """English→Zo closest Bible pattern lookup."""

    def __init__(self, grammar_patterns: list[dict], phrases_db: list[dict]):
        self.grammar_patterns = grammar_patterns
        self.phrases_db = phrases_db
        self.en_to_zo_patterns: dict[str, list[dict]] = defaultdict(list)
        for rec in grammar_patterns:
            for ex in rec.get("examples", []):
                self.en_to_zo_patterns[rec.get("pattern", "")].append(rec)

    def find_closest(self, english_text: str) -> list[dict]:
        """Find closest Zo pattern to an English sentence."""
        en_lower = english_text.lower()
        matches = []

        # Check question patterns
        if "?" in english_text or any(w in en_lower for w in ["what", "where", "when", "why", "how"]):
            matches.append({
                "pattern": "question_hiam",
                "zo_pattern": "... hiam",
                "description": "Add 'hiam' for yes/no questions",
                "confidence": HIGH,
            })

        # Check negation
        if any(w in en_lower for w in ["not", "no", "never", "don't", "won't"]):
            matches.append({
                "pattern": "negation_lo",
                "zo_pattern": "... V + lo",
                "description": "Add 'lo' after verb for negation",
                "confidence": HIGH,
            })

        # Check future
        if any(w in en_lower for w in ["will", "shall", "going to"]):
            matches.append({
                "pattern": "future_ding",
                "zo_pattern": "... ding + V",
                "description": "Add 'ding' before verb for future",
                "confidence": HIGH,
            })

        # Check imperative
        if english_text.rstrip().endswith("!") or en_lower.startswith(("go ", "come ", "take ", "give ")):
            matches.append({
                "pattern": "imperative_in",
                "zo_pattern": "... V + in",
                "description": "Add 'in' after verb for imperative",
                "confidence": MEDIUM,
            })

        # Default: SOV structure
        if not matches:
            matches.append({
                "pattern": "SOV_default",
                "zo_pattern": "S + O + V",
                "description": "Zolai uses SOV word order",
                "confidence": MEDIUM,
            })

        return matches


# ══════════════════════════════════════════════════════════════════════
# LEARNING MANAGER
# ══════════════════════════════════════════════════════════════════════
class LearningManager:
    """8 progressive levels, exercise generation, spaced review."""

    REVIEW_FILE = KB_DIR / "review" / "spaced_review.jsonl"
    PROGRESS_FILE = KB_DIR / "review" / "progress.json"

    def __init__(self, vocab: dict[str, dict], zo_en: dict[str, list[str]]):
        self.vocab = vocab
        self.zo_en = zo_en
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)

    def get_level_words(self, level: int, book: str = "") -> list[dict]:
        """Get words for a specific learning level."""
        threshold = LEVEL_THRESHOLDS.get(level, 999999)
        prev_threshold = LEVEL_THRESHOLDS.get(level - 1, 0)

        # Sort vocab by frequency
        sorted_words = sorted(
            self.vocab.items(),
            key=lambda x: x[1].get("frequency", 0),
            reverse=True,
        )

        result = []
        for word, info in sorted_words:
            freq = info.get("frequency", 0)
            if freq <= prev_threshold:
                continue
            if freq > threshold:
                continue
            # Get translation from dictionary
            trans = self.zo_en.get(word, info.get("translations", []))
            result.append({
                "word": word,
                "frequency": freq,
                "translation": trans[0] if trans else "?",
                "alternatives": trans[1:3] if trans else [],
                "level": level,
                "examples": info.get("examples", [])[:3],
            })
            if len(result) >= threshold - prev_threshold:
                break

        return result

    def generate_exercise(self, level: int, exercise_type: str = "translate") -> dict:
        """Generate a learning exercise."""
        words = self.get_level_words(level)
        if not words:
            return {"error": "no_words_for_level"}

        word = random.choice(words)
        correct = word["translation"]
        wrong_options = []

        # Generate wrong options from same level
        other_words = [w for w in words if w["word"] != word["word"]]
        if len(other_words) >= 3:
            wrong_options = [w["translation"] for w in random.sample(other_words, 3)]

        options = [correct] + wrong_options
        random.shuffle(options)

        if exercise_type == "translate":
            return {
                "type": "translate_zo_to_en",
                "prompt": f"Translate: {word['word']}",
                "options": options,
                "correct": correct,
                "word": word["word"],
                "level": level,
            }
        elif exercise_type == "reverse":
            return {
                "type": "translate_en_to_zo",
                "prompt": f"Translate to Zolai: {correct}",
                "options": [w["word"] for w in random.sample(words, min(4, len(words)))],
                "correct": word["word"],
                "level": level,
            }
        return {"error": "unknown_exercise_type"}

    def record_review(self, word: str, correct: bool, level: int):
        """Record a spaced repetition review."""
        entry = {
            "word": word,
            "correct": correct,
            "level": level,
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.REVIEW_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_due_items(self) -> list[dict]:
        """Get items due for review (spaced repetition)."""
        if not self.REVIEW_FILE.exists():
            return []

        # Load review history
        history: dict[str, list[dict]] = defaultdict(list)
        with open(self.REVIEW_FILE) as f:
            for line in f:
                rec = json.loads(line)
                history[rec["word"]].append(rec)

        due = []
        now = datetime.now()
        for word, reviews in history.items():
            if not reviews:
                continue
            last = reviews[-1]
            last_time = datetime.fromisoformat(last["timestamp"])
            # Simple spaced repetition: 1d, 3d, 7d, 14d, 30d
            streak = sum(1 for r in reversed(reviews) if r["correct"])
            intervals = [1, 3, 7, 14, 30]
            interval_days = intervals[min(streak, len(intervals) - 1)]
            if now - last_time > timedelta(days=interval_days):
                due.append({
                    "word": word,
                    "last_review": last["timestamp"],
                    "streak": streak,
                    "interval_days": interval_days,
                })

        return sorted(due, key=lambda x: x["streak"])


# ══════════════════════════════════════════════════════════════════════
# DATASET EXPORTER
# ══════════════════════════════════════════════════════════════════════
class DatasetExporter:
    """Training data export (translation, grammar, vocab, QA)."""

    EXPORT_DIR = KB_DIR / "exports"

    def __init__(self, corpus_by_book_fn, glossing: GlossingEngine,
                 grammar_matcher: GrammarMatcher):
        self.corpus_by_book = corpus_by_book_fn
        self.glossing = glossing
        self.grammar = grammar_matcher
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    def export_translation(self, book: str = "", limit: int = 0) -> str:
        """Export translation pairs (ZO→EN)."""
        verses = self.corpus_by_book(book) if book else self._load_all()
        pairs = []
        for v in verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            if zo and en:
                pairs.append({
                    "zo": zo,
                    "en": en,
                    "ref": v.get("ref", ""),
                    "book": v.get("book", ""),
                })
                if limit and len(pairs) >= limit:
                    break

        out_path = self.EXPORT_DIR / f"translation_pairs_{book or 'all'}.jsonl"
        with open(out_path, "w") as f:
            f.writelines(
                json.dumps(p, ensure_ascii=False) + "\n" for p in pairs
            )
        return str(out_path)

    def export_grammar(self, book: str = "", limit: int = 0) -> str:
        """Export grammar exercises."""
        verses = self.corpus_by_book(book) if book else self._load_all()
        exercises = []
        for v in verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            if not zo:
                continue
            patterns = self.grammar.match_all(zo)
            for p in patterns:
                exercises.append({
                    "verse_ref": v.get("ref", ""),
                    "pattern": p["pattern"],
                    "description": p["description"],
                    "zo_example": zo,
                    "en_example": v.get("en_kJV", ""),
                    "confidence": p["confidence"],
                })
                if limit and len(exercises) >= limit:
                    break
            if limit and len(exercises) >= limit:
                break

        out_path = self.EXPORT_DIR / f"grammar_exercises_{book or 'all'}.jsonl"
        with open(out_path, "w") as f:
            f.writelines(
                json.dumps(e, ensure_ascii=False) + "\n" for e in exercises
            )
        return str(out_path)

    def export_vocab(self, book: str = "", limit: int = 0) -> str:
        """Export vocabulary with translations."""
        verses = self.corpus_by_book(book) if book else self._load_all()
        word_freq: Counter = Counter()
        for v in verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo)
            for w in words:
                word_freq[w.lower()] += 1

        vocab_list = []
        for word, freq in word_freq.most_common(limit or 999999):
            glosses = self.glossing.gloss_word(word)
            vocab_list.append({
                "word": word,
                "frequency": freq,
                "gloss": glosses.get("gloss", "?"),
                "alternatives": glosses.get("alternatives", []),
                "source": glosses.get("source", "miss"),
            })

        out_path = self.EXPORT_DIR / f"vocab_{book or 'all'}.jsonl"
        with open(out_path, "w") as f:
            for v in vocab_list:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
        return str(out_path)

    def export_qa(self, book: str = "", limit: int = 0) -> str:
        """Export QA pairs (question about verse + answer)."""
        verses = self.corpus_by_book(book) if book else self._load_all()
        qa_pairs = []
        for v in verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en = v.get("en_kJV") or ""
            ref = v.get("ref", "")
            if not zo or not en:
                continue

            # Generate simple QA
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo)
            if len(words) >= 3:
                # Question: translate this verse
                qa_pairs.append({
                    "question": f"What does {ref} say in English?",
                    "context_zo": zo,
                    "answer": en,
                    "ref": ref,
                    "type": "translation",
                })
                # Question: translate English to Zolai
                qa_pairs.append({
                    "question": f"Translate to Zolai: {en[:100]}",
                    "answer": zo,
                    "ref": ref,
                    "type": "reverse_translation",
                })
            if limit and len(qa_pairs) >= limit:
                break

        out_path = self.EXPORT_DIR / f"qa_pairs_{book or 'all'}.jsonl"
        with open(out_path, "w") as f:
            f.writelines(
                json.dumps(qa, ensure_ascii=False) + "\n" for qa in qa_pairs
            )
        return str(out_path)

    def _load_all(self) -> list[dict]:
        verses = []
        if CORPUS.exists():
            with open(CORPUS) as f:
                for line in f:
                    verses.append(json.loads(line))
        return verses


# ══════════════════════════════════════════════════════════════════════
# CORPUS SEARCHER
# ══════════════════════════════════════════════════════════════════════
class CorpusSearcher:
    """Find similar patterns across 31K verses."""

    def __init__(self):
        self.corpus_loaded = False
        self.verses: list[dict] = []

    def _ensure_loaded(self):
        if not self.corpus_loaded:
            if CORPUS.exists():
                with open(CORPUS) as f:
                    self.verses = [json.loads(line) for line in f]
            self.corpus_loaded = True

    def search_text(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across all verses."""
        self._ensure_loaded()
        query_lower = query.lower()
        results = []
        for v in self.verses:
            zo = (v.get("zo_tedim2010") or v.get("zo_tdb77") or "").lower()
            en = (v.get("en_kJV") or "").lower()
            if query_lower in zo or query_lower in en:
                results.append({
                    "ref": v.get("ref", ""),
                    "zo": v.get("zo_tedim2010") or v.get("zo_tdb77") or "",
                    "en": v.get("en_kJV", ""),
                    "book": v.get("book", ""),
                    "match_in": "zo" if query_lower in zo else "en",
                })
                if len(results) >= limit:
                    break
        return results

    def search_pattern(self, pattern_name: str, limit: int = 20) -> list[dict]:
        """Search for verses containing a specific grammar pattern."""
        self._ensure_loaded()
        pattern_map = {
            "SOV": r"\b\w+\s+\w+\s+[a-zA-Z']+\b",
            "negation": r"\b\w+\s+(?:lo|si|tu)\b",
            "question_hiam": r"\bhiam\b",
            "conjunction_leh": r"\bleh\b",
            "ergative_in": r"\b\w+\s+in\s+\w+\b",
            "possessive_ta": r"[\u0027\u2019]\s*ta\b",
            "declarative_hi": r"\bhi\b",
        }
        regex = pattern_map.get(pattern_name, pattern_name)
        results = []
        for v in self.verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            if re.search(regex, zo, re.IGNORECASE):
                results.append({
                    "ref": v.get("ref", ""),
                    "zo": zo,
                    "en": v.get("en_kJV", ""),
                    "book": v.get("book", ""),
                })
                if len(results) >= limit:
                    break
        return results

    def search_word(self, word: str, limit: int = 20) -> list[dict]:
        """Search for verses containing a specific word."""
        return self.search_text(word, limit)

    def count_pattern(self, pattern_name: str) -> int:
        """Count occurrences of a pattern."""
        self._ensure_loaded()
        pattern_map = {
            "SOV": r"\b\w+\s+\w+\s+[a-zA-Z']+\b",
            "negation_lo": r"\blo\b",
            "question_hiam": r"\bhiam\b",
            "conjunction_leh": r"\bleh\b",
            "ergative_in": r"\bin\b",
            "declarative_hi": r"\bhi\b",
            "future_ding": r"\bding\b",
        }
        regex = pattern_map.get(pattern_name, pattern_name)
        count = 0
        for v in self.verses:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            if re.search(regex, zo, re.IGNORECASE):
                count += 1
        return count


# ══════════════════════════════════════════════════════════════════════
# BIBLE ENGINE (main orchestrator)
# ══════════════════════════════════════════════════════════════════════
class BibleEngine:
    """Main orchestrator — ties all modules together."""

    def __init__(self):
        print(f"{G}Loading Bible Engine...{NC}")
        # Load all data
        self.zo_en = load_zo_en_dict()
        self.vocab = load_vocab_index()
        self.grammar_patterns = load_grammar_patterns()
        self.verbs_raw = load_jsonl(VERB_DB)
        self.particles_raw = load_jsonl(PARTICLE_DB)
        self.phrases_db = load_phrase_database()
        self.collocations = load_collocations()

        self.phrase_dict = load_phrase_dict()

        print(f"  {len(self.zo_en)} ZO→EN entries")
        print(f"  {len(self.vocab)} vocab entries")
        print(f"  {len(self.grammar_patterns)} grammar patterns")
        print(f"  {len(self.collocations)} collocations")
        print(f"  {len(self.phrase_dict)} phrase entries")

        # Initialize all modules
        self.glossing = GlossingEngine(
            self.zo_en, self.vocab, self.phrases_db, self.collocations,
            self.phrase_dict,
        )
        self.phrases = PhraseExtractor(self.phrases_db, self.collocations, self.zo_en)
        self.morphology = MorphologyAnalyzer()
        self.grammar = GrammarMatcher(self.grammar_patterns)
        self.clauses = ClauseAnalyzer()
        self.contrastive = ContrastiveAnalyzer()
        self.verb_db = VerbDatabase(self.verbs_raw)
        self.particle_db = ParticleDatabase(self.particles_raw)
        self.pattern_matcher = PatternMatcher(self.grammar_patterns, self.phrases_db)
        self.learning = LearningManager(self.vocab, self.zo_en)
        self.searcher = CorpusSearcher()
        self.exporter = DatasetExporter(load_corpus_by_book, self.glossing, self.grammar)
        self.evidence = EvidenceScorer()

        self.analyzer = VerseAnalyzer(
            self.glossing, self.phrases, self.morphology, self.grammar,
            self.clauses, self.contrastive, self.verb_db, self.particle_db,
        )

        print(f"  {self.verb_db.count()} verbs loaded")
        print(f"  {self.particle_db.count()} particles loaded")
        print(f"{G}Engine ready.{NC}\n")

    def study_book(self, book: str) -> dict:
        """Full verse analysis for a book."""
        verses = load_corpus_by_book(book)
        if not verses:
            return {"book": book, "verses": 0, "error": "no_verses_found"}

        output_dir = KB_DIR / "verses"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{book.lower()}_analysis.jsonl"

        results = []
        for v in verses:
            analysis = self.analyzer.analyze_verse(v)
            results.append(analysis)

        with open(output_file, "w") as f:
            f.writelines(
                json.dumps(r, ensure_ascii=False) + "\n" for r in results
            )

        # Calculate stats
        total_words = sum(r.get("word_count", 0) for r in results)
        dict_hits = self.glossing.stats["dict_hit"]
        vocab_hits = self.glossing.stats["vocab_hit"]
        misses = self.glossing.stats["miss"]

        return {
            "book": book,
            "verses": len(results),
            "total_words": total_words,
            "dict_rate": round(dict_hits / max(total_words, 1) * 100, 1),
            "vocab_rate": round(vocab_hits / max(total_words, 1) * 100, 1),
            "miss_rate": round(misses / max(total_words, 1) * 100, 1),
            "output": str(output_file),
        }

    def study_all(self) -> dict:
        """Study all 66 books."""
        corpus = load_jsonl(CORPUS)
        books = sorted({v.get("book", "") for v in corpus if v.get("book")})
        results = []
        for i, book in enumerate(books, 1):
            print(f"  [{i}/{len(books)}] Analyzing {book}...")
            r = self.study_book(book)
            results.append(r)
        return {"books": len(books), "results": results}

    def show_stats(self):
        """Show comprehensive statistics."""
        print(f"\n{Y}═══ Bible Engine Statistics ═══{NC}\n")

        # Corpus stats
        corpus = load_jsonl(CORPUS)
        books = {v.get("book", "") for v in corpus if v.get("book")}
        print(f"  Corpus: {len(corpus)} verses across {len(books)} books")

        # Dictionary stats
        print(f"  ZO→EN dictionary: {len(self.zo_en)} entries")
        print(f"  Vocabulary index: {len(self.vocab)} words")
        print(f"  Grammar patterns: {len(self.grammar_patterns)} patterns")
        print(f"  Collocations: {len(self.collocations)} pairs")

        # Database stats
        print(f"\n  {Y}Databases:{NC}")
        print(f"    Verbs: {self.verb_db.count()} (file: {len(self.verbs_raw)}, built-in: {len(VerbDatabase.BUILTIN_VERBS)})")
        print(f"    Particles: {self.particle_db.count()} (file: {len(self.particles_raw)}, built-in: {len(ParticleDatabase.BUILTIN_PARTICLES)})")
        print(f"    Phrases: {len(self.phrases_db)} entries")

        # Analysis outputs
        analysis_dir = KB_DIR / "verses"
        if analysis_dir.exists():
            files = list(analysis_dir.glob("*.jsonl"))
            print(f"\n  {Y}Analysis Outputs:{NC}")
            print(f"    Verse analyses: {len(files)} books")

        # Review stats
        review_file = KB_DIR / "review" / "spaced_review.jsonl"
        if review_file.exists():
            with open(review_file) as f:
                review_count = sum(1 for _ in f)
            print(f"    Reviews completed: {review_count}")

        # Export stats
        export_dir = KB_DIR / "exports"
        if export_dir.exists():
            export_files = list(export_dir.glob("*.jsonl"))
            print(f"    Exported datasets: {len(export_files)}")

        # Evidence scoring example
        print(f"\n  {Y}Evidence Levels:{NC}")
        print("    HIGH: freq > 1000 or pattern > 500 (5+ examples)")
        print("    MEDIUM: freq > 100 or pattern > 100 (3+ examples)")
        print("    LOW: freq > 10 or pattern > 10")
        print("    UNCERTAIN: minimal evidence")

        print()

    def get_status(self) -> dict:
        """Get engine status for menu."""
        corpus = load_jsonl(CORPUS)
        books = {v.get("book", "") for v in corpus if v.get("book")}
        analysis_dir = KB_DIR / "verses"
        analyzed = 0
        if analysis_dir.exists():
            analyzed = len(list(analysis_dir.glob("*.jsonl")))
        return {
            "verses": len(corpus),
            "books": len(books),
            "analyzed_books": analyzed,
            "dict_entries": len(self.zo_en),
            "vocab_entries": len(self.vocab),
        }


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Zolai Bible Engine — Language Learning & Grammar Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Study mode:
  python bible_engine.py --study --book GEN
  python bible_engine.py --study --all

Learning mode:
  python bible_engine.py --learn --level 3 --book GEN

Review mode:
  python bible_engine.py --review --due
  python bible_engine.py --review --word bawl

Export mode:
  python bible_engine.py --export --type translation --book GEN

Search mode:
  python bible_engine.py --search "Pasian"
  python bible_engine.py --search-pattern "SOV"

Stats:
  python bible_engine.py --stats
""",
    )

    # Study mode
    parser.add_argument("--study", action="store_true", help="Full verse analysis (study mode)")
    parser.add_argument("--all", action="store_true", help="Process all books")
    parser.add_argument("--book", type=str, help="Book code(s) comma-separated")

    # Learning mode
    parser.add_argument("--learn", action="store_true", help="Progressive learning mode")
    parser.add_argument("--level", type=int, default=1, choices=range(1, 9),
                        help="Learning level (1-8)")
    parser.add_argument("--exercise", type=str, default="translate",
                        choices=["translate", "reverse"],
                        help="Exercise type")

    # Review mode
    parser.add_argument("--review", action="store_true", help="Spaced repetition review")
    parser.add_argument("--due", action="store_true", help="Show due items")
    parser.add_argument("--word", type=str, help="Review a specific word")

    # Export mode
    parser.add_argument("--export", action="store_true", help="Export training datasets")
    parser.add_argument("--type", type=str, default="translation",
                        choices=["translation", "grammar", "vocab", "qa"],
                        help="Export type")

    # Search mode
    parser.add_argument("--search", type=str, help="Full-text search")
    parser.add_argument("--search-pattern", type=str, help="Pattern search (SOV, negation, etc.)")
    parser.add_argument("--limit", type=int, default=20, help="Search result limit")

    # Stats
    parser.add_argument("--stats", action="store_true", help="Show statistics")

    args = parser.parse_args()

    # Build engine
    engine = BibleEngine()

    if args.stats:
        engine.show_stats()
        return

    if args.study:
        if args.all:
            result = engine.study_all()
            print(f"\n{G}═══ Study Complete ═══{NC}")
            print(f"  Books analyzed: {result['books']}")
        elif args.book:
            books = [b.strip().upper() for b in args.book.split(",")]
            for book in books:
                result = engine.study_book(book)
                print(f"\n{G}═══ {book} Complete ═══{NC}")
                print(f"  Verses: {result['verses']}")
                print(f"  Dict rate: {result.get('dict_rate', 0)}%")
                print(f"  Output: {result.get('output', '')}")
        else:
            parser.error("--study requires --book or --all")
        return

    if args.learn:
        words = engine.learning.get_level_words(args.level)
        print(f"\n{Y}═══ Level {args.level}: {LEVEL_NAMES[args.level]} ═══{NC}")
        print(f"  Words in level: {len(words)}")
        exercise = engine.learning.generate_exercise(args.level, args.exercise)
        if "error" not in exercise:
            print(f"\n  {C}Exercise:{NC}")
            print(f"    {exercise['prompt']}")
            for i, opt in enumerate(exercise.get("options", []), 1):
                marker = "→" if opt == exercise.get("correct") else " "
                print(f"    {i}) {marker} {opt}")
            print(f"    Correct: {exercise.get('correct')}")
        return

    if args.review:
        if args.due:
            due = engine.learning.get_due_items()
            print(f"\n{Y}═══ Due for Review ═══{NC}")
            if not due:
                print(f"  {G}No items due for review!{NC}")
            else:
                for item in due[:20]:
                    print(f"  {item['word']:15s} streak={item['streak']} "
                          f"interval={item['interval_days']}d")
        elif args.word:
            print(f"\n{Y}═══ Review: {args.word} ═══{NC}")
            glosses = engine.glossing.gloss_word(args.word)
            print(f"  Translation: {glosses.get('gloss', '?')}")
            print(f"  Source: {glosses.get('source', '?')}")
            engine.learning.record_review(args.word, True, 1)
            print(f"  {G}Review recorded!{NC}")
        else:
            parser.error("--review requires --due or --word")
        return

    if args.export:
        book = args.book or ""
        if args.type == "translation":
            path = engine.exporter.export_translation(book)
        elif args.type == "grammar":
            path = engine.exporter.export_grammar(book)
        elif args.type == "vocab":
            path = engine.exporter.export_vocab(book)
        elif args.type == "qa":
            path = engine.exporter.export_qa(book)
        else:
            path = ""
        print(f"\n{G}═══ Export Complete ═══{NC}")
        print(f"  Type: {args.type}")
        print(f"  Output: {path}")
        return

    if args.search:
        results = engine.searcher.search_text(args.search, args.limit)
        print(f"\n{Y}═══ Search: '{args.search}' ═══{NC}")
        print(f"  Results: {len(results)}")
        for r in results[:10]:
            print(f"\n  {B}{r['ref']}{NC}")
            print(f"    ZO: {r['zo'][:100]}...")
            print(f"    EN: {r['en'][:100]}...")
        return

    if args.search_pattern:
        results = engine.searcher.search_pattern(args.search_pattern, args.limit)
        count = engine.searcher.count_pattern(args.search_pattern)
        print(f"\n{Y}═══ Pattern: {args.search_pattern} ═══{NC}")
        print(f"  Total occurrences: {count}")
        print(f"  Showing: {min(len(results), args.limit)}")
        for r in results[:10]:
            print(f"\n  {B}{r['ref']}{NC}")
            print(f"    ZO: {r['zo'][:100]}...")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
