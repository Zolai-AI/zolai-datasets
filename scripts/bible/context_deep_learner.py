#!/usr/bin/env python3
"""Bible Context Deep Learning Engine — per-book/chapter/topic analysis.

Deep per-book, per-chapter, per-topic Bible context analysis.
Exports RAG-ready JSONL files for retrieval-augmented generation.

Data sources (read-only):
  data/bible/parallel_corpus_v1.jsonl       — 31,102 verses
  data/bible/vocab_index_full.jsonl          — 20,929 words
  data/dictionary/processed/dict_zo_en_master_v1.jsonl — 94,885 entries
  data/bible/phrases_v1.jsonl               — 5,000 phrase entries
  data/bible/grammar_patterns_text.jsonl     — 1,188 patterns

Outputs (gitignored):
  data/bible/context/per_book_analysis.jsonl
  data/bible/context/per_chapter_analysis.jsonl
  data/bible/context/word_usage_profiles.jsonl
  data/bible/context/phrase_context_map.jsonl
  data/bible/context/topic_clusters.jsonl
  data/bible/context/sentence_patterns.jsonl

Usage:
    python context_deep_learner.py --build --stats
    python context_deep_learner.py --book GEN
    python context_deep_learner.py --word pasian
    python context_deep_learner.py --topic creation
    python context_deep_learner.py --lookup pasian GEN
    python context_deep_learner.py --chapter GEN.1
    python context_deep_learner.py --export
"""

from __future__ import annotations

import argparse
import json
import re
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
DICT_PATH = (
    WORKSPACE / "data" / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
)
PHRASES_PATH = WORKSPACE / "data" / "bible" / "phrases_v1.jsonl"
GRAMMAR_PATH = WORKSPACE / "data" / "bible" / "grammar_patterns_text.jsonl"

CONTEXT_DIR = WORKSPACE / "data" / "bible" / "context"
PER_BOOK_PATH = CONTEXT_DIR / "per_book_analysis.jsonl"
PER_CHAPTER_PATH = CONTEXT_DIR / "per_chapter_analysis.jsonl"
WORD_PROFILE_PATH = CONTEXT_DIR / "word_usage_profiles.jsonl"
PHRASE_MAP_PATH = CONTEXT_DIR / "phrase_context_map.jsonl"
TOPIC_CLUSTER_PATH = CONTEXT_DIR / "topic_clusters.jsonl"
SENTENCE_PATTERNS_PATH = CONTEXT_DIR / "sentence_patterns.jsonl"

# ---------------------------------------------------------------------------
# Tokenizer (self-contained, copied from bible_context_learner.py)
# ---------------------------------------------------------------------------

# Common Zolai particles and function words
PARTICLES = frozenset({
    "a", "ah", "ahih", "amah", "an", "ang", "aw", "bang", "bawh",
    "cia", "ci", "cu", "cun", "ding", "hiam", "hi", "hoih", "in",
    "kip", "leh", "lo", "lu", "maw", "na", "naw", "ne", "ni", "pa",
    "pen", "pi", "sak", "si", "sung", "tawh", "te", "tui", "tua",
    "tu", "tun", "u", "uh", "un", "van", "va", "zong",
})

# Regex for splitting Zolai text into tokens (words + punctuation)
_TOKEN_RE = re.compile(r"[a-zA-Z\u00C0-\u024F']+[a-zA-Z\u00C0-\u024F]*|[,;:!.?\-]+")

# Negation particles
NEGATION_WORDS = frozenset({"kei", "lo", "si"})
# Question marker
QUESTION_MARKER = "hiam"
# Tense/aspect markers (suffixes or standalone)
TENSE_SUFFIXES = ("-sak", "-nak", "-ah", "-hen", "-ding")
TENSE_STANDALONE = frozenset({"ding", "sak", "nak", "ah", "hen", "lai"})

# Stopwords for content-word extraction
STOPWORDS = frozenset({
    "a", "ah", "ahih", "amah", "an", "ang", "ci", "cu", "cun",
    "hi", "hiam", "in", "leh", "na", "pen", "si", "tawh", "tu",
    "tua", "uh", "un", "le", "te", "ne",
})


def tokenize(text: str) -> list[str]:
    """Tokenize Zolai text into words and punctuation."""
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def content_words(tokens: list[str]) -> list[str]:
    """Extract content words (non-particle, non-stopword)."""
    return [t for t in tokens if t not in PARTICLES and t not in STOPWORDS
            and len(t) > 1 and t[0] not in ",;:!.?"]


def is_verb_final(tokens: list[str]) -> bool:
    """Heuristic: check if sentence is verb-final (SOV)."""
    content = content_words(tokens)
    if len(content) < 2:
        return False
    # Simple heuristic: if last content word is not a particle/preposition
    last = content[-1]
    if last in PARTICLES or last in {"leh", "sung", "tawh", "ah"}:
        return False
    return True


# ---------------------------------------------------------------------------
# Book metadata
# ---------------------------------------------------------------------------

BOOK_NAMES: dict[str, str] = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers",
    "DEU": "Deuteronomy", "JOS": "Joshua", "JUD": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles", "EZR": "Ezra",
    "NEH": "Nehemiah", "EST": "Esther", "JOB": "Job", "PSA": "Psalms",
    "PRO": "Proverbs", "ECC": "Ecclesiastes", "SNG": "Song of Solomon",
    "ISA": "Isaiah", "JER": "Jeremiah", "LAM": "Lamentations",
    "EZK": "Ezekiel", "DAN": "Daniel", "HOS": "Hosea", "JOL": "Joel",
    "AMO": "Amos", "OBA": "Obadiah", "JON": "Jonah", "MIC": "Micah",
    "NAM": "Nahum", "HAB": "Habakkuk", "ZEP": "Zephaniah", "HAG": "Haggai",
    "ZEC": "Zechariah", "MAL": "Malachi", "MAT": "Matthew",
    "MAR": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts",
    "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
    "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians",
    "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians",
    "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus",
    "PHM": "Philemon", "HEB": "Hebrews", "JAS": "James",
    "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John", "2JN": "2 John",
    "3JN": "3 John", "JUD": "Jude", "REV": "Revelation",
}

GENRE_MAP: dict[str, str] = {
    # Law / Narrative
    "GEN": "narrative", "EXO": "law", "LEV": "law", "NUM": "law",
    "DEU": "law", "JOS": "narrative", "JUD": "narrative", "RUT": "narrative",
    "1SA": "narrative", "2SA": "narrative", "1KI": "narrative",
    "2KI": "narrative", "1CH": "narrative", "2CH": "narrative",
    "EZR": "narrative", "NEH": "narrative", "EST": "narrative",
    # Poetry / Wisdom
    "JOB": "poetry", "PSA": "poetry", "PRO": "wisdom",
    "ECC": "wisdom", "SNG": "poetry",
    # Prophecy
    "ISA": "prophecy", "JER": "prophecy", "LAM": "prophecy",
    "EZK": "prophecy", "DAN": "prophecy", "HOS": "prophecy",
    "JOL": "prophecy", "AMO": "prophecy", "OBA": "prophecy",
    "JON": "prophecy", "MIC": "prophecy", "NAM": "prophecy",
    "HAB": "prophecy", "ZEP": "prophecy", "HAG": "prophecy",
    "ZEC": "prophecy", "MAL": "prophecy",
    # Gospels
    "MAT": "gospel", "MAR": "gospel", "LUK": "gospel", "JHN": "gospel",
    # Epistles
    "ACT": "narrative", "ROM": "epistle", "1CO": "epistle", "2CO": "epistle",
    "GAL": "epistle", "EPH": "epistle", "PHP": "epistle", "COL": "epistle",
    "1TH": "epistle", "2TH": "epistle", "1TI": "epistle", "2TI": "epistle",
    "TIT": "epistle", "PHM": "epistle", "HEB": "epistle", "JAS": "epistle",
    "1PE": "epistle", "2PE": "epistle", "1JN": "epistle", "2JN": "epistle",
    "3JN": "epistle", "JUD": "epistle", "REV": "prophecy",
}

# Canonical book order
BOOK_ORDER = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JUD", "RUT",
    "1SA", "2SA", "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST",
    "JOB", "PSA", "PRO", "ECC", "SNG",
    "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA",
    "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MAR", "LUK", "JHN", "ACT",
    "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
    "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

# Topic keyword dictionaries (Zolai words → topic)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "creation": ["piangsak", "bawl", "lebung", "tui", "khuavak", "mual",
                 "sing", "mi", "vantung", "khuamial", "khuazong"],
    "law": ["thuchun", "thuzat", "thuben", "theih", "that", "tua",
            "tun", "sak", "ze"],
    "history": ["gam", "lung", "ciang", "kip", "khuam", "khang",
                "ta", "te", "nuntak", "ci"],
    "praise": ["thupha", "lungdam", "sanggam", "gam", "song",
               "maan", "awn", "hong"],
    "prophecy": ["sim", "nuntlang", "thusim", "hong", "ding",
                 "nuntak", "khang", "piang"],
    "wisdom": ["sang", "thei", "hoih", "zong", "nuntakna",
               "thusei", "lai", "pa"],
    "love": ["hoih", "sang", "kip", "nuam", "nun", "pian",
             "na", "tawh"],
    "war": ["kham", "thuam", "pa", "sak", "piang", "dam",
            "khang", "cuak", "suak"],
    "exile": ["kip", "va", "cia", "suahtak", "nuntak", "si",
              "kuat", "khuat"],
    "redemption": ["puak", "sak", "thei", "zat", "piang",
                   "kuat", "khuat", "thupha"],
    "miracle": ["si", "bawl", "piang", "sang", "kuat",
                "khuat", "piangsak", "tengah"],
    "teaching": ["sim", "that", "ci", "leh", "thei",
                 "sang", "nuntakna", "lai"],
}


# ---------------------------------------------------------------------------
# Class 1: PerBookAnalyzer
# ---------------------------------------------------------------------------

class PerBookAnalyzer:
    """Analyze each Bible book: verse count, unique words, genre, top words."""

    def __init__(self, corpus: list[dict[str, Any]],
                 vocab_lookup: dict[str, dict[str, Any]]) -> None:
        self.corpus = corpus
        self.vocab_lookup = vocab_lookup
        self.book_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Pre-built global index: word → set of books that contain it
        self._word_books: dict[str, set[str]] = defaultdict(set)
        # Pre-built: word → set of verses (by index) containing it
        self._word_verse_idx: dict[str, set[int]] = defaultdict(set)
        self._index()

    def _index(self) -> None:
        """Group verses by book and build global word indexes."""
        for idx, verse in enumerate(self.corpus):
            book = verse.get("book", "")
            if book:
                self.book_data[book].append(verse)
            # Build global word→book and word→verse indexes
            zo = (verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "")
            for w in content_words(tokenize(zo)):
                self._word_books[w].add(book)
                self._word_verse_idx[w].add(idx)

    def analyze_book(self, book: str) -> dict[str, Any]:
        """Full analysis for a single book."""
        verses = self.book_data.get(book, [])
        if not verses:
            return {"book": book, "error": "no verses found"}

        all_tokens: list[str] = []
        word_counter: Counter[str] = Counter()
        sentence_lengths: list[int] = []

        for v in verses:
            zo = (v.get("zo_tdb77") or v.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            all_tokens.extend(tokens)
            cw = content_words(tokens)
            word_counter.update(cw)
            sentence_lengths.append(len(tokens))

        unique_words = set(all_tokens)
        total_tokens = len(all_tokens)

        # Top-20 content words
        top_words = [
            {"word": w, "count": c}
            for w, c in word_counter.most_common(20)
        ]

        # Book-specific words: ≥5 verses in this book, ≤1 verse in all others
        book_specific = self._find_book_specific(book, word_counter)

        avg_len = (
            round(sum(sentence_lengths) / len(sentence_lengths), 2)
            if sentence_lengths else 0
        )

        genre = GENRE_MAP.get(book, "unknown")
        book_name = BOOK_NAMES.get(book, book)

        return {
            "book": book,
            "book_name": book_name,
            "genre": genre,
            "verse_count": len(verses),
            "unique_words": len(unique_words),
            "total_tokens": total_tokens,
            "avg_sentence_length": avg_len,
            "top_words": top_words,
            "book_specific_words": book_specific[:30],
        }

    def _find_book_specific(self, book: str,
                            word_counter: Counter[str]) -> list[str]:
        """Find words that appear in ≥5 verses of this book
        but ≤1 verse in all other books combined."""
        book_verses = self.book_data.get(book, [])
        if len(book_verses) < 5:
            return []

        # Pre-build verse word sets for this book (fast: only this book)
        verse_word_sets: list[set[str]] = []
        for v in book_verses:
            zo = (v.get("zo_tdb77") or v.get("zo_tedim2010") or "")
            verse_word_sets.append(set(content_words(tokenize(zo))))

        # Candidate words: ≥5 verses in this book
        candidate_words: set[str] = set()
        for w in word_counter:
            count = sum(1 for vs in verse_word_sets if w in vs)
            if count >= 5:
                candidate_words.add(w)

        # Use pre-built global index to count other-book verses (O(1) per word)
        book_v_idx = {idx for idx, v in enumerate(self.corpus)
                      if v.get("book") == book}
        specific: list[str] = []
        for w in candidate_words:
            # All verses containing w
            all_verses_w = self._word_verse_idx.get(w, set())
            # Verses in other books containing w
            other_count = len(all_verses_w - book_v_idx)
            if other_count <= 1:
                specific.append(w)

        return sorted(specific, key=lambda x: word_counter[x], reverse=True)

    def analyze_all(self) -> list[dict[str, Any]]:
        """Analyze all books in canonical order."""
        results = []
        for book in BOOK_ORDER:
            if book in self.book_data:
                results.append(self.analyze_book(book))
        return results


# ---------------------------------------------------------------------------
# Class 2: PerChapterAnalyzer
# ---------------------------------------------------------------------------

class PerChapterAnalyzer:
    """Analyze each chapter: word usage, sentence structures, topic words."""

    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self.chapter_data: dict[str, dict[str, list[dict[str, Any]]]] = (
            defaultdict(lambda: defaultdict(list))
        )
        self._index()

    def _index(self) -> None:
        """Group verses by book → chapter."""
        for verse in self.corpus:
            book = verse.get("book", "")
            chapter = verse.get("chapter", "")
            if book and chapter:
                self.chapter_data[book][chapter].append(verse)

    def analyze_chapter(self, book: str, chapter: str) -> dict[str, Any]:
        """Full analysis for a single chapter."""
        verses = self.chapter_data.get(book, {}).get(chapter, [])
        if not verses:
            return {"book": book, "chapter": chapter, "error": "no verses found"}

        word_counter: Counter[str] = Counter()
        sentence_lengths: list[int] = []

        for v in verses:
            zo = (v.get("zo_tdb77") or v.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            sentence_lengths.append(len(tokens))
            cw = content_words(tokens)
            word_counter.update(cw)

        # Top-10 topic words
        topic_words = [
            {"word": w, "count": c}
            for w, c in word_counter.most_common(10)
        ]

        avg_len = (
            round(sum(sentence_lengths) / len(sentence_lengths), 2)
            if sentence_lengths else 0
        )

        return {
            "book": book,
            "chapter": chapter,
            "verse_count": len(verses),
            "unique_words": len(word_counter),
            "avg_length": avg_len,
            "top_words": topic_words,
            "theme_words": topic_words[:5],
        }

    def analyze_all(self) -> list[dict[str, Any]]:
        """Analyze all chapters in canonical order."""
        results = []
        for book in BOOK_ORDER:
            if book in self.chapter_data:
                for chapter in sorted(self.chapter_data[book].keys(),
                                      key=lambda x: int(x) if x.isdigit() else 0):
                    results.append(self.analyze_chapter(book, chapter))
        return results

    def get_chapters(self, book: str) -> dict[str, list[dict[str, Any]]]:
        """Return all chapters for a book."""
        return dict(self.chapter_data.get(book, {}))


# ---------------------------------------------------------------------------
# Class 3: TopicClusterer
# ---------------------------------------------------------------------------

class TopicClusterer:
    """Cluster verses/chapters into semantic topics via keyword matching."""

    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self.topic_results: dict[str, dict[str, Any]] = {}

    def score_verse(self, tokens: list[str],
                    topic: str) -> float:
        """Score a verse against a topic (0.0 – 1.0)."""
        keywords = TOPIC_KEYWORDS.get(topic, [])
        if not keywords:
            return 0.0
        word_set = set(tokens)
        matched = sum(1 for kw in keywords if kw in word_set)
        return matched / len(keywords) if keywords else 0.0

    def cluster_all(self) -> dict[str, dict[str, Any]]:
        """Score every verse against every topic, build clusters."""
        topic_scores: dict[str, list[tuple[float, dict[str, Any]]]] = (
            defaultdict(list)
        )
        topic_word_counts: dict[str, Counter[str]] = {
            t: Counter() for t in TOPIC_KEYWORDS
        }
        topic_chapters: dict[str, set[str]] = {
            t: set() for t in TOPIC_KEYWORDS
        }
        topic_examples: dict[str, list[dict[str, str]]] = {
            t: [] for t in TOPIC_KEYWORDS
        }

        for verse in self.corpus:
            zo = (verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            cw = content_words(tokens)
            book = verse.get("book", "")
            chapter = f"{book}.{verse.get('chapter', '')}"

            best_topic = None
            best_score = 0.0

            for topic in TOPIC_KEYWORDS:
                score = self.score_verse(tokens, topic)
                if score > 0:
                    topic_scores[topic].append((score, verse))
                    topic_word_counts[topic].update(cw)
                    topic_chapters[topic].add(chapter)
                if score > best_score:
                    best_score = score
                    best_topic = topic

            # Assign verse to best topic if score > 0
            if best_topic and best_score > 0:
                en = (verse.get("en_kJV") or "")[:80]
                if len(topic_examples[best_topic]) < 5:
                    topic_examples[best_topic].append({
                        "ref": verse.get("ref", ""),
                        "zo": zo[:80],
                        "en": en,
                    })

        # Build final clusters
        self.topic_results = {}
        for topic in TOPIC_KEYWORDS:
            scored = topic_scores[topic]
            top_words = [
                {"word": w, "count": c}
                for w, c in topic_word_counts[topic].most_common(15)
            ]
            self.topic_results[topic] = {
                "topic": topic,
                "keyword_match_count": len(scored),
                "characteristic_words": top_words,
                "chapters": sorted(topic_chapters[topic]),
                "chapter_count": len(topic_chapters[topic]),
                "usage_examples": topic_examples[topic],
            }

        return self.topic_results

    def get_topic(self, topic: str) -> dict[str, Any] | None:
        """Get details for a specific topic."""
        return self.topic_results.get(topic)


# ---------------------------------------------------------------------------
# Class 4: WordUsageProfiler
# ---------------------------------------------------------------------------

class WordUsageProfiler:
    """Profile each word: per-book frequency, translations, co-occurring words."""

    def __init__(self, corpus: list[dict[str, Any]],
                 dict_entries: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self.dict_entries = dict_entries
        # Build translation lookup: zolai → [english]
        self.translation_map: dict[str, list[str]] = defaultdict(list)
        self._build_dict_index()

        # Per-book word frequency
        self.book_word_freq: dict[str, Counter[str]] = defaultdict(Counter)
        # Per-book word → translations seen
        self.book_translations: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        # Per-book co-occurrence (top-10 per word only to limit memory)
        self.book_cooccurrence: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter)
        )
        self._index_corpus()

    def _build_dict_index(self) -> None:
        """Build zolai → english translation lookup."""
        for entry in self.dict_entries:
            zolai = (entry.get("zolai", "") or "").strip().lower()
            english = entry.get("english", "")
            if zolai and english:
                if isinstance(english, list):
                    self.translation_map[zolai].extend(
                        [e.strip() for e in english if e.strip()]
                    )
                elif isinstance(english, str):
                    self.translation_map[zolai].append(english.strip())

    def _index_corpus(self) -> None:
        """Build per-book word frequency and co-occurrence."""
        for verse in self.corpus:
            book = verse.get("book", "")
            zo = (verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            cw = content_words(tokens)

            self.book_word_freq[book].update(cw)

            # Co-occurrence: limit to top-10 unique content words per verse
            unique_cw = list(set(cw))[:10]
            for w in unique_cw:
                for other in unique_cw:
                    if other != w:
                        self.book_cooccurrence[book][w][other] += 1

            # Track translations per book per word
            for w in unique_cw:
                if w in self.translation_map:
                    for t in self.translation_map[w]:
                        self.book_translations[book][w].add(t)

    def profile_word(self, word: str) -> dict[str, Any]:
        """Build full usage profile for a word."""
        word_lower = word.lower()
        total_freq = sum(
            self.book_word_freq[b].get(word_lower, 0)
            for b in self.book_word_freq
        )
        books_found = sorted([
            b for b in self.book_word_freq
            if word_lower in self.book_word_freq[b]
        ])

        per_book: list[dict[str, Any]] = []
        all_translations: set[str] = set()
        for book in books_found:
            freq = self.book_word_freq[book][word_lower]
            trans = self.book_translations[book].get(word_lower, set())
            all_translations.update(trans)

            # Top co-occurring words in this book
            co = self.book_cooccurrence[book].get(word_lower, Counter())
            top_co = [{"word": w, "count": c} for w, c in co.most_common(5)]

            per_book.append({
                "book": book,
                "book_name": BOOK_NAMES.get(book, book),
                "frequency": freq,
                "top_translations": sorted(trans)[:5],
                "co_occurring_words": top_co,
            })

        # Meaning-shift detection: top translation differs across ≥2 books
        meaning_shifts = self._detect_meaning_shifts(word_lower, books_found)

        return {
            "word": word_lower,
            "total_freq": total_freq,
            "books_found": len(books_found),
            "per_book_distribution": per_book,
            "meaning_shifts": meaning_shifts,
            "all_translations": sorted(all_translations)[:20],
        }

    def _detect_meaning_shifts(self, word: str,
                               books: list[str]) -> list[dict[str, Any]]:
        """Detect if top translation differs across books."""
        book_top_trans: dict[str, str | None] = {}
        for book in books:
            trans = self.book_translations[book].get(word, set())
            if trans:
                # Pick most frequent translation (by book frequency heuristic)
                book_top_trans[book] = sorted(trans)[0]
            else:
                book_top_trans[book] = None

        # Group by top translation
        trans_groups: dict[str | None, list[str]] = defaultdict(list)
        for book, t in book_top_trans.items():
            trans_groups[t].append(book)

        shifts: list[dict[str, Any]] = []
        if len(trans_groups) > 1:
            for trans, bk_list in trans_groups.items():
                if trans is not None:
                    shifts.append({
                        "translation": trans,
                        "books": bk_list,
                    })

        return shifts

    def profile_all(self) -> list[dict[str, Any]]:
        """Profile all words found in the corpus."""
        all_words: set[str] = set()
        for book, counter in self.book_word_freq.items():
            all_words.update(counter.keys())

        results = []
        for word in sorted(all_words):
            profile = self.profile_word(word)
            if profile["total_freq"] >= 3:  # Min frequency threshold
                results.append(profile)
        return results


# ---------------------------------------------------------------------------
# Class 5: PhraseContextMapper
# ---------------------------------------------------------------------------

class PhraseContextMapper:
    """Extract bigrams/trigrams, map phrase contexts, detect idioms."""

    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self.bigram_freq: Counter[tuple[str, str]] = Counter()
        self.trigram_freq: Counter[tuple[str, str, str]] = Counter()
        self.bigram_locations: dict[tuple[str, str], list[dict[str, str]]] = (
            defaultdict(list)
        )
        self.trigram_locations: dict[
            tuple[str, str, str], list[dict[str, str]]
        ] = defaultdict(list)
        # Pre-computed context words for each phrase
        self.bigram_context: dict[tuple[str, str], Counter[str]] = defaultdict(
            Counter
        )
        self.trigram_context: dict[
            tuple[str, str, str], Counter[str]
        ] = defaultdict(Counter)
        self.word_freq: Counter[str] = Counter()
        self._index()

    def _index(self) -> None:
        """Extract all bigrams and trigrams from corpus."""
        for verse in self.corpus:
            zo = (verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            cw = content_words(tokens)
            ref = verse.get("ref", "")
            book = verse.get("book", "")

            for w in cw:
                self.word_freq[w] += 1

            # Bigrams
            for i in range(len(cw) - 1):
                bg = (cw[i], cw[i + 1])
                self.bigram_freq[bg] += 1
                if len(self.bigram_locations[bg]) < 10:
                    self.bigram_locations[bg].append({
                        "ref": ref,
                        "book": book,
                        "context": zo[:100],
                    })
                # Pre-compute surrounding context words
                if i > 0:
                    self.bigram_context[bg][cw[i - 1]] += 1
                if i + 2 < len(cw):
                    self.bigram_context[bg][cw[i + 2]] += 1

            # Trigrams
            for i in range(len(cw) - 2):
                tg = (cw[i], cw[i + 1], cw[i + 2])
                self.trigram_freq[tg] += 1
                if len(self.trigram_locations[tg]) < 10:
                    self.trigram_locations[tg].append({
                        "ref": ref,
                        "book": book,
                        "context": zo[:100],
                    })
                # Pre-compute surrounding context words
                if i > 0:
                    self.trigram_context[tg][cw[i - 1]] += 1
                if i + 3 < len(cw):
                    self.trigram_context[tg][cw[i + 3]] += 1

    def get_phrases(self, min_freq: int = 3) -> list[dict[str, Any]]:
        """Get all phrases appearing ≥min_freq times."""
        results = []

        # Bigrams
        for bg, freq in self.bigram_freq.most_common():
            if freq < min_freq:
                break
            phrase = f"{bg[0]} {bg[1]}"
            is_idiomatic = self._is_idiomatic(bg[0], bg[1], freq)
            ctx = self.bigram_context.get(bg, Counter())
            results.append({
                "phrase": phrase,
                "type": "bigram",
                "frequency": freq,
                "locations": self.bigram_locations[bg][:5],
                "context_words": [w for w, _ in ctx.most_common(5)],
                "is_idiomatic": is_idiomatic,
            })

        # Trigrams
        for tg, freq in self.trigram_freq.most_common():
            if freq < min_freq:
                break
            phrase = f"{tg[0]} {tg[1]} {tg[2]}"
            is_idiomatic = self._is_idiomatic_trigram(tg, freq)
            ctx = self.trigram_context.get(tg, Counter())
            results.append({
                "phrase": phrase,
                "type": "trigram",
                "frequency": freq,
                "locations": self.trigram_locations[tg][:5],
                "context_words": [w for w, _ in ctx.most_common(5)],
                "is_idiomatic": is_idiomatic,
            })

        return results

    def _is_idiomatic(self, w1: str, w2: str, phrase_freq: int) -> bool:
        """Check if bigram is idiomatic: freq / (w1_freq * w2_freq) > threshold."""
        f1 = self.word_freq.get(w1, 1)
        f2 = self.word_freq.get(w2, 1)
        pmi = phrase_freq / (f1 * f2)
        return pmi > 0.001

    def _is_idiomatic_trigram(self, tg: tuple[str, str, str],
                              phrase_freq: int) -> bool:
        """Check if trigram is idiomatic."""
        f1 = self.word_freq.get(tg[0], 1)
        f2 = self.word_freq.get(tg[1], 1)
        f3 = self.word_freq.get(tg[2], 1)
        pmi = phrase_freq / (f1 * f2 * f3)
        return pmi > 0.0001


# ---------------------------------------------------------------------------
# Class 6: SentencePatternAnalyzer
# ---------------------------------------------------------------------------

class SentencePatternAnalyzer:
    """Per-book grammar fingerprint: SOV rate, negation, question, tense."""

    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus
        self.book_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._index()

    def _index(self) -> None:
        """Group verses by book."""
        for verse in self.corpus:
            book = verse.get("book", "")
            if book:
                self.book_data[book].append(verse)

    def analyze_book(self, book: str) -> dict[str, Any]:
        """Analyze grammar patterns for a single book."""
        verses = self.book_data.get(book, [])
        if not verses:
            return {"book": book, "error": "no verses found"}

        total = len(verses)
        sov_count = 0
        negation_count = 0
        question_count = 0
        tense_dist: Counter[str] = Counter()
        lengths: list[int] = []

        for v in verses:
            zo = (v.get("zo_tdb77") or v.get("zo_tedim2010") or "")
            tokens = tokenize(zo)
            lengths.append(len(tokens))

            # SOV check
            if is_verb_final(tokens):
                sov_count += 1

            # Negation check
            if any(t in NEGATION_WORDS for t in tokens):
                negation_count += 1

            # Question marker check
            if QUESTION_MARKER in tokens:
                question_count += 1

            # Tense/aspect markers
            for token in tokens:
                for suffix in TENSE_SUFFIXES:
                    if token.endswith(suffix) and len(token) > len(suffix):
                        tense_dist[f"*-{suffix}"] += 1
                        break
                if token in TENSE_STANDALONE:
                    tense_dist[token] += 1

        avg_length = round(sum(lengths) / total, 2) if lengths else 0

        return {
            "book": book,
            "book_name": BOOK_NAMES.get(book, book),
            "genre": GENRE_MAP.get(book, "unknown"),
            "verse_count": total,
            "sov_rate": round(sov_count / total, 3),
            "negation_rate": round(negation_count / total, 3),
            "question_rate": round(question_count / total, 3),
            "tense_distribution": dict(tense_dist.most_common(15)),
            "avg_complexity": avg_length,
        }

    def analyze_all(self) -> list[dict[str, Any]]:
        """Analyze all books in canonical order."""
        results = []
        for book in BOOK_ORDER:
            if book in self.book_data:
                results.append(self.analyze_book(book))
        return results


# ---------------------------------------------------------------------------
# Class 7: ContextDeepLearner (orchestrator)
# ---------------------------------------------------------------------------

class ContextDeepLearner:
    """Orchestrator: loads data, runs all analyzers, exports JSONL."""

    def __init__(self) -> None:
        self.corpus: list[dict[str, Any]] = []
        self.vocab: list[dict[str, Any]] = []
        self.dict_entries: list[dict[str, Any]] = []
        self.phrases: list[dict[str, Any]] = []
        self.grammar_patterns: list[dict[str, Any]] = []

        # Analyzers (initialized after data load)
        self.book_analyzer: PerBookAnalyzer | None = None
        self.chapter_analyzer: PerChapterAnalyzer | None = None
        self.topic_clusterer: TopicClusterer | None = None
        self.word_profiler: WordUsageProfiler | None = None
        self.phrase_mapper: PhraseContextMapper | None = None
        self.pattern_analyzer: SentencePatternAnalyzer | None = None

    def load_data(self) -> None:
        """Load all data files."""
        print("Loading corpus...")
        self.corpus = self._load_jsonl(CORPUS_PATH)
        print(f"  {len(self.corpus):,} verses loaded")

        print("Loading vocabulary...")
        self.vocab = self._load_jsonl(VOCAB_PATH)
        print(f"  {len(self.vocab):,} words loaded")

        print("Loading dictionary...")
        self.dict_entries = self._load_jsonl(DICT_PATH)
        print(f"  {len(self.dict_entries):,} entries loaded")

        if PHRASES_PATH.exists():
            print("Loading phrases...")
            self.phrases = self._load_jsonl(PHRASES_PATH)
            print(f"  {len(self.phrases):,} phrases loaded")

        if GRAMMAR_PATH.exists():
            print("Loading grammar patterns...")
            self.grammar_patterns = self._load_jsonl(GRAMMAR_PATH)
            print(f"  {len(self.grammar_patterns):,} patterns loaded")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """Load a JSONL file."""
        results = []
        if not path.exists():
            print(f"  Warning: {path.name} not found")
            return results
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return results

    def init_analyzers(self) -> None:
        """Initialize all analyzers with loaded data."""
        # Build vocab lookup
        vocab_lookup: dict[str, dict[str, Any]] = {}
        for v in self.vocab:
            w = v.get("word", "")
            if w:
                vocab_lookup[w] = v

        print("Initializing analyzers...")
        self.book_analyzer = PerBookAnalyzer(self.corpus, vocab_lookup)
        self.chapter_analyzer = PerChapterAnalyzer(self.corpus)
        self.topic_clusterer = TopicClusterer(self.corpus)
        self.word_profiler = WordUsageProfiler(self.corpus, self.dict_entries)
        self.phrase_mapper = PhraseContextMapper(self.corpus)
        self.pattern_analyzer = SentencePatternAnalyzer(self.corpus)
        print("  All analyzers ready")

    def build_all(self) -> None:
        """Run all analysis and export to JSONL."""
        t0 = time.time()
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Per-book analysis
        print("\n[1/6] Analyzing per-book...")
        book_results = self.book_analyzer.analyze_all()  # type: ignore[union-attr]
        self._export_jsonl(PER_BOOK_PATH, book_results)
        print(f"  → {len(book_results)} books analyzed")

        # 2. Per-chapter analysis
        print("[2/6] Analyzing per-chapter...")
        chapter_results = self.chapter_analyzer.analyze_all()  # type: ignore[union-attr]
        self._export_jsonl(PER_CHAPTER_PATH, chapter_results)
        print(f"  → {len(chapter_results)} chapters analyzed")

        # 3. Topic clustering
        print("[3/6] Clustering topics...")
        topic_results = self.topic_clusterer.cluster_all()  # type: ignore[union-attr]
        topic_list = list(topic_results.values())
        self._export_jsonl(TOPIC_CLUSTER_PATH, topic_list)
        print(f"  → {len(topic_list)} topics clustered")

        # 4. Word usage profiles
        print("[4/6] Profiling word usage...")
        word_results = self.word_profiler.profile_all()  # type: ignore[union-attr]
        self._export_jsonl(WORD_PROFILE_PATH, word_results)
        print(f"  → {len(word_results)} words profiled")

        # 5. Phrase context map
        print("[5/6] Mapping phrase contexts...")
        phrase_results = self.phrase_mapper.get_phrases(min_freq=3)  # type: ignore[union-attr]
        self._export_jsonl(PHRASE_MAP_PATH, phrase_results)
        print(f"  → {len(phrase_results)} phrases mapped")

        # 6. Sentence patterns
        print("[6/6] Analyzing sentence patterns...")
        pattern_results = self.pattern_analyzer.analyze_all()  # type: ignore[union-attr]
        self._export_jsonl(SENTENCE_PATTERNS_PATH, pattern_results)
        print(f"  → {len(pattern_results)} book patterns analyzed")

        elapsed = time.time() - t0
        print(f"\n✅ Build complete in {elapsed:.1f}s")
        print(f"Output: {CONTEXT_DIR}/")

    def print_stats(self) -> None:
        """Print summary statistics."""
        print("\n" + "=" * 60)
        print("  BIBLE CONTEXT DEEP LEARNING — Summary Statistics")
        print("=" * 60)

        for path, label in [
            (PER_BOOK_PATH, "Per-book analysis"),
            (PER_CHAPTER_PATH, "Per-chapter analysis"),
            (WORD_PROFILE_PATH, "Word usage profiles"),
            (PHRASE_MAP_PATH, "Phrase context map"),
            (TOPIC_CLUSTER_PATH, "Topic clusters"),
            (SENTENCE_PATTERNS_PATH, "Sentence patterns"),
        ]:
            if path.exists():
                count = sum(1 for _ in open(path, encoding="utf-8"))
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  {label:30s}  {count:>6,} records  {size_mb:.1f} MB")
            else:
                print(f"  {label:30s}  {'(not built)':>18s}")

        print(f"\n  Corpus:          {len(self.corpus):>10,} verses")
        print(f"  Vocabulary:      {len(self.vocab):>10,} words")
        print(f"  Dictionary:      {len(self.dict_entries):>10,} entries")
        print(f"  Topics:          {len(TOPIC_KEYWORDS):>10}")
        print("=" * 60)

    def _export_jsonl(self, path: Path, data: list[dict[str, Any]]) -> None:
        """Export data to JSONL file."""
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in data)

    def lookup(self, word: str, book: str) -> dict[str, Any]:
        """Context lookup: word meaning in a specific book."""
        word_lower = word.lower()
        book_upper = book.upper()

        # Get word profile
        profile = self.word_profiler.profile_word(word_lower)  # type: ignore[union-attr]

        # Get book-specific distribution
        book_dist = None
        for bd in profile.get("per_book_distribution", []):
            if bd.get("book") == book_upper:
                book_dist = bd
                break

        # Get top co-occurring words in this book
        co_occurring = book_dist.get("co_occurring_words", []) if book_dist else []

        # Get translations
        translations = book_dist.get("top_translations", []) if book_dist else []

        # Get topic associations
        topic_matches: list[str] = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if word_lower in keywords:
                topic_matches.append(topic)

        return {
            "word": word_lower,
            "book": book_upper,
            "book_name": BOOK_NAMES.get(book_upper, book_upper),
            "frequency_in_book": (
                book_dist.get("frequency", 0) if book_dist else 0
            ),
            "total_frequency": profile.get("total_freq", 0),
            "translations": translations,
            "co_occurring_words": co_occurring,
            "topic_associations": topic_matches,
            "meaning_shifts": profile.get("meaning_shifts", []),
            "books_found_in": profile.get("books_found", 0),
        }

    def analyze_book(self, book: str) -> dict[str, Any] | None:
        """Get full analysis for a specific book."""
        if self.book_analyzer is None:
            return None
        return self.book_analyzer.analyze_book(book.upper())

    def analyze_chapter(self, ref: str) -> dict[str, Any] | None:
        """Get analysis for a specific chapter (e.g. 'GEN.1')."""
        parts = ref.upper().split(".")
        if len(parts) != 2:
            return None
        book, chapter = parts
        if self.chapter_analyzer is None:
            return None
        return self.chapter_analyzer.analyze_chapter(book, chapter)

    def get_topic(self, topic: str) -> dict[str, Any] | None:
        """Get topic cluster details."""
        if self.topic_clusterer is None:
            return None
        return self.topic_clusterer.get_topic(topic.lower())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Bible Context Deep Learning Engine"
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Build all context indexes and export JSONL files"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print summary statistics"
    )
    parser.add_argument(
        "--book", type=str, default=None,
        help="Analyze specific book(s), comma-separated (e.g. GEN,EXO)"
    )
    parser.add_argument(
        "--chapter", type=str, default=None,
        help="Analyze specific chapter (e.g. GEN.1)"
    )
    parser.add_argument(
        "--word", type=str, default=None,
        help="Show usage profile for a word"
    )
    parser.add_argument(
        "--topic", type=str, default=None,
        help="Show topic cluster details (e.g. creation)"
    )
    parser.add_argument(
        "--lookup", nargs=2, metavar=("WORD", "BOOK"),
        help="Context lookup: word in book (e.g. pasian GEN)"
    )
    parser.add_argument(
        "--export", action="store_true",
        help="Export all JSONL files to data/bible/context/"
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    learner = ContextDeepLearner()
    learner.load_data()

    # Default: build + stats if no specific action
    if not any([args.build, args.stats, args.book, args.chapter,
                args.word, args.topic, args.lookup, args.export]):
        args.build = True
        args.stats = True

    if args.build or args.export:
        learner.init_analyzers()
        learner.build_all()

    if args.stats:
        if learner.book_analyzer is None:
            learner.init_analyzers()
        learner.print_stats()

    if args.book:
        if learner.book_analyzer is None:
            learner.init_analyzers()
        books = [b.strip().upper() for b in args.book.split(",")]
        for book in books:
            result = learner.analyze_book(book)
            if result:
                print(f"\n{'=' * 60}")
                print(f"  {result.get('book_name', book)} "
                      f"({result.get('genre', 'unknown')})")
                print(f"{'=' * 60}")
                print(f"  Verses:             {result.get('verse_count', 0)}")
                print(f"  Unique words:       {result.get('unique_words', 0)}")
                print(f"  Avg sentence length: {result.get('avg_sentence_length', 0)}")
                print("\n  Top 20 content words:")
                for i, tw in enumerate(result.get("top_words", [])[:20], 1):
                    print(f"    {i:2d}. {tw['word']:20s}  ({tw['count']})")
                if result.get("book_specific_words"):
                    print("\n  Book-specific words "
                          "(≥5 verses, ≤1 in other books):")
                    for w in result["book_specific_words"][:15]:
                        print(f"    • {w}")
            else:
                print(f"\n❌ Book '{book}' not found in corpus")

    if args.chapter:
        if learner.chapter_analyzer is None:
            learner.init_analyzers()
        result = learner.analyze_chapter(args.chapter)
        if result and "error" not in result:
            print(f"\n{'=' * 60}")
            print(f"  {result['book']} Chapter {result['chapter']}")
            print(f"{'=' * 60}")
            print(f"  Verses:          {result['verse_count']}")
            print(f"  Unique words:    {result['unique_words']}")
            print(f"  Avg length:      {result['avg_length']}")
            print("\n  Theme words:")
            for tw in result.get("theme_words", []):
                print(f"    • {tw['word']:20s}  ({tw['count']})")
        else:
            print(f"❌ Chapter '{args.chapter}' not found")

    if args.word:
        if learner.word_profiler is None:
            learner.init_analyzers()
        profile = learner.word_profiler.profile_word(args.word.lower())  # type: ignore[union-attr]
        print(f"\n{'=' * 60}")
        print(f"  Word Profile: {profile['word']}")
        print(f"{'=' * 60}")
        print(f"  Total frequency: {profile['total_freq']:,}")
        print(f"  Books found in:  {profile['books_found']}")
        trans = ", ".join(profile.get("all_translations", [])[:10])
        print(f"  Translations:    {trans}")
        if profile.get("meaning_shifts"):
            print("\n  ⚠ Meaning shifts detected:")
            for ms in profile["meaning_shifts"]:
                print(f"    • {ms['translation']:30s} → {', '.join(ms['books'][:5])}")
        print("\n  Per-book distribution:")
        for bd in profile.get("per_book_distribution", [])[:15]:
            trans = ", ".join(bd.get("top_translations", [])[:3])
            co = ", ".join(cw["word"] for cw in bd.get("co_occurring_words", [])[:3])
            print(f"    {bd['book']:5s} {BOOK_NAMES.get(bd['book'], ''):20s}  "
                  f"freq={bd['frequency']:>5d}  "
                  f"trans=[{trans}]  "
                  f"co=[{co}]")

    if args.topic:
        if learner.topic_clusterer is None:
            learner.init_analyzers()
            learner.topic_clusterer.cluster_all()  # type: ignore[union-attr]
        topic = learner.get_topic(args.topic)
        if topic:
            print(f"\n{'=' * 60}")
            print(f"  Topic: {topic['topic']}")
            print(f"{'=' * 60}")
            print(f"  Keyword match count: {topic['keyword_match_count']}")
            print(f"  Chapters:            {topic['chapter_count']}")
            print("\n  Characteristic words:")
            for tw in topic.get("characteristic_words", [])[:15]:
                print(f"    • {tw['word']:20s}  ({tw['count']})")
            if topic.get("usage_examples"):
                print("\n  Usage examples:")
                for ex in topic["usage_examples"]:
                    print(f"    [{ex['ref']}] {ex['zo'][:60]}")
                    print(f"                {ex['en'][:60]}")
        else:
            print(f"❌ Topic '{args.topic}' not found. Available:")
            for t in sorted(TOPIC_KEYWORDS):
                print(f"  • {t}")

    if args.lookup:
        word, book = args.lookup
        if learner.word_profiler is None:
            learner.init_analyzers()
        result = learner.lookup(word, book)
        print(f"\n{'=' * 60}")
        print(f"  Context Lookup: {result['word']} in {result['book']}")
        print(f"{'=' * 60}")
        print(f"  Book:               {result['book_name']}")
        print(f"  Frequency in book:  {result['frequency_in_book']}")
        print(f"  Total frequency:    {result['total_frequency']:,}")
        print(f"  Translations:       {', '.join(result.get('translations', [])[:5])}")
        if result.get("co_occurring_words"):
            print(f"\n  Co-occurring words in {result['book']}:")
            for cw in result["co_occurring_words"]:
                print(f"    • {cw['word']:20s}  ({cw['count']})")
        if result.get("topic_associations"):
            print(f"\n  Topic associations: {', '.join(result['topic_associations'])}")
        if result.get("meaning_shifts"):
            print("\n  ⚠ Meaning shifts:")
            for ms in result["meaning_shifts"]:
                print(f"    • {ms['translation']:30s} → {', '.join(ms['books'][:5])}")
        print(f"\n  Books found in: {result['books_found_in']}")


if __name__ == "__main__":
    main()
