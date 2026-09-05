#!/usr/bin/env python3
"""
ZOLAI PARAGRAPH ENGINE — Paragraph Analysis, Style Learning & Paraphrase
Single-script engine for Zolai paragraph analysis, style profiling,
paraphrase generation, and knowledge extraction.

Reuses patterns from bible_engine.py:
- EvidenceScorer, GlossingEngine, MorphologyAnalyzer, VerbDatabase, ParticleDatabase
- JSONL I/O, data loading, color constants
"""

import json
import re
import hashlib
import argparse
import random
from collections import Counter, defaultdict
from datetime import datetime
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
KB_DIR = DATA / "bible" / "knowledge_base"

# Paragraph engine specific paths
PARA_DIR = DATA / "bible" / "paragraph_engine"
ANALYSES_DIR = PARA_DIR / "analyses"
KNOWLEDGE_DIR = PARA_DIR / "knowledge"
INDEXES_DIR = PARA_DIR / "indexes"

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
# PERMISSION STATUS
# ══════════════════════════════════════════════════════════════════════
PRIVATE = "PRIVATE"
SHARED = "SHARED"
PUBLIC = "PUBLIC"
TRAINING_ELIGIBLE = "TRAINING_ELIGIBLE"
EVALUATION_ONLY = "EVALUATION_ONLY"

# ══════════════════════════════════════════════════════════════════════
# STYLE PROFILES
# ══════════════════════════════════════════════════════════════════════
STYLE_PROFILES: ClassVar[dict[str, dict]] = {
    "ZO-STYLE-BIBLE": {
        "name": "Zolai Bible Style",
        "description": "Traditional biblical Zolai style with religious markers",
        "formality": 0.9,
        "complexity": 0.7,
        "emotionality": 0.6,
        "narrative_density": 0.8,
        "religious_markers": 0.9,
        "connectors_per_sentence": 1.2,
        "avg_sentence_length": 18,
        "vocab_rarity": 0.6,
    },
    "FORMAL": {
        "name": "Formal",
        "description": "Formal, structured writing",
        "formality": 0.95,
        "complexity": 0.8,
        "emotionality": 0.3,
        "narrative_density": 0.5,
        "religious_markers": 0.1,
        "connectors_per_sentence": 1.5,
        "avg_sentence_length": 22,
        "vocab_rarity": 0.7,
    },
    "INFORMAL": {
        "name": "Informal",
        "description": "Casual, everyday conversation",
        "formality": 0.3,
        "complexity": 0.4,
        "emotionality": 0.5,
        "narrative_density": 0.6,
        "religious_markers": 0.05,
        "connectors_per_sentence": 0.8,
        "avg_sentence_length": 12,
        "vocab_rarity": 0.3,
    },
    "CONVERSATIONAL": {
        "name": "Conversational",
        "description": "Dialogue-style, interactive",
        "formality": 0.25,
        "complexity": 0.35,
        "emotionality": 0.6,
        "narrative_density": 0.4,
        "religious_markers": 0.1,
        "connectors_per_sentence": 0.6,
        "avg_sentence_length": 10,
        "vocab_rarity": 0.25,
    },
    "EDUCATIONAL": {
        "name": "Educational",
        "description": "Teaching/explanatory style",
        "formality": 0.7,
        "complexity": 0.6,
        "emotionality": 0.2,
        "narrative_density": 0.3,
        "religious_markers": 0.15,
        "connectors_per_sentence": 1.3,
        "avg_sentence_length": 16,
        "vocab_rarity": 0.5,
    },
    "NEWS": {
        "name": "News/Journalistic",
        "description": "Factual reporting style",
        "formality": 0.85,
        "complexity": 0.6,
        "emotionality": 0.2,
        "narrative_density": 0.4,
        "religious_markers": 0.05,
        "connectors_per_sentence": 1.1,
        "avg_sentence_length": 20,
        "vocab_rarity": 0.55,
    },
    "LITERARY": {
        "name": "Literary",
        "description": "Creative, artistic prose",
        "formality": 0.75,
        "complexity": 0.85,
        "emotionality": 0.7,
        "narrative_density": 0.9,
        "religious_markers": 0.2,
        "connectors_per_sentence": 1.0,
        "avg_sentence_length": 15,
        "vocab_rarity": 0.75,
    },
    "STORYTELLING": {
        "name": "Storytelling",
        "description": "Narrative, plot-driven",
        "formality": 0.5,
        "complexity": 0.6,
        "emotionality": 0.65,
        "narrative_density": 0.95,
        "religious_markers": 0.3,
        "connectors_per_sentence": 0.9,
        "avg_sentence_length": 14,
        "vocab_rarity": 0.45,
    },
    "PERSUASIVE": {
        "name": "Persuasive",
        "description": "Argumentative, convincing",
        "formality": 0.7,
        "complexity": 0.7,
        "emotionality": 0.6,
        "narrative_density": 0.3,
        "religious_markers": 0.25,
        "connectors_per_sentence": 1.4,
        "avg_sentence_length": 18,
        "vocab_rarity": 0.6,
    },
    "INSPIRATIONAL": {
        "name": "Inspirational",
        "description": "Motivational, uplifting",
        "formality": 0.6,
        "complexity": 0.5,
        "emotionality": 0.8,
        "narrative_density": 0.5,
        "religious_markers": 0.7,
        "connectors_per_sentence": 1.0,
        "avg_sentence_length": 13,
        "vocab_rarity": 0.4,
    },
    "SOCIAL": {
        "name": "Social Media",
        "description": "Short, punchy, casual",
        "formality": 0.15,
        "complexity": 0.25,
        "emotionality": 0.5,
        "narrative_density": 0.3,
        "religious_markers": 0.05,
        "connectors_per_sentence": 0.5,
        "avg_sentence_length": 8,
        "vocab_rarity": 0.2,
    },
    "ACADEMIC": {
        "name": "Academic",
        "description": "Scholarly, research-oriented",
        "formality": 0.95,
        "complexity": 0.9,
        "emotionality": 0.1,
        "narrative_density": 0.2,
        "religious_markers": 0.05,
        "connectors_per_sentence": 1.6,
        "avg_sentence_length": 25,
        "vocab_rarity": 0.8,
    },
    "RELIGIOUS": {
        "name": "Religious",
        "description": "Devotional, worship-oriented",
        "formality": 0.8,
        "complexity": 0.5,
        "emotionality": 0.7,
        "narrative_density": 0.4,
        "religious_markers": 0.95,
        "connectors_per_sentence": 1.1,
        "avg_sentence_length": 14,
        "vocab_rarity": 0.5,
    },
    "SIMPLE": {
        "name": "Simple",
        "description": "Basic, easy to understand",
        "formality": 0.4,
        "complexity": 0.2,
        "emotionality": 0.3,
        "narrative_density": 0.4,
        "religious_markers": 0.1,
        "connectors_per_sentence": 0.7,
        "avg_sentence_length": 8,
        "vocab_rarity": 0.2,
    },
    "PROFESSIONAL": {
        "name": "Professional",
        "description": "Business, workplace",
        "formality": 0.85,
        "complexity": 0.65,
        "emotionality": 0.25,
        "narrative_density": 0.35,
        "religious_markers": 0.05,
        "connectors_per_sentence": 1.3,
        "avg_sentence_length": 18,
        "vocab_rarity": 0.55,
    },
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
    """Build phrase dictionary from supplement dict (multi-word headwords)."""
    phrase_dict: dict[str, str] = {}
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
        self.phrase_dict: dict[str, str] = phrase_dict or {}
        self.stats = {"dict_hit": 0, "vocab_hit": 0, "phrase_hit": 0, "miss": 0}

    def gloss_word(self, word: str) -> dict:
        """Gloss a single Zolai word."""
        w = word.strip().lower()
        if w in self.zo_en:
            self.stats["dict_hit"] += 1
            return {
                "word": word,
                "gloss": self.zo_en[w][0] if self.zo_en[w] else "?",
                "alternatives": self.zo_en[w][1:3],
                "source": "dict_zo_en",
                "confidence": HIGH,
            }
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
        self.stats["miss"] += 1
        return {
            "word": word,
            "gloss": "?",
            "alternatives": [],
            "source": "miss",
            "confidence": UNCERTAIN,
        }

    def gloss_text(self, zo_text: str) -> list[dict]:
        """Gloss text with phrase-first, then word-by-word fallback."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        if not words:
            return []
        result: list[dict] = []
        i = 0
        while i < len(words):
            matched = False
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
# MORPHOLOGY ANALYZER
# ══════════════════════════════════════════════════════════════════════
class MorphologyAnalyzer:
    """Root + prefix (ka-/na-/a-/uh-) + suffix (-hi/-leh/-te/-in) decomposition."""

    PREFIXES: ClassVar[list[str]] = ["ka", "na", "uh", "a", "ki", "si", "tu"]
    SUFFIXES: ClassVar[list[str]] = ["hi", "leh", "te", "in", "in", "na", "pi", "te"]
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
        for pfx in sorted(self.PREFIXES, key=len, reverse=True):
            if w.startswith(pfx) and len(w) > len(pfx) + 1:
                root_candidate = w[len(pfx):]
                result["prefix"] = pfx
                result["root"] = root_candidate
                result["morphemes"] = [pfx, root_candidate]
                break
        root = result["root"]
        for sfx in sorted(self.SUFFIXES, key=len, reverse=True):
            if root.endswith(sfx) and len(root) > len(sfx) + 1:
                root_stem = root[:-len(sfx)]
                result["suffix"] = sfx
                result["root"] = root_stem
                result["morphemes"] = result["morphemes"][:1] + [root_stem, sfx]
                break
        for ending, tag in self.INFLECTIONS.items():
            if w.endswith(ending):
                result["inflection"] = tag
                break
        if len(result["morphemes"]) > 1:
            result["confidence"] = LOW
        else:
            result["confidence"] = UNCERTAIN
        return result


# ══════════════════════════════════════════════════════════════════════
# GRAMMAR MATCHER
# ══════════════════════════════════════════════════════════════════════
class GrammarMatcher:
    """Pattern matching from grammar_patterns_text.jsonl."""

    PATTERNS: ClassVar[dict[str, dict]] = {
        "SOV": {
            "pattern": r"\b(\w+)\s+(?:(?:ki|si|tu|a|in)\s+)?(\w+)\s+([a-zA-Z']+)\b",
            "description": "Subject + Object + Verb (SOV order)",
            "confidence": HIGH,
        },
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
        """Match all known patterns in text."""
        matches = []
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

    def match_sov(self, zo_text: str) -> dict:
        """Check for SOV word order in a sentence."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", zo_text)
        if len(words) < 3:
            return {"sov": False, "confidence": UNCERTAIN, "reason": "too_short"}
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
# VERB DATABASE
# ══════════════════════════════════════════════════════════════════════
class VerbDatabase:
    """Expanded verb database with argument structure."""

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

    def count(self) -> int:
        return len(self.verbs)


# ══════════════════════════════════════════════════════════════════════
# PARTICLE DATABASE
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
# CLASS 1: PROVENANCE MANAGER
# ══════════════════════════════════════════════════════════════════════
class ProvenanceManager:
    """Tracks source_type, source_id, date_added, permission_status."""

    def __init__(self):
        self.records: list[dict] = []

    def create_envelope(self, source_type: str, source_id: str,
                        permission_status: str = PRIVATE,
                        metadata: dict | None = None) -> dict:
        """Create a provenance envelope for an extracted item."""
        envelope = {
            "source_type": source_type,
            "source_id": source_id,
            "date_added": datetime.now().isoformat(),
            "permission_status": permission_status,
        }
        if metadata:
            envelope["metadata"] = metadata
        self.records.append(envelope)
        return envelope

    def update_permission(self, source_id: str, new_status: str) -> bool:
        """Update permission status for a record."""
        for rec in self.records:
            if rec["source_id"] == source_id:
                rec["permission_status"] = new_status
                rec["date_updated"] = datetime.now().isoformat()
                return True
        return False

    def get_records(self, permission_status: str | None = None) -> list[dict]:
        """Get records, optionally filtered by permission status."""
        if permission_status:
            return [r for r in self.records if r["permission_status"] == permission_status]
        return list(self.records)


# ══════════════════════════════════════════════════════════════════════
# CLASS 2: INPUT HANDLER
# ══════════════════════════════════════════════════════════════════════
class InputHandler:
    """Accept paragraph via CLI, file, or interactive stdin."""

    def __init__(self):
        self.paragraphs: list[dict] = []

    def load_from_text(self, text: str) -> dict:
        """Load paragraph from direct text input."""
        paragraph_id = self._generate_id(text)
        para = {
            "paragraph_id": paragraph_id,
            "text": text,
            "source": "cli_text",
            "timestamp": datetime.now().isoformat(),
        }
        self.paragraphs.append(para)
        return para

    def load_from_file(self, filepath: str) -> list[dict]:
        """Load paragraphs from a file (one per line or blank-line separated)."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        content = path.read_text(encoding="utf-8")
        # Split by blank lines for multi-paragraph files
        raw_paragraphs = re.split(r"\n\s*\n", content)
        results = []
        for text in raw_paragraphs:
            text = text.strip()
            if text:
                para = self.load_from_text(text)
                results.append(para)
        return results

    def load_interactive(self) -> dict:
        """Load paragraph from interactive stdin."""
        print(f"{C}Enter paragraph (empty line to finish):{NC}")
        lines = []
        while True:
            try:
                line = input()
                if not line.strip() and lines:
                    break
                lines.append(line)
            except EOFError:
                break
        text = "\n".join(lines).strip()
        if text:
            return self.load_from_text(text)
        return {}

    def _generate_id(self, text: str) -> str:
        """Generate hash-based paragraph ID."""
        hash_input = text.encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()[:16]

    def get_paragraphs(self) -> list[dict]:
        """Get all loaded paragraphs."""
        return list(self.paragraphs)


# ══════════════════════════════════════════════════════════════════════
# CLASS 3: FIRST PASS ANALYZER
# ══════════════════════════════════════════════════════════════════════
class FirstPassAnalyzer:
    """Detect language, text type, register, tone, audience."""

    # Common Zolai function words
    ZOLAI_FUNCTION_WORDS: ClassVar[set[str]] = {
        "a", "hi", "in", "leh", "hang", "ci", "lo", "si", "tu",
        "hiam", "pen", "ta", "kei", "sung", "ki", "na", "pi",
    }

    # Common English function words
    ENGLISH_FUNCTION_WORDS: ClassVar[set[str]] = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "shall",
        "can", "could", "may", "might", "must", "should", "would",
        "and", "but", "or", "nor", "for", "yet", "so",
        "in", "on", "at", "to", "with", "by", "from",
    }

    def analyze(self, text: str) -> dict:
        """Full first-pass analysis."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)
        if not words:
            return self._empty_result()

        lower_words = [w.lower() for w in words]

        # Language detection
        zo_count = sum(1 for w in lower_words if w in self.ZOLAI_FUNCTION_WORDS)
        en_count = sum(1 for w in lower_words if w in self.ENGLISH_FUNCTION_WORDS)
        total = len(words)
        zo_ratio = zo_count / total if total else 0
        en_ratio = en_count / total if total else 0

        if zo_ratio > en_ratio * 2:
            language = "ZO"
        elif en_ratio > zo_ratio * 2:
            language = "EN"
        else:
            language = "MIXED"

        # Text type detection
        text_type = self._detect_text_type(text, words, lower_words)

        # Register detection
        register = self._detect_register(text, words, lower_words)

        # Tone detection
        tone = self._detect_tone(text, words, lower_words)

        # Audience detection
        audience = self._detect_audience(text_type, register, tone)

        return {
            "language": language,
            "zo_ratio": round(zo_ratio, 3),
            "en_ratio": round(en_ratio, 3),
            "word_count": total,
            "sentence_count": len(re.split(r"[.!?]+", text)),
            "text_type": text_type,
            "register": register,
            "tone": tone,
            "audience": audience,
        }

    def _detect_text_type(self, text: str, words: list[str],
                          lower_words: list[str]) -> str:
        """Detect text type: narrative/expository/descriptive/persuasive/conversational."""
        # Narrative markers
        narrative_markers = {"ci", "hei", "om", "in", "leh", "hiam"}
        narrative_count = sum(1 for w in lower_words if w in narrative_markers)

        # Expository markers
        expository_markers = {"thei", "kia", "a", "pen"}
        expository_count = sum(1 for w in lower_words if w in expository_markers)

        # Descriptive markers
        descriptive_markers = {"hih", "kha", "sang", "ta"}
        descriptive_count = sum(1 for w in lower_words if w in descriptive_markers)

        # Persuasive markers
        persuasive_markers = {"kei", "ang", "gal", "khawh", "thupha"}
        persuasive_count = sum(1 for w in lower_words if w in persuasive_markers)

        # Conversational markers
        conversational_markers = {"hiam", "kua", "bang", "mai", "lah"}
        conversational_count = sum(1 for w in lower_words if w in conversational_markers)

        counts = {
            "narrative": narrative_count,
            "expository": expository_count,
            "descriptive": descriptive_count,
            "persuasive": persuasive_count,
            "conversational": conversational_count,
        }

        return max(counts, key=counts.get) if counts else "unknown"

    def _detect_register(self, text: str, words: list[str],
                         lower_words: list[str]) -> str:
        """Detect register: formal/informal/literary/religious."""
        # Formal indicators: longer sentences, complex structure
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        sentence_count = len(re.split(r"[.!?]+", text))
        avg_sentence_len = len(words) / max(sentence_count, 1)

        # Religious markers
        religious_words = {"pasian", "topa", "thupha", "kuankhiat", "kumpi", "siang"}
        religious_count = sum(1 for w in lower_words if w in religious_words)

        # Literary markers
        literary_markers = {"sung", "zat", "hih", "cih"}
        literary_count = sum(1 for w in lower_words if w in literary_markers)

        if religious_count > 2:
            return "religious"
        if avg_sentence_len > 20 and avg_word_len > 5:
            return "formal"
        if literary_count > 2:
            return "literary"
        if avg_sentence_len < 10:
            return "informal"
        return "neutral"

    def _detect_tone(self, text: str, words: list[str],
                     lower_words: list[str]) -> str:
        """Detect tone: positive/negative/neutral/urgent."""
        positive_words = {"thupha", "mu", "siang", "kha", "sang"}
        negative_words = {"kuh", "tah", "kia", "lo", "si", "tu"}
        urgent_words = {"ang", "kei", "gal", "khawh"}

        pos_count = sum(1 for w in lower_words if w in positive_words)
        neg_count = sum(1 for w in lower_words if w in negative_words)
        urg_count = sum(1 for w in lower_words if w in urgent_words)

        if urg_count > pos_count and urg_count > neg_count:
            return "urgent"
        if pos_count > neg_count * 2:
            return "positive"
        if neg_count > pos_count * 2:
            return "negative"
        return "neutral"

    def _detect_audience(self, text_type: str, register: str,
                         tone: str) -> str:
        """Detect target audience."""
        if register == "religious":
            return "religious_community"
        if text_type == "narrative" and register in ("literary", "neutral"):
            return "general_readers"
        if text_type == "expository":
            return "learners"
        if text_type == "conversational":
            return "community_members"
        if register == "formal":
            return "professional"
        return "general"

    def _empty_result(self) -> dict:
        return {
            "language": "UNKNOWN",
            "zo_ratio": 0.0,
            "en_ratio": 0.0,
            "word_count": 0,
            "sentence_count": 0,
            "text_type": "unknown",
            "register": "unknown",
            "tone": "unknown",
            "audience": "unknown",
        }


# ══════════════════════════════════════════════════════════════════════
# CLASS 4: SENTENCE SEGMENTER
# ══════════════════════════════════════════════════════════════════════
class SentenceSegmenter:
    """Split paragraph into sentences with IDs."""

    # Zolai sentence-final particles
    SENTENCE_FINAL_PARTICLES: ClassVar[set[str]] = {
        "hi", "hen", "ah", "ci", "mai", "lah", "khi",
    }

    def __init__(self, paragraph_id: str):
        self.paragraph_id = paragraph_id

    def segment(self, text: str) -> list[dict]:
        """Segment text into sentences."""
        sentences = []

        # Split on sentence-ending punctuation
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)

        for i, sent_text in enumerate(raw_sentences):
            sent_text = sent_text.strip()
            if not sent_text:
                continue

            sentence_id = f"{self.paragraph_id}:s{i}"

            # Check for sentence-final particles
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent_text)
            last_word = words[-1].lower() if words else ""
            has_particle = last_word in self.SENTENCE_FINAL_PARTICLES

            sentences.append({
                "sentence_id": sentence_id,
                "text": sent_text,
                "position": i,
                "word_count": len(words),
                "ends_with_particle": has_particle,
                "final_particle": last_word if has_particle else None,
            })

        return sentences


# ══════════════════════════════════════════════════════════════════════
# CLASS 5: SENTENCE ANALYZER
# ══════════════════════════════════════════════════════════════════════
class SentenceAnalyzer:
    """Per-sentence analysis reusing bible_engine patterns."""

    def __init__(self, glossing: GlossingEngine, morphology: MorphologyAnalyzer,
                 grammar: GrammarMatcher, verbs: VerbDatabase,
                 particles: ParticleDatabase):
        self.glossing = glossing
        self.morphology = morphology
        self.grammar = grammar
        self.verbs = verbs
        self.particles = particles

    def analyze(self, sentence: dict) -> dict:
        """Full analysis of a single sentence."""
        text = sentence["text"]
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)

        # 1. Glossing
        glosses = self.glossing.gloss_text(text)
        dict_rate = sum(1 for g in glosses if g["source"] != "miss") / len(glosses) if glosses else 0

        # 2. Morphology
        morphemes = [self.morphology.analyze(w) for w in words[:20]]

        # 3. Grammar patterns
        grammar_matches = self.grammar.match_all(text)
        sov_check = self.grammar.match_sov(text)

        # 4. Identify verbs and particles
        found_verbs = [w for w in words if self.verbs.is_verb(w)]
        found_particles = [w for w in words if self.particles.is_particle(w)]

        # 5. Sentence structure
        structure = self._analyze_structure(text, glosses)

        # 6. SOV structure detection
        sov_structure = self._detect_sov(words, glosses)

        # 7. Verb constructions
        verb_constructions = self._analyze_verb_constructions(words, found_verbs)

        # 8. Tense/aspect
        tense_aspect = self._analyze_tense_aspect(words)

        # 9. Negation
        negation = self._analyze_negation(words, found_particles)

        # 10. Questions
        question = self._analyze_question(words, found_particles)

        # 11. Connectors
        connectors = self._analyze_connectors(words, found_particles)

        # 12. Pronouns
        pronouns = self._analyze_pronouns(words)

        # 13. Semantic roles
        semantic_roles = self._analyze_semantic_roles(words, glosses)

        # 14. Sentence pattern
        pattern = self._extract_pattern(sov_structure, structure)

        return {
            "sentence_id": sentence["sentence_id"],
            "text": text,
            "word_count": len(words),
            "glosses": glosses,
            "dict_rate": round(dict_rate * 100, 1),
            "morphemes": morphemes[:10],
            "grammar_patterns": grammar_matches,
            "sov_check": sov_check,
            "structure": structure,
            "sov_structure": sov_structure,
            "verbs_found": found_verbs,
            "particles_found": found_particles,
            "verb_constructions": verb_constructions,
            "tense_aspect": tense_aspect,
            "negation": negation,
            "question": question,
            "connectors": connectors,
            "pronouns": pronouns,
            "semantic_roles": semantic_roles,
            "sentence_pattern": pattern,
        }

    def _analyze_structure(self, text: str, glosses: list[dict]) -> dict:
        """Analyze sentence structure: Subject + Object + Verb."""
        structure = {"subject": "", "object": "", "verb": "", "pattern": "SOV"}
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)

        # Find ergative marker "in" — word before it is likely subject
        for i, w in enumerate(words):
            if w.lower() == "in" and i > 0:
                prev = words[i - 1].lower()
                if prev not in ("a", "the", "leh", "hang"):
                    structure["subject"] = " ".join(words[max(0, i - 2):i + 1])
                    break

        # Find verb — usually last content word before "hi" or sentence end
        for i in range(len(words) - 1, -1, -1):
            w = words[i].lower()
            if w in ("hi", "hen", "ah"):
                if i > 0:
                    verb_word = words[i - 1]
                    for g in glosses:
                        if g["word"].lower() == verb_word.lower():
                            if g["source"] in ("dict_zo_en", "vocab_index"):
                                structure["verb"] = verb_word
                                break
                break

        # Object = everything between subject and verb
        if structure["subject"] and structure["verb"]:
            subj_end = text.lower().find(structure["subject"].lower().split()[0])
            verb_start = text.lower().rfind(structure["verb"].lower())
            if subj_end >= 0 and verb_start > subj_end:
                obj_text = text[subj_end + len(structure["subject"]):verb_start].strip()
                if obj_text:
                    structure["object"] = obj_text

        return structure

    def _detect_sov(self, words: list[str], glosses: list[dict]) -> dict:
        """Detect SOV word order."""
        if len(words) < 3:
            return {"detected": False, "confidence": UNCERTAIN, "reason": "too_short"}

        # Check if last content word is a verb
        verb_markers = {"ci", "hei", "om", "nek", "mu", "gal", "thlak", "bawl",
                        "piangsak", "kia", "thei", "hong", "sung", "khawh"}

        for i in range(len(words) - 1, -1, -1):
            w = words[i].lower()
            if w in verb_markers:
                return {
                    "detected": True,
                    "confidence": HIGH,
                    "subject": words[0] if words else "",
                    "verb": w,
                    "position": i,
                    "total_words": len(words),
                }
            # Stop at sentence-final particles
            if w in ("hi", "hen", "ah"):
                break

        return {"detected": False, "confidence": LOW, "reason": "no_verb_final"}

    def _analyze_verb_constructions(self, words: list[str],
                                     found_verbs: list[str]) -> list[dict]:
        """Analyze verb constructions."""
        constructions = []
        for verb in found_verbs:
            verb_info = self.verbs.lookup(verb)
            if verb_info:
                constructions.append({
                    "verb": verb,
                    "english": verb_info.get("english", []),
                    "transitivity": verb_info.get("transitivity", "unknown"),
                    "argument": verb_info.get("argument", ""),
                })
        return constructions

    def _analyze_tense_aspect(self, words: list[str]) -> dict:
        """Analyze tense and aspect markers."""
        markers = {
            "ding": "future",
            "uh": "perfective",
            "hi": "declarative",
            "in": "imperative/ergative",
        }
        found = []
        for w in words:
            wl = w.lower()
            if wl in markers:
                found.append({"marker": wl, "function": markers[wl]})
        return {
            "markers": found,
            "primary": found[0]["function"] if found else "unknown",
        }

    def _analyze_negation(self, words: list[str],
                          found_particles: list[str]) -> dict:
        """Analyze negation patterns."""
        neg_words = {"lo", "si", "tu"}
        found_neg = [w for w in words if w.lower() in neg_words]
        return {
            "present": bool(found_neg),
            "words": found_neg,
            "pattern": "post-verbal negation" if "lo" in found_neg else "other",
        }

    def _analyze_question(self, words: list[str],
                          found_particles: list[str]) -> dict:
        """Analyze question patterns."""
        lower_words = [w.lower() for w in words]
        if "hiam" in lower_words:
            return {"is_question": True, "type": "yes/no", "marker": "hiam"}
        if "bang" in lower_words and "ci" in lower_words:
            return {"is_question": True, "type": "content", "marker": "bang ci"}
        if "kua" in lower_words:
            return {"is_question": True, "type": "content", "marker": "kua"}
        return {"is_question": False, "type": "none"}

    def _analyze_connectors(self, words: list[str],
                            found_particles: list[str]) -> list[dict]:
        """Analyze connector usage."""
        connector_map = {
            "leh": {"type": "coordinating", "meaning": "and"},
            "hang": {"type": "coordinating", "meaning": "but/however"},
            "cih": {"type": "coordinating", "meaning": "then/and then"},
            "sung": {"type": "subordinating", "meaning": "inside/quotative"},
            "zat": {"type": "subordinating", "meaning": "when/at the time of"},
        }
        connectors = []
        for w in words:
            wl = w.lower()
            if wl in connector_map:
                connectors.append({
                    "word": wl,
                    "type": connector_map[wl]["type"],
                    "meaning": connector_map[wl]["meaning"],
                })
        return connectors

    def _analyze_pronouns(self, words: list[str]) -> list[dict]:
        """Analyze pronoun usage."""
        pronouns = {
            "ki": {"type": "reflexive", "meaning": "self/oneself"},
            "a": {"type": "possessive", "meaning": "his/her/its"},
        }
        found = []
        for w in words:
            wl = w.lower()
            if wl in pronouns:
                found.append({
                    "word": wl,
                    "type": pronouns[wl]["type"],
                    "meaning": pronouns[wl]["meaning"],
                })
        return found

    def _analyze_semantic_roles(self, words: list[str],
                                glosses: list[dict]) -> dict:
        """Analyze semantic roles (heuristic)."""
        roles = {"agent": "", "patient": "", "instrument": "", "location": ""}

        # Find ergative marker for agent
        for i, w in enumerate(words):
            if w.lower() == "in" and i > 0:
                roles["agent"] = words[i - 1]
                break

        # Verb at end
        verb_markers = {"ci", "hei", "om", "nek", "mu", "gal", "thlak", "bawl",
                        "piangsak", "kia", "thei", "hong", "sung", "khawh"}
        for i in range(len(words) - 1, -1, -1):
            if words[i].lower() in verb_markers:
                if roles["agent"] and i > 1:
                    # Patient = words between agent and verb
                    patient_words = []
                    for j in range(1, i):
                        if words[j].lower() != "in":
                            patient_words.append(words[j])
                    roles["patient"] = " ".join(patient_words)
                break

        return roles

    def _extract_pattern(self, sov: dict, structure: dict) -> dict:
        """Extract reusable sentence pattern."""
        pattern = {
            "template": "",
            "zo_pattern": "",
            "en_pattern": "",
        }
        if sov.get("detected") and sov.get("verb"):
            pattern["template"] = f"Subject + [Object] + {sov['verb']}"
            pattern["zo_pattern"] = f"[Subject] + [Object] + {sov['verb']}"
            pattern["en_pattern"] = "[Subject] + [Object] + [verb]"
        elif structure["subject"] and structure["verb"]:
            pattern["template"] = f"Subject + [Object] + {structure['verb']}"
            pattern["zo_pattern"] = f"[Subject] + [Object] + {structure['verb']}"
            pattern["en_pattern"] = "[Subject] + [Object] + [verb]"
        return pattern


# ══════════════════════════════════════════════════════════════════════
# CLASS 6: PARAGRAPH ANALYZER
# ══════════════════════════════════════════════════════════════════════
class ParagraphAnalyzer:
    """Topic extraction, cohesion, logical sequence, rhetorical structure."""

    # Common Zolai connectors
    CONNECTORS: ClassVar[dict[str, dict]] = {
        "leh": {"type": "coordinating", "meaning": "and"},
        "hang": {"type": "coordinating", "meaning": "but/however"},
        "cih": {"type": "coordinating", "meaning": "then/and then"},
        "sung": {"type": "subordinating", "meaning": "inside/quotative"},
        "zat": {"type": "subordinating", "meaning": "when/at the time of"},
        "hih": {"type": "relative", "meaning": "which/that"},
        "a": {"type": "article", "meaning": "the/possessive"},
    }

    def __init__(self, zo_en: dict[str, list[str]]):
        self.zo_en = zo_en

    def analyze(self, sentences: list[dict], paragraph_id: str) -> dict:
        """Full paragraph analysis."""
        all_words = []
        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"])
            all_words.extend([w.lower() for w in words])

        # Topic extraction
        topic = self._extract_topic(all_words, sentences)

        # Main idea + supporting ideas
        ideas = self._extract_ideas(sentences, topic)

        # Logical sequence
        sequence = self._analyze_sequence(sentences)

        # Cohesion scoring
        cohesion = self._score_cohesion(sentences, all_words)

        # Connector inventory
        connector_inventory = self._inventory_connectors(all_words)

        # Topic development arc
        arc = self._analyze_topic_development(sentences, topic)

        # Rhetorical structure
        rhetorical = self._analyze_rhetorical(sentences)

        return {
            "paragraph_id": paragraph_id,
            "sentence_count": len(sentences),
            "word_count": len(all_words),
            "topic": topic,
            "ideas": ideas,
            "logical_sequence": sequence,
            "cohesion": cohesion,
            "connector_inventory": connector_inventory,
            "topic_development_arc": arc,
            "rhetorical_structure": rhetorical,
        }

    def _extract_topic(self, all_words: list[str],
                       sentences: list[dict]) -> dict:
        """Extract paragraph topic from most frequent content words."""
        # Count word frequency
        word_freq = Counter(all_words)

        # Filter out function words
        function_words = {
            "a", "hi", "in", "leh", "hang", "ci", "lo", "si", "tu",
            "hiam", "pen", "ta", "kei", "sung", "ki", "na", "pi",
        }
        content_words = {w: f for w, f in word_freq.items()
                         if w not in function_words and len(w) > 2}

        # Get top content words
        top_words = sorted(content_words.items(), key=lambda x: x[1], reverse=True)[:5]

        # First/last sentence bias
        first_words = re.findall(r"[a-zA-Z\u0027\u2019]+",
                                  sentences[0]["text"] if sentences else "")
        last_words = re.findall(r"[a-zA-Z\u0027\u2019]+",
                                 sentences[-1]["text"] if sentences else "")

        return {
            "top_words": [{"word": w, "frequency": f} for w, f in top_words],
            "first_sentence_words": [w.lower() for w in first_words[:5]],
            "last_sentence_words": [w.lower() for w in last_words[:5]],
            "topic_words": [w for w, _ in top_words[:3]],
        }

    def _extract_ideas(self, sentences: list[dict], topic: dict) -> dict:
        """Extract main idea and supporting ideas."""
        if not sentences:
            return {"main_idea": "", "supporting_ideas": []}

        # Main idea: first sentence (usually)
        main_idea = sentences[0]["text"] if sentences else ""

        # Supporting ideas: remaining sentences
        supporting = [s["text"] for s in sentences[1:]]

        return {
            "main_idea": main_idea,
            "supporting_ideas": supporting,
            "idea_count": len(supporting) + 1,
        }

    def _analyze_sequence(self, sentences: list[dict]) -> dict:
        """Analyze logical sequence (temporal/connective markers)."""
        markers = {
            "temporal": {"zat": "when", "cih": "then", "leh": "and"},
            "contrastive": {"hang": "but", "kia": "only/but"},
            "causal": {"cih": "therefore", "kia": "because"},
        }

        sequence_type = "chronological"
        found_markers = []

        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"])
            for w in words:
                wl = w.lower()
                for cat, marker_map in markers.items():
                    if wl in marker_map:
                        found_markers.append({
                            "marker": wl,
                            "category": cat,
                            "meaning": marker_map[wl],
                        })
                        if cat == "contrastive":
                            sequence_type = "contrastive"
                        elif cat == "causal":
                            sequence_type = "causal"

        return {
            "type": sequence_type,
            "markers": found_markers,
            "marker_count": len(found_markers),
        }

    def _score_cohesion(self, sentences: list[dict],
                        all_words: list[str]) -> dict:
        """Score paragraph cohesion."""
        if not sentences:
            return {"score": 0.0, "factors": {}}

        # Connector density
        connector_words = {"leh", "hang", "cih", "sung", "zat", "hih"}
        connector_count = sum(1 for w in all_words if w in connector_words)
        connector_density = connector_count / len(sentences) if sentences else 0

        # Reference word reuse
        word_freq = Counter(all_words)
        repeated_words = sum(1 for f in word_freq.values() if f > 1)
        reference_ratio = repeated_words / len(word_freq) if word_freq else 0

        # Lexical chain (content word overlap between sentences)
        lexical_chain_score = 0
        if len(sentences) > 1:
            for i in range(len(sentences) - 1):
                words1 = set(re.findall(r"[a-zA-Z\u0027\u2019]+",
                                         sentences[i]["text"].lower()))
                words2 = set(re.findall(r"[a-zA-Z\u0027\u2019]+",
                                         sentences[i + 1]["text"].lower()))
                if words1 and words2:
                    overlap = len(words1 & words2) / min(len(words1), len(words2))
                    lexical_chain_score += overlap
            lexical_chain_score /= len(sentences) - 1

        # Overall cohesion score (0-1)
        cohesion_score = (
            min(connector_density / 2.0, 0.3) +
            min(reference_ratio, 0.3) +
            min(lexical_chain_score, 0.4)
        )

        return {
            "score": round(min(cohesion_score, 1.0), 3),
            "connector_density": round(connector_density, 3),
            "reference_ratio": round(reference_ratio, 3),
            "lexical_chain_score": round(lexical_chain_score, 3),
        }

    def _inventory_connectors(self, all_words: list[str]) -> dict:
        """Inventory all connectors in the paragraph."""
        inventory = {}
        for w in all_words:
            if w in self.CONNECTORS:
                if w not in inventory:
                    inventory[w] = {
                        "count": 0,
                        "type": self.CONNECTORS[w]["type"],
                        "meaning": self.CONNECTORS[w]["meaning"],
                    }
                inventory[w]["count"] += 1
        return inventory

    def _analyze_topic_development(self, sentences: list[dict],
                                    topic: dict) -> dict:
        """Analyze topic development arc: introduction → body → conclusion."""
        if not sentences:
            return {"arc": "empty", "phases": []}

        phases = []
        total = len(sentences)

        if total >= 3:
            # Introduction (first 20-30%)
            intro_end = max(1, int(total * 0.25))
            phases.append({
                "phase": "introduction",
                "sentences": list(range(intro_end)),
                "topic_words": topic.get("first_sentence_words", []),
            })

            # Body (middle 50-60%)
            body_start = intro_end
            body_end = max(body_start + 1, int(total * 0.75))
            phases.append({
                "phase": "body",
                "sentences": list(range(body_start, body_end)),
                "topic_words": topic.get("topic_words", []),
            })

            # Conclusion (last 20-30%)
            phases.append({
                "phase": "conclusion",
                "sentences": list(range(body_end, total)),
                "topic_words": topic.get("last_sentence_words", []),
            })
        else:
            phases.append({
                "phase": "single",
                "sentences": list(range(total)),
                "topic_words": topic.get("topic_words", []),
            })

        return {"arc": "structured" if total >= 3 else "simple", "phases": phases}

    def _analyze_rhetorical(self, sentences: list[dict]) -> dict:
        """Analyze rhetorical structure (parallelism, repetition, contrast)."""
        rhetorical_devices = []

        if len(sentences) < 2:
            return {"devices": rhetorical_devices, "complexity": "simple"}

        # Check for parallelism (similar sentence structures)
        structures = []
        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"])
            structures.append(len(words))

        # Check if sentence lengths are similar (parallelism)
        if structures:
            avg_len = sum(structures) / len(structures)
            variance = sum((l - avg_len) ** 2 for l in structures) / len(structures)
            if variance < 10:  # Low variance = parallelism
                rhetorical_devices.append({
                    "device": "parallelism",
                    "evidence": f"sentence lengths: {structures}",
                })

        # Check for repetition
        all_words = []
        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"].lower())
            all_words.extend(words)

        word_freq = Counter(all_words)
        repeated = [(w, f) for w, f in word_freq.most_common(10) if f > 2]
        if repeated:
            rhetorical_devices.append({
                "device": "repetition",
                "words": [{"word": w, "count": f} for w, f in repeated[:5]],
            })

        # Check for contrast markers
        contrast_words = {"hang", "kia"}
        contrast_count = sum(1 for w in all_words if w in contrast_words)
        if contrast_count > 0:
            rhetorical_devices.append({
                "device": "contrast",
                "markers": contrast_count,
            })

        complexity = "complex" if len(rhetorical_devices) > 1 else "simple"
        return {"devices": rhetorical_devices, "complexity": complexity}


# ══════════════════════════════════════════════════════════════════════
# CLASS 7: STYLE PROFILER
# ══════════════════════════════════════════════════════════════════════
class StyleProfiler:
    """Style fingerprinting and profile matching."""

    # Style feature dimensions
    FEATURE_DIMENSIONS: ClassVar[list[str]] = [
        "formality", "complexity", "emotionality", "narrative_density",
        "religious_markers", "connectors_per_sentence", "avg_sentence_length",
        "vocab_rarity",
    ]

    # Religious words
    RELIGIOUS_WORDS: ClassVar[set[str]] = {
        "pasian", "topa", "thupha", "kuankhiat", "kumpi", "siang", "kia",
    }

    def __init__(self, zo_en: dict[str, list[str]], vocab: dict[str, dict]):
        self.zo_en = zo_en
        self.vocab = vocab

    def profile(self, sentences: list[dict], paragraph_analysis: dict) -> dict:
        """Create style fingerprint for a paragraph."""
        if not sentences:
            return self._empty_profile()

        all_words = []
        sentence_lengths = []
        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"])
            all_words.extend([w.lower() for w in words])
            sentence_lengths.append(len(words))

        total_words = len(all_words)
        if total_words == 0:
            return self._empty_profile()

        # 1. Formality (based on sentence length, vocabulary)
        avg_sent_len = sum(sentence_lengths) / len(sentence_lengths)
        formality = min(avg_sent_len / 25.0, 1.0)

        # 2. Complexity (based on vocabulary rarity, sentence length)
        rare_words = sum(1 for w in all_words if w not in self.zo_en and len(w) > 4)
        vocab_rarity = rare_words / total_words if total_words else 0
        complexity = min((vocab_rarity * 2 + avg_sent_len / 30.0) / 2, 1.0)

        # 3. Emotionality (based on exclamative particles, religious words)
        exclamative = {"khi", "mai", "lah"}
        excl_count = sum(1 for w in all_words if w in exclamative)
        emotionality = min(excl_count / len(sentences) if sentences else 0, 1.0)

        # 4. Narrative density (from paragraph analysis)
        narrative_density = 0.5
        if paragraph_analysis.get("ideas", {}).get("idea_count", 0) > 2:
            narrative_density = 0.7
        if paragraph_analysis.get("topic_development_arc", {}).get("arc") == "structured":
            narrative_density = 0.8

        # 5. Religious markers
        religious_count = sum(1 for w in all_words if w in self.RELIGIOUS_WORDS)
        religious_markers = min(religious_count / total_words * 10, 1.0)

        # 6. Connectors per sentence
        connector_words = {"leh", "hang", "cih", "sung", "zat", "hih"}
        connector_count = sum(1 for w in all_words if w in connector_words)
        connectors_per_sentence = connector_count / len(sentences) if sentences else 0

        # 7. Average sentence length
        avg_sentence_length = avg_sent_len

        # 8. Vocab rarity
        vocab_rarity_final = vocab_rarity

        # Create fingerprint vector
        fingerprint = {
            "formality": round(formality, 3),
            "complexity": round(complexity, 3),
            "emotionality": round(emotionality, 3),
            "narrative_density": round(narrative_density, 3),
            "religious_markers": round(religious_markers, 3),
            "connectors_per_sentence": round(connectors_per_sentence, 3),
            "avg_sentence_length": round(avg_sentence_length, 3),
            "vocab_rarity": round(vocab_rarity_final, 3),
        }

        # Match to closest profile
        matched_profile = self._match_profile(fingerprint)

        return {
            "fingerprint": fingerprint,
            "matched_profile": matched_profile,
            "sentence_count": len(sentences),
            "total_words": total_words,
        }

    def _match_profile(self, fingerprint: dict) -> dict:
        """Match fingerprint to closest style profile."""
        best_match = None
        best_similarity = -1

        for profile_name, profile_data in STYLE_PROFILES.items():
            similarity = self._calculate_similarity(fingerprint, profile_data)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = profile_name

        return {
            "name": best_match,
            "similarity": round(best_similarity, 3),
            "description": STYLE_PROFILES.get(best_match, {}).get("description", ""),
        }

    def _calculate_similarity(self, fingerprint: dict,
                              profile: dict) -> float:
        """Calculate similarity between fingerprint and profile."""
        similarity = 0.0
        dimensions = len(self.FEATURE_DIMENSIONS)

        for dim in self.FEATURE_DIMENSIONS:
            fp_val = fingerprint.get(dim, 0.0)
            pr_val = profile.get(dim, 0.0)

            # Handle connectors_per_sentence specially (0-2 range)
            if dim == "connectors_per_sentence":
                fp_norm = min(fp_val / 2.0, 1.0)
                pr_norm = min(pr_val / 2.0, 1.0)
            # Handle avg_sentence_length specially (0-30 range)
            elif dim == "avg_sentence_length":
                fp_norm = min(fp_val / 30.0, 1.0)
                pr_norm = min(pr_val / 30.0, 1.0)
            else:
                fp_norm = min(fp_val, 1.0)
                pr_norm = min(pr_val, 1.0)

            # Euclidean distance component
            similarity += 1.0 - abs(fp_norm - pr_norm)

        return similarity / dimensions if dimensions else 0.0

    def _empty_profile(self) -> dict:
        return {
            "fingerprint": {dim: 0.0 for dim in self.FEATURE_DIMENSIONS},
            "matched_profile": {"name": "UNKNOWN", "similarity": 0.0},
            "sentence_count": 0,
            "total_words": 0,
        }


# ══════════════════════════════════════════════════════════════════════
# CLASS 8: STYLE VOCAB EXTRACTOR
# ══════════════════════════════════════════════════════════════════════
class StyleVocabExtractor:
    """Extract vocabulary and phrases by register/style."""

    REGISTER_WORDS: ClassVar[dict[str, set[str]]] = {
        "everyday": {"mu", "nek", "hei", "ci", "om", "thei"},
        "formal": {"piangsak", "kuankhiat", "thupha", "kumpi"},
        "literary": {"sung", "zat", "hih", "cih"},
        "religious": {"pasian", "topa", "thupha", "siang"},
        "emotional": {"khi", "mai", "lah", "tah"},
        "persuasive": {"kei", "ang", "gal", "khawh"},
        "descriptive": {"hih", "kha", "sang", "ta"},
        "transitional": {"leh", "hang", "cih", "sung"},
    }

    LEARNING_STATUSES: ClassVar[list[str]] = [
        "OBSERVED", "EXTRACTED", "VALIDATED", "GENERALIZED", "CONFIRMED",
    ]

    def __init__(self, zo_en: dict[str, list[str]], vocab: dict[str, dict],
                 collocations: dict[str, int], provenance: ProvenanceManager):
        self.zo_en = zo_en
        self.vocab = vocab
        self.collocations = collocations
        self.provenance = provenance
        self.extracted_items: list[dict] = []

    def extract(self, sentences: list[dict], style_profile: dict,
                paragraph_id: str) -> list[dict]:
        """Extract vocabulary and phrases by register."""
        items = []
        matched_style = style_profile.get("matched_profile", {}).get("name", "UNKNOWN")

        for sent in sentences:
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", sent["text"])
            for word in words:
                wl = word.lower()

                # Determine register
                register = self._classify_register(wl)

                # Get translation
                translation = self.zo_en.get(wl, ["?"])[0] if wl in self.zo_en else "?"

                # Get frequency
                freq = self.vocab.get(wl, {}).get("frequency", 0)

                # Get collocations
                colls = [k for k in self.collocations if wl in k]

                # Create item
                item = {
                    "word": wl,
                    "lemma": wl,
                    "pos": self._heuristic_pos(wl),
                    "meaning": translation,
                    "contextual_meaning": self._contextual_meaning(wl, sent["text"]),
                    "register_tag": register,
                    "style_tag": matched_style,
                    "collocations": colls[:5],
                    "examples": [sent["text"]],
                    "frequency": freq,
                    "learning_status": "EXTRACTED",
                    "paragraph_id": paragraph_id,
                    "sentence_id": sent.get("sentence_id", ""),
                }

                # Add provenance
                envelope = self.provenance.create_envelope(
                    source_type="paragraph_analysis",
                    source_id=f"{paragraph_id}:{wl}",
                    permission_status=TRAINING_ELIGIBLE,
                    metadata={"style": matched_style, "register": register},
                )
                item["provenance"] = envelope

                # Check for duplicates
                if not self._is_duplicate(item):
                    items.append(item)
                    self.extracted_items.append(item)

        return items

    def _classify_register(self, word: str) -> str:
        """Classify word register."""
        for register, words in self.REGISTER_WORDS.items():
            if word in words:
                return register
        return "neutral"

    def _heuristic_pos(self, word: str) -> str:
        """Heuristic POS tagging."""
        # Common function words
        if word in {"a", "hi", "in", "leh", "hang", "ci", "lo", "si", "tu"}:
            return "particle"
        if word in {"mu", "nek", "hei", "om", "ci", "gal", "thlak"}:
            return "verb"
        if word in {"kha", "sang", "hih"}:
            return "adjective"
        return "noun"  # default

    def _contextual_meaning(self, word: str, context: str) -> str:
        """Get contextual meaning based on surrounding text."""
        # Simple heuristic: if word appears in religious context
        religious_context = {"pasian", "topa", "thupha", "siang"}
        if word in religious_context:
            return f"religious: {self.zo_en.get(word, ['?'])[0]}"
        return self.zo_en.get(word, ["?"])[0]

    def _is_duplicate(self, item: dict) -> bool:
        """Check for duplicate items."""
        for existing in self.extracted_items:
            if (existing["word"] == item["word"] and
                    existing["sentence_id"] == item["sentence_id"]):
                return True
        return False


# ══════════════════════════════════════════════════════════════════════
# CLASS 9: GRAMMAR EXTRACTOR
# ══════════════════════════════════════════════════════════════════════
class GrammarExtractor:
    """Extract grammar patterns from real paragraph text."""

    def __init__(self, grammar_db: list[dict], provenance: ProvenanceManager):
        self.grammar_db = grammar_db
        self.provenance = provenance
        self.extracted_patterns: list[dict] = []

    def extract(self, sentences: list[dict], paragraph_id: str) -> list[dict]:
        """Extract grammar patterns from sentences."""
        patterns = []
        pattern_counter: Counter = Counter()

        for sent in sentences:
            text = sent["text"]
            words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)

            # SOV pattern
            if len(words) >= 3:
                verb_markers = {"ci", "hei", "om", "nek", "mu", "gal", "thlak",
                                "bawl", "piangsak", "kia", "thei", "hong", "sung", "khawh"}
                if words[-1].lower() in verb_markers:
                    pattern_counter["SOV"] += 1

            # Negation pattern
            for w in words:
                if w.lower() in {"lo", "si", "tu"}:
                    pattern_counter["negation"] += 1
                    break

            # Question pattern
            for w in words:
                if w.lower() == "hiam":
                    pattern_counter["question_hiam"] += 1
                    break

            # Conjunction pattern
            for w in words:
                if w.lower() in {"leh", "hang", "cih"}:
                    pattern_counter[f"conjunction_{w.lower()}"] += 1

            # Ergative pattern
            for i, w in enumerate(words):
                if w.lower() == "in" and i > 0:
                    pattern_counter["ergative_in"] += 1
                    break

        # Create pattern entries
        for pattern_name, count in pattern_counter.items():
            pattern_entry = {
                "pattern": pattern_name,
                "frequency": count,
                "confidence": EvidenceScorer.score_pattern(count, 1),
                "paragraph_id": paragraph_id,
                "examples": [s["text"] for s in sentences[:3]],
            }

            # Add provenance
            envelope = self.provenance.create_envelope(
                source_type="grammar_extraction",
                source_id=f"{paragraph_id}:{pattern_name}",
                permission_status=TRAINING_ELIGIBLE,
                metadata={"frequency": count},
            )
            pattern_entry["provenance"] = envelope

            patterns.append(pattern_entry)
            self.extracted_patterns.append(pattern_entry)

        return patterns


# ══════════════════════════════════════════════════════════════════════
# CLASS 10: PARAPHRASE ENGINE
# ══════════════════════════════════════════════════════════════════════
class ParaphraseEngine:
    """Generate paraphrases at multiple levels and styles."""

    # Paraphrase levels
    LEVELS: ClassVar[dict[int, str]] = {
        1: "Minimal — synonym substitution only",
        2: "Moderate — phrase-level rewrites",
        3: "Strong — sentence restructuring",
        4: "Structural — complete reorganization",
        5: "Style — style transformation",
    }

    # Synonym maps (Zolai)
    SYNONYM_MAP: ClassVar[dict[str, list[str]]] = {
        "mu": ["siang", "thei"],
        "ci": ["om", "thei"],
        "nek": ["mu", "khawh"],
        "hei": ["leng", "tleh"],
        "bawl": ["piangsak"],
        "thupha": ["siang", "kumpi"],
    }

    # Connector swaps
    CONNECTOR_SWAPS: ClassVar[dict[str, list[str]]] = {
        "leh": ["hang", "cih"],
        "hang": ["leh", "cih"],
        "cih": ["leh", "hang"],
    }

    # Particle swaps
    PARTICLE_SWAPS: ClassVar[dict[str, list[str]]] = {
        "hi": ["hen", "mai"],
        "hen": ["hi", "mai"],
        "lo": ["si", "tu"],
        "si": ["lo", "tu"],
        "tu": ["lo", "si"],
    }

    def __init__(self, zo_en: dict[str, list[str]], glossing: GlossingEngine):
        self.zo_en = zo_en
        self.glossing = glossing

    def paraphrase(self, text: str, level: int = 2,
                   style: str | None = None) -> dict:
        """Generate paraphrase at specified level and style."""
        if level not in self.LEVELS:
            return {"error": f"Invalid level: {level}. Use 1-5."}

        # Get original glosses for meaning preservation check
        original_glosses = self.glossing.gloss_text(text)
        original_meanings = {g["gloss"] for g in original_glosses if g["gloss"] != "?"}

        # Generate paraphrase based on level
        if level == 1:
            paraphrased = self._minimal_paraphrase(text)
        elif level == 2:
            paraphrased = self._moderate_paraphrase(text)
        elif level == 3:
            paraphrased = self._strong_paraphrase(text)
        elif level == 4:
            paraphrased = self._structural_paraphrase(text)
        elif level == 5:
            paraphrased = self._style_paraphrase(text, style or "SIMPLE")
        else:
            paraphrased = text

        # Check meaning preservation
        paraphrased_glosses = self.glossing.gloss_text(paraphrased)
        paraphrased_meanings = {g["gloss"] for g in paraphrased_glosses if g["gloss"] != "?"}

        meaning_preserved = len(original_meanings & paraphrased_meanings) / max(
            len(original_meanings), 1
        )

        return {
            "original": text,
            "paraphrased": paraphrased,
            "level": level,
            "level_description": self.LEVELS[level],
            "style": style,
            "meaning_preservation": round(meaning_preserved, 3),
            "original_meanings": list(original_meanings)[:5],
            "paraphrased_meanings": list(paraphrased_meanings)[:5],
        }

    def generate_multi_style(self, text: str) -> list[dict]:
        """Generate paraphrases in multiple styles."""
        styles = ["SIMPLE", "FORMAL", "LITERARY", "CONVERSATIONAL",
                  "EDUCATIONAL", "INSPIRATIONAL"]
        results = []
        for style in styles:
            result = self.paraphrase(text, level=5, style=style)
            results.append(result)
        return results

    def _minimal_paraphrase(self, text: str) -> str:
        """Level 1: Synonym substitution only."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)
        result = []
        for w in words:
            wl = w.lower()
            if self.SYNONYM_MAP.get(wl):
                result.append(random.choice(self.SYNONYM_MAP[wl]))
            else:
                result.append(w)
        return " ".join(result)

    def _moderate_paraphrase(self, text: str) -> str:
        """Level 2: Phrase-level rewrites + connector swaps."""
        # First do synonym substitution
        result = self._minimal_paraphrase(text)

        # Then swap connectors
        words = result.split()
        for i, w in enumerate(words):
            wl = w.lower()
            if wl in self.CONNECTOR_SWAPS:
                words[i] = random.choice(self.CONNECTOR_SWAPS[wl])
        return " ".join(words)

    def _strong_paraphrase(self, text: str) -> str:
        """Level 3: Sentence restructuring."""
        # Split into clauses
        clauses = re.split(r"\s+(?:leh|hang|cih)\s+", text)

        # Reverse clause order if multiple clauses
        if len(clauses) > 1:
            random.shuffle(clauses)

        # Apply moderate paraphrase to each clause
        result = []
        for clause in clauses:
            paraphrased = self._moderate_paraphrase(clause.strip())
            result.append(paraphrased)

        # Join with appropriate connectors
        connectors = ["leh", "hang", "cih"]
        return f" {random.choice(connectors)} ".join(result)

    def _structural_paraphrase(self, text: str) -> str:
        """Level 4: Complete reorganization."""
        words = re.findall(r"[a-zA-Z\u0027\u2019]+", text)
        if len(words) < 3:
            return text

        # Move subject to end (if SOV, make it OVS or VSO)
        verb_markers = {"ci", "hei", "om", "nek", "mu", "gal", "thlak",
                        "bawl", "piangsak", "kia", "thei", "hong", "sung", "khawh"}

        verb_idx = None
        for i in range(len(words) - 1, -1, -1):
            if words[i].lower() in verb_markers:
                verb_idx = i
                break

        if verb_idx is not None and verb_idx > 0:
            # Move verb to beginning
            verb = words[verb_idx]
            rest = words[:verb_idx] + words[verb_idx + 1:]
            result = [verb] + rest
        else:
            result = words

        # Apply strong paraphrase
        text_restructured = " ".join(result)
        return self._strong_paraphrase(text_restructured)

    def _style_paraphrase(self, text: str, style: str) -> str:
        """Level 5: Style transformation."""
        # Get base paraphrase
        base = self._moderate_paraphrase(text)

        # Apply style-specific transformations
        if style == "SIMPLE":
            return self._simplify(base)
        elif style == "FORMAL":
            return self._formalize(base)
        elif style == "LITERARY":
            return self._literarize(base)
        elif style == "CONVERSATIONAL":
            return self._conversationalize(base)
        elif style == "EDUCATIONAL":
            return self._educationalize(base)
        elif style == "INSPIRATIONAL":
            return self._inspirationalize(base)
        return base

    def _simplify(self, text: str) -> str:
        """Make text simpler."""
        words = text.split()
        # Remove complex particles, keep basic structure
        simple_words = [w for w in words if w.lower() not in {"sung", "zat", "hih"}]
        return " ".join(simple_words) if simple_words else text

    def _formalize(self, text: str) -> str:
        """Make text more formal."""
        words = text.split()
        # Add formal particles
        if words and words[-1].lower() == "hi":
            words[-1] = "hen"  # More formal ending
        return " ".join(words)

    def _literarize(self, text: str) -> str:
        """Make text more literary."""
        words = text.split()
        # Add literary particles
        if len(words) > 2:
            words.insert(1, "a")  # Add article for literary feel
        return " ".join(words)

    def _conversationalize(self, text: str) -> str:
        """Make text more conversational."""
        words = text.split()
        # Add conversational particles
        if words and words[-1].lower() not in {"mai", "lah"}:
            words.append(random.choice(["mai", "lah"]))
        return " ".join(words)

    def _educationalize(self, text: str) -> str:
        """Make text more educational."""
        words = text.split()
        # Add explanatory particles
        if len(words) > 2:
            words.insert(0, "a")  # Add article for clarity
        return " ".join(words)

    def _inspirationalize(self, text: str) -> str:
        """Make text more inspirational."""
        words = text.split()
        # Add inspirational particles
        if words and words[-1].lower() not in {"khi", "mai"}:
            words.append(random.choice(["khi", "mai"]))
        return " ".join(words)


# ══════════════════════════════════════════════════════════════════════
# CLASS 11: KNOWLEDGE BUILDER
# ══════════════════════════════════════════════════════════════════════
class KnowledgeBuilder:
    """Aggregate extracted items into JSONL for RAG."""

    def __init__(self):
        self.knowledge_files = {
            "paragraph_analyses": KNOWLEDGE_DIR / "paragraph_analyses.jsonl",
            "style_profiles": KNOWLEDGE_DIR / "style_profiles.jsonl",
            "extracted_phrases": KNOWLEDGE_DIR / "extracted_phrases.jsonl",
            "extracted_vocab": KNOWLEDGE_DIR / "extracted_vocab.jsonl",
            "grammar_from_text": KNOWLEDGE_DIR / "grammar_from_text.jsonl",
            "paraphrase_examples": KNOWLEDGE_DIR / "paraphrase_examples.jsonl",
        }
        self.index_files = {
            "phrase_index": INDEXES_DIR / "phrase_index.json",
            "vocab_index": INDEXES_DIR / "vocab_index.json",
        }

    def ensure_dirs(self):
        """Create output directories."""
        for path in self.knowledge_files.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        for path in self.index_files.values():
            path.parent.mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, filepath: Path, records: list[dict]):
        """Append records to a JSONL file."""
        with open(filepath, "a") as f:
            f.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in records)

    def build_paragraph_analysis(self, analysis: dict):
        """Store paragraph analysis."""
        self.append_jsonl(self.knowledge_files["paragraph_analyses"], [analysis])

    def build_style_profile(self, profile: dict):
        """Store style profile."""
        self.append_jsonl(self.knowledge_files["style_profiles"], [profile])

    def build_extracted_phrases(self, phrases: list[dict]):
        """Store extracted phrases."""
        self.append_jsonl(self.knowledge_files["extracted_phrases"], phrases)

    def build_extracted_vocab(self, vocab: list[dict]):
        """Store extracted vocabulary."""
        self.append_jsonl(self.knowledge_files["extracted_vocab"], vocab)

    def build_grammar_patterns(self, patterns: list[dict]):
        """Store extracted grammar patterns."""
        self.append_jsonl(self.knowledge_files["grammar_from_text"], patterns)

    def build_paraphrase_examples(self, examples: list[dict]):
        """Store paraphrase examples."""
        self.append_jsonl(self.knowledge_files["paraphrase_examples"], examples)

    def build_indexes(self):
        """Build index files for fast lookup."""
        # Phrase index
        phrase_index: dict[str, list[dict]] = defaultdict(list)
        if self.knowledge_files["extracted_phrases"].exists():
            with open(self.knowledge_files["extracted_phrases"]) as f:
                for line in f:
                    record = json.loads(line)
                    word = record.get("word", "")
                    if word:
                        phrase_index[word].append(record)

        with open(self.index_files["phrase_index"], "w") as f:
            json.dump(dict(phrase_index), f, ensure_ascii=False, indent=2)

        # Vocab index
        vocab_index: dict[str, list[dict]] = defaultdict(list)
        if self.knowledge_files["extracted_vocab"].exists():
            with open(self.knowledge_files["extracted_vocab"]) as f:
                for line in f:
                    record = json.loads(line)
                    word = record.get("word", "")
                    if word:
                        vocab_index[word].append(record)

        with open(self.index_files["vocab_index"], "w") as f:
            json.dump(dict(vocab_index), f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════
# CLASS 12: PARAGRAPH ENGINE (MAIN ORCHESTRATOR)
# ══════════════════════════════════════════════════════════════════════
class ParagraphEngine:
    """Main orchestrator — ties all modules together."""

    def __init__(self):
        print(f"{G}Loading Paragraph Engine...{NC}")

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
        self.input_handler = InputHandler()
        self.first_pass = FirstPassAnalyzer()
        self.glossing = GlossingEngine(
            self.zo_en, self.vocab, self.phrases_db, self.collocations,
            self.phrase_dict,
        )
        self.morphology = MorphologyAnalyzer()
        self.grammar = GrammarMatcher(self.grammar_patterns)
        self.verb_db = VerbDatabase(self.verbs_raw)
        self.particle_db = ParticleDatabase(self.particles_raw)
        self.provenance = ProvenanceManager()
        self.style_profiler = StyleProfiler(self.zo_en, self.vocab)
        self.vocab_extractor = StyleVocabExtractor(
            self.zo_en, self.vocab, self.collocations, self.provenance,
        )
        self.grammar_extractor = GrammarExtractor(
            self.grammar_patterns, self.provenance,
        )
        self.paraphrase_engine = ParaphraseEngine(self.zo_en, self.glossing)
        self.knowledge_builder = KnowledgeBuilder()

        # Create output directories
        self.knowledge_builder.ensure_dirs()

        print(f"  {self.verb_db.count()} verbs loaded")
        print(f"  {self.particle_db.count()} particles loaded")
        print(f"{G}Engine ready.{NC}\n")

    def analyze_text(self, text: str) -> dict:
        """Full analysis pipeline for a text."""
        # 1. Input handling
        para = self.input_handler.load_from_text(text)
        paragraph_id = para["paragraph_id"]

        # 2. First pass analysis
        first_pass = self.first_pass.analyze(text)

        # 3. Sentence segmentation
        segmenter = SentenceSegmenter(paragraph_id)
        sentences = segmenter.segment(text)

        # 4. Sentence analysis
        sentence_analyzer = SentenceAnalyzer(
            self.glossing, self.morphology, self.grammar,
            self.verb_db, self.particle_db,
        )
        sentence_analyses = [sentence_analyzer.analyze(s) for s in sentences]

        # 5. Paragraph analysis
        para_analyzer = ParagraphAnalyzer(self.zo_en)
        para_analysis = para_analyzer.analyze(sentences, paragraph_id)

        # 6. Style profiling
        style_profile = self.style_profiler.profile(sentences, para_analysis)

        # 7. Vocabulary extraction
        vocab_items = self.vocab_extractor.extract(
            sentences, style_profile, paragraph_id,
        )

        # 8. Grammar extraction
        grammar_items = self.grammar_extractor.extract(sentences, paragraph_id)

        # 9. Provenance summary
        provenance_summary = self.provenance.get_records()

        # 10. Build knowledge base
        self.knowledge_builder.build_paragraph_analysis({
            "paragraph_id": paragraph_id,
            "text": text,
            "first_pass": first_pass,
            "sentences": sentence_analyses,
            "paragraph_analysis": para_analysis,
            "style_profile": style_profile,
            "vocab_count": len(vocab_items),
            "grammar_count": len(grammar_items),
            "provenance_count": len(provenance_summary),
            "timestamp": datetime.now().isoformat(),
        })

        self.knowledge_builder.build_style_profile({
            "paragraph_id": paragraph_id,
            "style_profile": style_profile,
            "timestamp": datetime.now().isoformat(),
        })

        self.knowledge_builder.build_extracted_phrases(vocab_items)
        self.knowledge_builder.build_grammar_patterns(grammar_items)

        # Build indexes
        self.knowledge_builder.build_indexes()

        return {
            "paragraph_id": paragraph_id,
            "first_pass": first_pass,
            "sentences": sentence_analyses,
            "paragraph_analysis": para_analysis,
            "style_profile": style_profile,
            "vocab_extracted": len(vocab_items),
            "grammar_extracted": len(grammar_items),
            "provenance_records": len(provenance_summary),
        }

    def paraphrase_text(self, text: str, level: int = 2,
                        style: str | None = None) -> dict:
        """Generate paraphrase for text."""
        result = self.paraphrase_engine.paraphrase(text, level, style)

        # Store paraphrase example
        self.knowledge_builder.build_paraphrase_examples([{
            "original": text,
            "paraphrased": result["paraphrased"],
            "level": level,
            "style": style,
            "meaning_preservation": result["meaning_preservation"],
            "timestamp": datetime.now().isoformat(),
        }])

        return result

    def generate_multi_style_paraphrases(self, text: str) -> list[dict]:
        """Generate paraphrases in multiple styles."""
        results = self.paraphrase_engine.generate_multi_style(text)

        # Store all examples
        examples = []
        for r in results:
            examples.append({
                "original": text,
                "paraphrased": r["paraphrased"],
                "level": 5,
                "style": r["style"],
                "meaning_preservation": r["meaning_preservation"],
                "timestamp": datetime.now().isoformat(),
            })
        self.knowledge_builder.build_paraphrase_examples(examples)

        return results

    def show_stats(self):
        """Show paragraph engine statistics."""
        print(f"\n{Y}═══ Paragraph Engine Statistics ═══{NC}\n")

        # Dictionary stats
        print(f"  ZO→EN dictionary: {len(self.zo_en)} entries")
        print(f"  Vocabulary index: {len(self.vocab)} words")
        print(f"  Grammar patterns: {len(self.grammar_patterns)} patterns")
        print(f"  Collocations: {len(self.collocations)} pairs")
        print(f"  Phrase entries: {len(self.phrase_dict)}")

        # Database stats
        print(f"\n  {Y}Databases:{NC}")
        print(f"    Verbs: {self.verb_db.count()} (file: {len(self.verbs_raw)}, built-in: {len(VerbDatabase.BUILTIN_VERBS)})")
        print(f"    Particles: {self.particle_db.count()} (file: {len(self.particles_raw)}, built-in: {len(ParticleDatabase.BUILTIN_PARTICLES)})")
        print(f"    Phrase DB: {len(self.phrases_db)} entries")

        # Style profiles
        print(f"\n  {Y}Style Profiles:{NC}")
        print(f"    Available: {len(STYLE_PROFILES)}")
        for name in STYLE_PROFILES:
            print(f"      - {name}")

        # Output stats
        print(f"\n  {Y}Output Directories:{NC}")
        for name, path in self.knowledge_builder.knowledge_files.items():
            if path.exists():
                with open(path) as f:
                    count = sum(1 for _ in f)
                print(f"    {name}: {count} records")
            else:
                print(f"    {name}: 0 records")

        # Index stats
        for name, path in self.knowledge_builder.index_files.items():
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                print(f"    {name}: {len(data)} entries")

        print()


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Zolai Paragraph Engine — Analysis, Style Learning & Paraphrase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Analyze mode:
  python paragraph_engine.py --analyze --text "Pasian in hi leh a piangsak hi"
  python paragraph_engine.py --analyze --file input.txt

Paraphrase mode:
  python paragraph_engine.py --paraphrase --text "..." --level 2
  python paragraph_engine.py --paraphrase --text "..." --style FORMAL

Multi-style mode:
  python paragraph_engine.py --paraphrase --text "..." --multi-style

Style mode:
  python paragraph_engine.py --style --text "..."

Search mode:
  python paragraph_engine.py --search "Pasian"

Stats:
  python paragraph_engine.py --stats

Interactive mode:
  python paragraph_engine.py --interactive
""",
    )

    # Analyze mode
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze a paragraph")
    parser.add_argument("--text", type=str,
                        help="Text to analyze/paraphrase")
    parser.add_argument("--file", type=str,
                        help="File containing text to analyze")

    # Paraphrase mode
    parser.add_argument("--paraphrase", action="store_true",
                        help="Generate paraphrase")
    parser.add_argument("--level", type=int, default=2, choices=range(1, 6),
                        help="Paraphrase level (1-5)")
    parser.add_argument("--style", type=str,
                        choices=["SIMPLE", "FORMAL", "LITERARY", "CONVERSATIONAL",
                                 "EDUCATIONAL", "INSPIRATIONAL"],
                        help="Target style for paraphrase")
    parser.add_argument("--multi-style", action="store_true",
                        help="Generate paraphrases in all styles")

    # Style mode
    parser.add_argument("--style-analysis", action="store_true",
                        help="Analyze style of text")

    # Search mode
    parser.add_argument("--search", type=str,
                        help="Search extracted vocabulary")

    # Stats
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics")

    # Interactive
    parser.add_argument("--interactive", action="store_true",
                        help="Interactive mode")

    args = parser.parse_args()

    # Build engine
    engine = ParagraphEngine()

    if args.stats:
        engine.show_stats()
        return

    if args.interactive:
        print(f"\n{Y}═══ Interactive Mode ═══{NC}")
        print("Commands: analyze, paraphrase, multi-style, style, stats, quit")
        while True:
            try:
                cmd = input(f"\n{C}Command:{NC} ").strip().lower()
                if cmd in ("quit", "exit", "q"):
                    break
                elif cmd == "analyze":
                    text = input("Enter text: ").strip()
                    if text:
                        result = engine.analyze_text(text)
                        print(f"\n{G}═══ Analysis Result ═══{NC}")
                        print(f"  Paragraph ID: {result['paragraph_id']}")
                        print(f"  Language: {result['first_pass']['language']}")
                        print(f"  Text type: {result['first_pass']['text_type']}")
                        print(f"  Register: {result['first_pass']['register']}")
                        print(f"  Style: {result['style_profile']['matched_profile']['name']}")
                        print(f"  Sentences: {len(result['sentences'])}")
                        print(f"  Vocab extracted: {result['vocab_extracted']}")
                        print(f"  Grammar extracted: {result['grammar_extracted']}")
                elif cmd == "paraphrase":
                    text = input("Enter text: ").strip()
                    level = input("Level (1-5, default 2): ").strip()
                    level = int(level) if level else 2
                    result = engine.paraphrase_text(text, level)
                    print(f"\n{G}═══ Paraphrase ═══{NC}")
                    print(f"  Original: {result['original']}")
                    print(f"  Paraphrased: {result['paraphrased']}")
                    print(f"  Level: {result['level_description']}")
                    print(f"  Meaning preserved: {result['meaning_preservation']*100:.1f}%")
                elif cmd == "multi-style":
                    text = input("Enter text: ").strip()
                    if text:
                        results = engine.generate_multi_style_paraphrases(text)
                        print(f"\n{G}═══ Multi-Style Paraphrases ═══{NC}")
                        for r in results:
                            print(f"\n  {M}{r['style']}:{NC}")
                            print(f"    {r['paraphrased']}")
                elif cmd == "style":
                    text = input("Enter text: ").strip()
                    if text:
                        result = engine.paraphrase_engine.paraphrase(text, level=1)
                        print(f"\n{G}═══ Style Analysis ═══{NC}")
                        print(f"  Fingerprint: {result.get('fingerprint', {})}")
                elif cmd == "stats":
                    engine.show_stats()
                else:
                    print(f"{R}Unknown command: {cmd}{NC}")
            except (EOFError, KeyboardInterrupt):
                break
        print(f"\n{G}Goodbye!{NC}")
        return

    # Get text from arguments
    text = args.text
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()

    if args.analyze and text:
        result = engine.analyze_text(text)
        print(f"\n{G}═══ Analysis Result ═══{NC}")
        print(f"  Paragraph ID: {result['paragraph_id']}")
        print(f"  Language: {result['first_pass']['language']}")
        print(f"  Text type: {result['first_pass']['text_type']}")
        print(f"  Register: {result['first_pass']['register']}")
        print(f"  Tone: {result['first_pass']['tone']}")
        print(f"  Audience: {result['first_pass']['audience']}")
        print(f"  Style: {result['style_profile']['matched_profile']['name']}")
        print(f"  Style similarity: {result['style_profile']['matched_profile']['similarity']}")
        print(f"  Sentences: {len(result['sentences'])}")
        print(f"  Vocab extracted: {result['vocab_extracted']}")
        print(f"  Grammar extracted: {result['grammar_extracted']}")
        print(f"  Provenance records: {result['provenance_records']}")
        return

    if args.paraphrase and text:
        if args.multi_style:
            results = engine.generate_multi_style_paraphrases(text)
            print(f"\n{G}═══ Multi-Style Paraphrases ═══{NC}")
            for r in results:
                print(f"\n  {M}{r['style']}:{NC}")
                print(f"    {r['paraphrased']}")
                print(f"    Meaning preserved: {r['meaning_preservation']*100:.1f}%")
        else:
            result = engine.paraphrase_text(text, args.level, args.style)
            print(f"\n{G}═══ Paraphrase ═══{NC}")
            print(f"  Original: {result['original']}")
            print(f"  Paraphrased: {result['paraphrased']}")
            print(f"  Level: {result['level_description']}")
            print(f"  Meaning preserved: {result['meaning_preservation']*100:.1f}%")
        return

    if args.style_analysis and text:
        # Analyze style without full analysis
        first_pass = engine.first_pass.analyze(text)
        print(f"\n{G}═══ Style Analysis ═══{NC}")
        print(f"  Language: {first_pass['language']}")
        print(f"  Text type: {first_pass['text_type']}")
        print(f"  Register: {first_pass['register']}")
        print(f"  Tone: {first_pass['tone']}")
        print(f"  Audience: {first_pass['audience']}")
        return

    if args.search:
        print(f"\n{Y}═══ Search: '{args.search}' ═══{NC}")
        # Search extracted vocabulary
        vocab_index = engine.knowledge_builder.index_files["vocab_index"]
        if vocab_index.exists():
            with open(vocab_index) as f:
                index = json.load(f)
            query_lower = args.search.lower()
            results = {k: v for k, v in index.items() if query_lower in k}
            print(f"  Results: {len(results)}")
            for word, entries in list(results.items())[:10]:
                print(f"    {word}: {len(entries)} entries")
        else:
            print("  No vocabulary index found. Run --analyze first.")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
