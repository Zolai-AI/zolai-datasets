#!/usr/bin/env python3
"""Deep Bible context learner — per-book indexing, hyphen rules, phrase bank.

Indexes Bible data per book to learn word usage, phrase patterns,
hyphenation rules, and sentence structure. Provides a validation API
for scoring Zolai sentences against real Bible usage context.

Data sources (read-only):
  data/bible/parallel_corpus_v1.jsonl — 31,102 verses
  data/bible/vocab_index_full.jsonl — 20,929 words

Outputs (gitignored):
  data/bible/bible_book_index.json — per-book indexes
  data/bible/bible_context_usage.json — word usage statistics
  data/bible/bible_hyphen_rules.json — hyphenation rules

Usage:
    python bible_context_learner.py --build
    python bible_context_learner.py --stats
    python bible_context_learner.py --validate sentences.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]

CORPUS_PATH = WORKSPACE / "data" / "bible" / "parallel_corpus_v1.jsonl"
VOCAB_PATH = WORKSPACE / "data" / "bible" / "vocab_index_full.jsonl"
BOOK_INDEX_PATH = WORKSPACE / "data" / "bible" / "bible_book_index.json"
CONTEXT_USAGE_PATH = WORKSPACE / "data" / "bible" / "bible_context_usage.json"
HYPHEN_RULES_PATH = WORKSPACE / "data" / "bible" / "bible_hyphen_rules.json"

# Output dir also in data/bible/ (gitignored)

# ---------------------------------------------------------------------------
# Particles and word-class sets
# ---------------------------------------------------------------------------

PARTICLES = frozenset({
    "a", "in", "hi", "hiam", "un", "ah", "leh", "tawh", "panin",
    "sungah", "tungah", "kiangah", "bangin", "hangin", "ciangin",
    "dingin", "khempeuh", "khat", "te", "ni", "na", "la",
    "la-in", "tu-in", "ni-in", "pai-in", "ma-in", "ci-in",
    "mai-ah", "lai-ah", "khua-ah", "kei", "lo", "ding", "sak",
    "nak", "hen", "pia", "nei", "ci", "thei", "bawl", "thu",
    "uh", "tua", "note",
})

SUBJECT_MARKERS = frozenset({
    "ka", "na", "a", "i", "ki", "amah", "kasi", "nasi",
    "keimani", "nisu", "asuo", "isuo", "kisuo",
})

VERB_FINALS = frozenset({
    "hi", "hiam", "kei", "lo", "ding", "sak", "nak", "ah", "hen",
    "leh", "pia", "nei", "ci", "thei", "bawl", "thu",
    "ciangin", "amah", "amaute", "a", "in",
})

# Suffixes attached to verb stems via hyphens
HYPHEN_SUFFIXES = ("in", "ah", "a", "inah", "te")

# Content question words
CONTENT_QUESTIONS = frozenset({
    "banghang", "bang_hang", "bang hang", "diam", "kua",
})

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Tokenize Zolai text into words, splitting hyphens."""
    cleaned: list[str] = []
    for token in text.split():
        c = token.strip(".,;:!?\"'()[]{}").lower()
        if c:
            for part in c.split("-"):
                if part:
                    cleaned.append(part)
    return cleaned


def clean_word(word: str) -> str:
    """Strip punctuation from a single word."""
    return word.strip(".,;:!?\"'()[]{}").lower()


# ---------------------------------------------------------------------------
# 1. BibleBookIndexer — per-book word/bigram/trigram/structure indexing
# ---------------------------------------------------------------------------


class BibleBookIndexer:
    """Index Bible data per book: word freq, bigrams, trigrams, structures."""

    def __init__(self) -> None:
        # Per-book storage
        self.word_freq: dict[str, Counter] = defaultdict(Counter)
        self.bigrams: dict[str, Counter] = defaultdict(Counter)
        self.trigrams: dict[str, Counter] = defaultdict(Counter)
        self.sentence_lengths: dict[str, list[int]] = defaultdict(list)
        self.structure_patterns: dict[str, list[str]] = defaultdict(list)
        self.topic_words: dict[str, Counter] = defaultdict(Counter)

        # Global counters
        self.global_freq: Counter = Counter()
        self.total_verses: int = 0
        self.books_seen: set[str] = set()

    def build(self, corpus_path: Path) -> None:
        """Build per-book indexes from parallel corpus."""
        t0 = time.time()
        with open(corpus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                zo = obj.get("zo_tdb77")
                if not zo:
                    continue
                book = obj.get("book", "UNK")
                self.books_seen.add(book)
                self.total_verses += 1

                words = tokenize(zo)
                wc = len(words)
                self.sentence_lengths[book].append(wc)

                # Word frequency
                for w in words:
                    self.word_freq[book][w] += 1
                    self.global_freq[w] += 1

                # Content words for topic extraction (exclude particles)
                for w in words:
                    if w not in PARTICLES and w not in SUBJECT_MARKERS:
                        self.topic_words[book][w] += 1

                # Bigrams
                for i in range(len(words) - 1):
                    bg = (words[i], words[i + 1])
                    self.bigrams[book][bg] += 1

                # Trigrams
                for i in range(len(words) - 2):
                    tg = (words[i], words[i + 1], words[i + 2])
                    self.trigrams[book][tg] += 1

                # Structure pattern
                pat = self._extract_structure(words)
                self.structure_patterns[book].append(pat)

        elapsed = time.time() - t0
        print(
            f"  BibleBookIndexer: {self.total_verses:,} verses, "
            f"{len(self.books_seen)} books ({elapsed:.1f}s)"
        )

    @staticmethod
    def _extract_structure(words: list[str]) -> str:
        """Extract a lightweight structure tag for a sentence."""
        tags: list[str] = []
        for w in words:
            if w in SUBJECT_MARKERS:
                tags.append("SUBJ")
            elif w == "in":
                tags.append("ERG")
            elif w in PARTICLES:
                tags.append("PART")
            elif w in VERB_FINALS:
                tags.append("VERB_END")
            else:
                tags.append("WORD")
        # Collapse consecutive WORD tags
        collapsed: list[str] = []
        for t in tags:
            if t == "WORD" and collapsed and collapsed[-1] == "WORD":
                continue
            collapsed.append(t)
        return "-".join(collapsed)

    def get_top_topic_words(self, book: str, n: int = 30) -> list[tuple[str, int]]:
        """Return top n content words for a book (excluding particles)."""
        return self.topic_words[book].most_common(n)

    def get_bigrams_for_book(
        self, book: str, min_count: int = 1
    ) -> list[tuple[tuple[str, str], int]]:
        """Return bigrams for a book filtered by min_count."""
        return [
            (bg, c)
            for bg, c in self.bigrams[book].most_common()
            if c >= min_count
        ]

    def get_avg_sentence_length(self, book: str) -> float:
        """Average word count per verse in a book."""
        lengths = self.sentence_lengths.get(book, [])
        return sum(lengths) / max(len(lengths), 1)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-able dict."""
        data: dict[str, Any] = {
            "total_verses": self.total_verses,
            "books": sorted(self.books_seen),
            "per_book": {},
        }
        for book in sorted(self.books_seen):
            avg_len = self.get_avg_sentence_length(book)
            # Top 30 topic words
            top_topics = [
                {"word": w, "count": c}
                for w, c in self.get_top_topic_words(book, 30)
            ]
            # Top 100 bigrams
            top_bigrams = [
                {"w1": bg[0], "w2": bg[1], "count": c}
                for bg, c in self.get_bigrams_for_book(book, 100)[:100]
            ]
            # Top 50 trigrams
            top_trigrams = [
                {"w1": tg[0], "w2": tg[1], "w3": tg[2], "count": c}
                for tg, c in self.trigrams[book].most_common(50)
            ]
            # Structure pattern distribution
            pat_dist = Counter(self.structure_patterns[book])
            top_patterns = [
                {"pattern": p, "count": c}
                for p, c in pat_dist.most_common(20)
            ]

            data["per_book"][book] = {
                "verse_count": len(self.sentence_lengths.get(book, [])),
                "avg_sentence_length": round(avg_len, 1),
                "unique_words": len(self.word_freq.get(book, {})),
                "topic_words": top_topics,
                "top_bigrams": top_bigrams,
                "top_trigrams": top_trigrams,
                "structure_patterns": top_patterns,
            }

        # Global stats
        data["global_top_words"] = [
            {"word": w, "count": c}
            for w, c in self.global_freq.most_common(200)
        ]

        return data


# ---------------------------------------------------------------------------
# 2. HyphenRuleEngine — learn hyphenation patterns from Bible
# ---------------------------------------------------------------------------


class HyphenRuleEngine:
    """Learn hyphenation rules from Bible text.

    Tracks all X-Y patterns found in the Bible and builds rules
    about which suffixes legitimately attach to verb stems.
    """

    def __init__(self) -> None:
        self.hyphen_patterns: Counter = Counter()
        self.prefix_suffix_pairs: Counter = Counter()  # (prefix, suffix)
        self.suffix_groups: dict[str, Counter] = defaultdict(Counter)
        self.total_hyphenated: int = 0

    def build(self, corpus_path: Path) -> None:
        """Scan Bible for hyphenated word patterns."""
        t0 = time.time()
        with open(corpus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                zo = obj.get("zo_tdb77")
                if not zo:
                    continue

                for token in zo.split():
                    raw = token.strip(".,;:!?\"'()[]{}").lower()
                    if "-" in raw:
                        parts = raw.split("-")
                        if len(parts) == 2:
                            prefix, suffix = parts
                            self.hyphen_patterns[raw] += 1
                            self.prefix_suffix_pairs[(prefix, suffix)] += 1
                            self.suffix_groups[suffix][prefix] += 1
                            self.total_hyphenated += 1

        elapsed = time.time() - t0
        print(
            f"  HyphenRuleEngine: {self.total_hyphenated:,} hyphenated tokens, "
            f"{len(self.hyphen_patterns):,} unique patterns ({elapsed:.1f}s)"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize rules to JSON-able dict."""
        # Build suffix group summaries
        suffix_summary: dict[str, Any] = {}
        for suffix, prefixes in sorted(self.suffix_groups.items()):
            suffix_summary[suffix] = {
                "count": sum(prefixes.values()),
                "unique_prefixes": len(prefixes),
                "top_prefixes": [
                    {"prefix": p, "count": c}
                    for p, c in prefixes.most_common(20)
                ],
            }

        # Top patterns
        top_patterns = [
            {"pattern": p, "count": c}
            for p, c in self.hyphen_patterns.most_common(200)
        ]

        # Rule set: verb stems that use these suffixes
        verb_stems_by_suffix: dict[str, set[str]] = defaultdict(set)
        for (prefix, suffix), count in self.prefix_suffix_pairs.items():
            if count >= 2:  # Only patterns seen 2+ times
                verb_stems_by_suffix[suffix].add(prefix)

        rules: dict[str, list[str]] = {}
        for suffix, stems in verb_stems_by_suffix.items():
            rules[suffix] = sorted(stems)

        return {
            "total_hyphenated": self.total_hyphenated,
            "unique_patterns": len(self.hyphen_patterns),
            "suffix_groups": suffix_summary,
            "top_patterns": top_patterns,
            "rules": rules,
        }


# ---------------------------------------------------------------------------
# 3. PhraseBank — multi-word expression storage
# ---------------------------------------------------------------------------


class PhraseBank:
    """Store 2-gram and 3-gram phrases with per-book frequency."""

    def __init__(self) -> None:
        self.bigrams_global: Counter = Counter()
        self.trigrams_global: Counter = Counter()
        self.bigrams_per_book: dict[str, Counter] = defaultdict(Counter)
        self.trigrams_per_book: dict[str, Counter] = defaultdict(Counter)
        self.total_verses: int = 0

    def build(self, corpus_path: Path) -> None:
        """Build phrase bank from Bible parallel corpus."""
        t0 = time.time()
        with open(corpus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                zo = obj.get("zo_tdb77")
                if not zo:
                    continue
                book = obj.get("book", "UNK")
                self.total_verses += 1

                words = tokenize(zo)

                # Store as string phrases
                for i in range(len(words) - 1):
                    bg = f"{words[i]} {words[i + 1]}"
                    self.bigrams_global[bg] += 1
                    self.bigrams_per_book[book][bg] += 1

                for i in range(len(words) - 2):
                    tg = f"{words[i]} {words[i + 1]} {words[i + 2]}"
                    self.trigrams_global[tg] += 1
                    self.trigrams_per_book[book][tg] += 1

        elapsed = time.time() - t0
        print(
            f"  PhraseBank: {len(self.bigrams_global):,} unique 2-grams, "
            f"{len(self.trigrams_global):,} unique 3-grams ({elapsed:.1f}s)"
        )

    def lookup_phrase(self, phrase: str) -> dict[str, Any]:
        """Look up a phrase in the bank, returning frequency info."""
        words = phrase.strip().lower().split()
        if len(words) == 2:
            key = f"{words[0]} {words[1]}"
            count = self.bigrams_global.get(key, 0)
            books = {
                b: c
                for b, c in self.bigrams_per_book.items()
                if c.get(key, 0) > 0
            }
            return {"phrase": key, "count": count, "books": books}
        if len(words) == 3:
            key = f"{words[0]} {words[1]} {words[2]}"
            count = self.trigrams_global.get(key, 0)
            books = {
                b: c
                for b, c in self.trigrams_per_book.items()
                if c.get(key, 0) > 0
            }
            return {"phrase": key, "count": count, "books": books}
        # Single word fallback
        return {"phrase": phrase, "count": 0, "books": {}}

    def score_sentence_phrases(
        self, words: list[str], book: str | None = None,
    ) -> tuple[float, list[dict[str, Any]]]:
        """Score how well a sentence's phrases appear in the Bible.

        Returns (score 0-100, list of phrase details).
        """
        if len(words) < 2:
            return 100.0, []

        phrase_scores: list[dict[str, Any]] = []
        total = 0.0

        # Check bigrams
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i + 1]}"
            global_count = self.bigrams_global.get(bg, 0)
            book_count = 0
            if book:
                book_count = self.bigrams_per_book.get(book, {}).get(bg, 0)
            total += 1.0
            if global_count > 0:
                phrase_scores.append({
                    "phrase": bg, "global_count": global_count,
                    "book_count": book_count, "found": True,
                })
            else:
                phrase_scores.append({
                    "phrase": bg, "global_count": 0,
                    "book_count": 0, "found": False,
                })

        found = sum(1 for p in phrase_scores if p["found"])
        score = (found / max(total, 1)) * 100.0
        return score, phrase_scores

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-able dict (top phrases only)."""
        top_bigrams = [
            {"phrase": p, "count": c}
            for p, c in self.bigrams_global.most_common(500)
        ]
        top_trigrams = [
            {"phrase": p, "count": c}
            for p, c in self.trigrams_global.most_common(200)
        ]
        return {
            "total_verses": self.total_verses,
            "unique_bigrams": len(self.bigrams_global),
            "unique_trigrams": len(self.trigrams_global),
            "top_bigrams": top_bigrams,
            "top_trigrams": top_trigrams,
        }


# ---------------------------------------------------------------------------
# 4. ContextValidator — validation API
# ---------------------------------------------------------------------------


class ContextValidator:
    """Validate Zolai sentences against Bible context.

    Uses BibleBookIndexer, HyphenRuleEngine, and PhraseBank to score
    sentences based on real Bible usage patterns.
    """

    def __init__(self, verbose: bool = True) -> None:
        self.book_indexer = BibleBookIndexer()
        self.hyphen_engine = HyphenRuleEngine()
        self.phrase_bank = PhraseBank()
        self.verbose = verbose

        # Loaded data
        self.book_index_data: dict[str, Any] = {}
        self.hyphen_data: dict[str, Any] = {}
        self.vocab_words: set[str] = set()
        self.dict_words: set[str] = set()

    def build_all(self) -> None:
        """Build all indexes from Bible data."""
        if self.verbose:
            print("Building Bible context indexes...")

        self.book_indexer.build(CORPUS_PATH)
        self.hyphen_engine.build(CORPUS_PATH)
        self.phrase_bank.build(CORPUS_PATH)

        # Load vocab for word existence checks
        self._load_vocab()

        if self.verbose:
            print("  Building done.")

    def _load_vocab(self) -> None:
        """Load vocabulary index for word existence checks."""
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
                    count += 1
        if self.verbose:
            print(f"  Vocab loaded: {count:,} words ({time.time()-t0:.1f}s)")

    def save(self) -> None:
        """Save all built indexes to disk."""
        # Book index
        book_data = self.book_indexer.to_dict()
        BOOK_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BOOK_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(book_data, f, ensure_ascii=False, separators=(",", ":"))
        if self.verbose:
            size_kb = BOOK_INDEX_PATH.stat().st_size / 1024
            print(f"  Saved: {BOOK_INDEX_PATH.name} ({size_kb:.0f} KB)")

        # Context usage (phrase bank)
        usage_data = self.phrase_bank.to_dict()
        with open(CONTEXT_USAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, ensure_ascii=False, separators=(",", ":"))
        if self.verbose:
            size_kb = CONTEXT_USAGE_PATH.stat().st_size / 1024
            print(f"  Saved: {CONTEXT_USAGE_PATH.name} ({size_kb:.0f} KB)")

        # Hyphen rules
        hyphen_data = self.hyphen_engine.to_dict()
        with open(HYPHEN_RULES_PATH, "w", encoding="utf-8") as f:
            json.dump(hyphen_data, f, ensure_ascii=False, separators=(",", ":"))
        if self.verbose:
            size_kb = HYPHEN_RULES_PATH.stat().st_size / 1024
            print(f"  Saved: {HYPHEN_RULES_PATH.name} ({size_kb:.0f} KB)")

    def load(self) -> bool:
        """Load pre-built indexes from disk. Returns True if loaded."""
        if not all(p.exists() for p in [
            BOOK_INDEX_PATH, CONTEXT_USAGE_PATH, HYPHEN_RULES_PATH,
        ]):
            return False

        try:
            with open(BOOK_INDEX_PATH, encoding="utf-8") as f:
                self.book_index_data = json.load(f)
            with open(CONTEXT_USAGE_PATH, encoding="utf-8") as f:
                # We keep this as raw data for phrase lookups
                usage = json.load(f)
                self.phrase_bank.bigrams_global = Counter({
                    item["phrase"]: item["count"]
                    for item in usage.get("top_bigrams", [])
                })
                self.phrase_bank.trigrams_global = Counter({
                    item["phrase"]: item["count"]
                    for item in usage.get("top_trigrams", [])
                })
                self.phrase_bank.total_verses = usage.get("total_verses", 0)
            with open(HYPHEN_RULES_PATH, encoding="utf-8") as f:
                self.hyphen_data = json.load(f)
            self._load_vocab()
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    # -- Validation API --

    def validate_word_usage(
        self, word: str, context_words: list[str], book: str | None = None,
    ) -> dict[str, Any]:
        """Check if a word is used in context similar to Bible patterns."""
        w = clean_word(word)
        if w in PARTICLES or w in SUBJECT_MARKERS or w in VERB_FINALS:
            return {"valid": True, "reason": "particle/functional"}

        # Check word exists in vocab
        if w not in self.vocab_words:
            return {"valid": False, "reason": "not_in_bible_vocab"}

        # Check per-book frequency if book is known
        per_book = self.book_index_data.get("per_book", {})
        if book and book in per_book:
            book_info = per_book[book]
            topic_words = {
                item["word"]: item["count"]
                for item in book_info.get("topic_words", [])
            }
            if w in topic_words:
                return {
                    "valid": True,
                    "reason": "topic_word_in_book",
                    "book_count": topic_words[w],
                }

        # Check bigram co-occurrence with context words
        for cw in context_words:
            cw_clean = clean_word(cw)
            bg = f"{w} {cw_clean}"
            bg_rev = f"{cw_clean} {w}"
            if (
                self.phrase_bank.bigrams_global.get(bg, 0) > 0
                or self.phrase_bank.bigrams_global.get(bg_rev, 0) > 0
            ):
                return {"valid": True, "reason": "bigram_attested"}

        return {"valid": True, "reason": "word_exists_in_vocab"}

    def validate_phrase(self, phrase: str) -> dict[str, Any]:
        """Check if a multi-word phrase is attested in the Bible."""
        result = self.phrase_bank.lookup_phrase(phrase)
        return {
            "valid": result["count"] > 0,
            "phrase": result["phrase"],
            "bible_count": result["count"],
            "books_found": len(result.get("books", {})),
        }

    def validate_structure(
        self, tokens: list[str], book: str | None = None,
    ) -> dict[str, Any]:
        """Check if sentence structure matches typical book patterns."""
        # Extract structure from tokens
        tags: list[str] = []
        for w in tokens:
            if w in SUBJECT_MARKERS:
                tags.append("SUBJ")
            elif w == "in":
                tags.append("ERG")
            elif w in PARTICLES:
                tags.append("PART")
            elif w in VERB_FINALS:
                tags.append("VERB_END")
            else:
                tags.append("WORD")
        # Collapse consecutive WORD tags
        collapsed: list[str] = []
        for t in tags:
            if t == "WORD" and collapsed and collapsed[-1] == "WORD":
                continue
            collapsed.append(t)
        pattern = "-".join(collapsed)

        per_book = self.book_index_data.get("per_book", {})

        if book and book in per_book:
            book_patterns = per_book[book].get("structure_patterns", [])
            for bp in book_patterns:
                if bp["pattern"] == pattern:
                    return {
                        "valid": True,
                        "pattern": pattern,
                        "source": "book_match",
                        "book_count": bp["count"],
                    }
            return {
                "valid": True,
                "pattern": pattern,
                "source": "book_no_exact_match",
            }

        # No book specified — check global
        return {"valid": True, "pattern": pattern, "source": "no_book_context"}

    def get_usage_stats(self, word: str) -> dict[str, Any]:
        """Get frequency and usage statistics for a word."""
        w = clean_word(word)
        global_freq = self.book_indexer.global_freq.get(w, 0)

        # Books where it appears
        books_with = []
        per_book = self.book_index_data.get("per_book", {})
        for book_name, book_info in per_book.items():
            tw = {item["word"]: item["count"] for item in book_info.get("topic_words", [])}
            if w in tw:
                books_with.append({"book": book_name, "count": tw[w]})

        # Common neighbors (bigrams)
        neighbors: Counter = Counter()
        for bg_str, count in self.phrase_bank.bigrams_global.items():
            parts = bg_str.split()
            if len(parts) == 2:
                if parts[0] == w:
                    neighbors[parts[1]] += count
                elif parts[1] == w:
                    neighbors[parts[0]] += count

        return {
            "word": w,
            "global_frequency": global_freq,
            "books_found": len(books_with),
            "top_books": sorted(books_with, key=lambda x: -x["count"])[:10],
            "common_neighbors": [
                {"word": nw, "count": nc}
                for nw, nc in neighbors.most_common(15)
            ],
        }

    def score_sentence(
        self, zolai: str, english: str = "", book: str | None = None,
    ) -> dict[str, Any]:
        """Score a sentence using Bible context. Returns 0-100 composite."""
        words = tokenize(zolai)
        if not words:
            return {"score": 0, "reason": "empty"}

        # 1. Word existence (0-30 pts)
        word_score = 30.0
        unknown_count = 0
        for w in words:
            if w in PARTICLES or w in SUBJECT_MARKERS or w in VERB_FINALS:
                continue
            if w not in self.vocab_words:
                # Check hyphen exempt
                if not self._is_hyphen_exempt(w):
                    unknown_count += 1
        word_score -= min(unknown_count * 5, 30)

        # 2. Phrase attestation (0-30 pts)
        phrase_score_val, _phrase_details = self.phrase_bank.score_sentence_phrases(
            words, book,
        )
        phrase_score = (phrase_score_val / 100.0) * 30.0

        # 3. Structure match (0-20 pts)
        structure_result = self.validate_structure(words, book)
        structure_score = 20.0 if structure_result.get("valid") else 10.0

        # 4. Per-book bonus (0-20 pts)
        book_bonus = 0.0
        if book:
            per_book = self.book_index_data.get("per_book", {})
            if book in per_book:
                book_bonus = 15.0  # Known book gets bonus
                # Extra points if words appear in this book's topic words
                topic_words_set = {
                    item["word"]
                    for item in per_book[book].get("topic_words", [])
                }
                content_words = [
                    w for w in words
                    if w not in PARTICLES
                    and w not in SUBJECT_MARKERS
                    and w not in VERB_FINALS
                ]
                if content_words:
                    matches = sum(1 for w in content_words if w in topic_words_set)
                    book_bonus += 5.0 * (matches / len(content_words))

        total = word_score + phrase_score + structure_score + book_bonus
        total = max(0.0, min(100.0, total))

        return {
            "score": round(total, 1),
            "word_score": round(word_score, 1),
            "phrase_score": round(phrase_score, 1),
            "structure_score": round(structure_score, 1),
            "book_bonus": round(book_bonus, 1),
            "unknown_words": unknown_count,
            "phrase_attestation": round(phrase_score_val, 1),
            "structure": structure_result.get("pattern", ""),
        }

    def _is_hyphen_exempt(self, word: str) -> bool:
        """Check if a word is part of a known hyphen pattern."""
        rules = self.hyphen_data.get("rules", {})
        for suffix, stems in rules.items():
            if word in stems:
                return True
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                stem = word[: -len(suffix)]
                if stem in stems:
                    return True
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bible context learner — per-book indexing + validation.",
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Build all indexes from Bible data",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show loaded stats",
    )
    parser.add_argument(
        "--validate", type=str, default="",
        help="Validate a JSONL file of sentences",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=True,
        help="Print progress",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress output",
    )
    args = parser.parse_args()

    verbose = not args.quiet

    if args.build:
        print("=" * 60)
        print("  Building Bible Context Indexes")
        print("=" * 60)
        print()
        cv = ContextValidator(verbose=verbose)
        cv.build_all()
        print()
        cv.save()
        print()
        print("  Done. Indexes saved to data/bible/")
        print()

    elif args.stats:
        cv = ContextValidator(verbose=verbose)
        if not cv.load():
            print("Error: Run --build first to create indexes.")
            sys.exit(1)
        print("=" * 60)
        print("  Bible Context Index Stats")
        print("=" * 60)
        bi = cv.book_index_data
        print(f"  Total verses:     {bi.get('total_verses', 0):,}")
        print(f"  Books indexed:    {len(bi.get('books', []))}")
        print(f"  Global top words: {len(bi.get('global_top_words', []))}")
        print()
        # Show per-book summary
        per_book = bi.get("per_book", {})
        print(f"  {'Book':>5s}  {'Verses':>7s}  {'AvgLen':>6s}  {'Words':>7s}")
        print(f"  {'-'*5}  {'-'*7}  {'-'*6}  {'-'*7}")
        for book_name, info in sorted(per_book.items()):
            print(
                f"  {book_name:>5s}  {info['verse_count']:>7d}  "
                f"{info['avg_sentence_length']:>6.1f}  "
                f"{info['unique_words']:>7d}"
            )
        print()
        # Hyphen stats
        hd = cv.hyphen_data
        print(f"  Hyphen patterns:  {hd.get('unique_patterns', 0):,}")
        print(f"  Hyphenated tokens:{hd.get('total_hyphenated', 0):,}")
        suffix_groups = hd.get("suffix_groups", {})
        for sg, info in sorted(suffix_groups.items(), key=lambda x: -x[1]["count"]):
            print(f"    -{sg}: {info['count']:,} occurrences, "
                  f"{info['unique_prefixes']} unique prefixes")
        print()
        # Phrase bank
        pb = cv.phrase_bank.to_dict()
        print(f"  Unique bigrams:   {pb.get('unique_bigrams', 0):,}")
        print(f"  Unique trigrams:  {pb.get('unique_trigrams', 0):,}")
        print()
        # Sample validation
        print("  Sample word stats:")
        for w in ["pasian", "topa", "gam", "vantung", "tui", "mi"]:
            stats = cv.get_usage_stats(w)
            print(f"    {w}: freq={stats['global_frequency']}, "
                  f"books={stats['books_found']}, "
                  f"neighbors={len(stats['common_neighbors'])}")

    elif args.validate:
        cv = ContextValidator(verbose=verbose)
        if not cv.load():
            print("Error: Run --build first to create indexes.")
            sys.exit(1)
        input_path = Path(args.validate)
        if not input_path.exists():
            print(f"Error: File not found: {input_path}")
            sys.exit(1)
        print(f"Validating sentences from {input_path}...")
        sentences: list[dict[str, str]] = []
        with open(input_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        sentences.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        print(f"  Loaded {len(sentences)} sentences")
        print()
        scores: list[float] = []
        for i, sent in enumerate(sentences[:50]):  # Sample first 50
            zolai = sent.get("zolai", "")
            english = sent.get("english", "")
            result = cv.score_sentence(zolai, english)
            scores.append(result["score"])
            if i < 10:
                print(f"  [{result['score']:5.1f}] {zolai}")
                print(f"         words={result['word_score']:.1f} "
                      f"phrase={result['phrase_score']:.1f} "
                      f"struct={result['structure_score']:.1f} "
                      f"book={result['book_bonus']:.1f}")
        if scores:
            avg = sum(scores) / len(scores)
            print(f"\n  Average score (first {len(scores)}): {avg:.1f}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
