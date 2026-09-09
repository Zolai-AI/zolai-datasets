#!/usr/bin/env python3
"""Extract vocabulary, phrases, and patterns from scraped ZomiDaily articles.

Usage:
    python extract_knowledge.py                 # Full extraction
    python extract_knowledge.py --stats         # Show extraction stats
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ARTICLES_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily" / "articles"
VOCAB_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily" / "vocabulary"
METADATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily" / "metadata"

# Known English words to exclude from Zolai vocabulary extraction
ENGLISH_STOP = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "must", "not",
    "no", "nor", "if", "then", "else", "when", "where", "how", "what",
    "which", "who", "whom", "this", "that", "these", "those", "it",
    "its", "he", "she", "they", "them", "we", "you", "me", "him",
    "her", "his", "my", "your", "our", "their", "mine", "yours",
    "hers", "ours", "theirs", "so", "as", "up", "out", "about",
    "into", "over", "after", "before", "between", "under", "again",
    "further", "once", "here", "there", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "than",
    "too", "very", "just", "also", "now", "new", "like", "well",
    "back", "even", "still", "way", "take", "much", "go", "come",
    "know", "see", "think", "make", "get", "say", "said", "one",
    "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "first", "last", "next", "year", "years", "day", "days",
    "time", "people", "man", "men", "woman", "women", "child", "children",
    "thing", "things", "place", "world", "country", "hand", "part",
    "number", "right", "left", "good", "great", "big", "small",
    "long", "high", "old", "little", "own", "same", "us", "down",
    "while", "because", "until", "although", "since", "through",
    "during", "without", "within", "along", "across", "behind",
    "beyond", "around", "above", "below", "near", "far", "never", "always", "often", "sometimes", "already", "yet",
    "ever", "ago", "soon", "today", "tomorrow",
    "yesterday", "everywhere", "nowhere",
    "yes", "ok", "okay", "wow", "oh", "ah", "um", "uh",
    # WordPress/HTML artifacts
    "nbsp", "amp", "lt", "gt", "quot", "apos",
    "com", "org", "net", "http", "https", "www", "html",
    "img", "src", "alt", "div", "span", "class", "style",
    "font", "color", "size", "width", "height", "border",
    "padding", "margin", "text", "center", "top", "bottom", "block", "none", "auto", "bold",
    "italic", "normal", "medium", "large",
    # Common Zolai function words (will be captured separately)
}

# Common Zolai particles/function words to track separately
ZOLAI_PARTICLES = {
    "hi", "hen", "un", "in", "vo", "le", "leh", "tawh", "ah",
    "ciang", "ci", "tua", "banah", "manin", "pen", "ni", "aw",
    "lo", "kei", "ding", "ta", "zo", "lai", "khin", "hiam",
    "diam", "bang", "hong", "va", "khia", "lut", "kik",
    "ka", "na", "a", "i", "ki", "amah",
}


def load_articles() -> list[dict[str, Any]]:
    """Load all scraped articles from disk."""
    articles = []
    for fp in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            with open(fp) as f:
                articles.append(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [WARN] Skipping {fp.name}: {e}", file=sys.stderr)
    return articles


def is_english_word(word: str) -> bool:
    """Heuristic: is this likely an English word?"""
    lower = word.lower()
    if lower in ENGLISH_STOP:
        return True
    # Words with mostly ASCII + common English patterns
    if re.match(r"^[a-z]+$", lower) and len(lower) > 1:
        # Check if it's a common English word pattern
        english_suffixes = (
            "tion", "sion", "ment", "ness", "able", "ible",
            "ful", "less", "ous", "ive", "ing", "ed", "ly",
            "er", "or", "al", "ial", "tion", "sion", "ence",
            "ance", "ity", "ies", "ual",
        )
        if any(lower.endswith(s) for s in english_suffixes) and len(lower) > 4:
            return True
    return False


def extract_words(articles: list[dict[str, Any]]) -> Counter:
    """Extract all words with frequency counts."""
    word_counter: Counter = Counter()
    for article in articles:
        text = article.get("content", "")
        # Split into words, keeping only alphabetic tokens
        words = re.findall(r"[a-zA-Z']+", text)
        for word in words:
            clean = word.strip("'").lower()
            if len(clean) < 2:
                continue
            word_counter[clean] += 1
    return word_counter


def extract_bigrams(articles: list[dict[str, Any]]) -> Counter:
    """Extract bigram phrases with frequency."""
    bigram_counter: Counter = Counter()
    for article in articles:
        text = article.get("content", "")
        words = re.findall(r"[a-zA-Z']+", text)
        words = [w.strip("'").lower() for w in words if len(w.strip("'")) >= 2]
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            bigram_counter[bg] += 1
    return bigram_counter


def extract_trigrams(articles: list[dict[str, Any]]) -> Counter:
    """Extract trigram phrases with frequency."""
    trigram_counter: Counter = Counter()
    for article in articles:
        text = article.get("content", "")
        words = re.findall(r"[a-zA-Z']+", text)
        words = [w.strip("'").lower() for w in words if len(w.strip("'")) >= 2]
        for i in range(len(words) - 2):
            tg = f"{words[i]} {words[i+1]} {words[i+2]}"
            trigram_counter[tg] += 1
    return trigram_counter


def extract_sentences(articles: list[dict[str, Any]]) -> list[str]:
    """Extract all sentences from articles."""
    sentences: list[str] = []
    for article in articles:
        text = article.get("content", "")
        # Split on sentence boundaries
        sents = re.split(r"[.!?।\n]+", text)
        for s in sents:
            s = s.strip()
            if len(s) > 10:  # Skip very short fragments
                sentences.append(s)
    return sentences


def detect_grammar_patterns(sentences: list[str]) -> dict[str, int]:
    """Detect common Zolai grammar patterns."""
    patterns: dict[str, int] = {
        "negation_kei": 0,
        "negation_lo": 0,
        "question_hiam": 0,
        "question_diam": 0,
        "question_bang": 0,
        "future_ding": 0,
        "past_ta": 0,
        "completive_zo": 0,
        "progressive_lai": 0,
        "ergative_in": 0,
        "quotative_ci": 0,
    }

    for sent in sentences:
        words = sent.lower().split()
        if "kei" in words:
            patterns["negation_kei"] += 1
        if "lo" in words and "kei" not in words:
            patterns["negation_lo"] += 1
        if "hiam" in words:
            patterns["question_hiam"] += 1
        if "diam" in words:
            patterns["question_diam"] += 1
        if "bang" in words:
            patterns["question_bang"] += 1
        if "ding" in words:
            patterns["future_ding"] += 1
        if "ta" in words and len(words) > 3:
            patterns["past_ta"] += 1
        if "zo" in words:
            patterns["completive_zo"] += 1
        if "lai" in words:
            patterns["progressive_lai"] += 1
        if "in" in words:
            patterns["ergative_in"] += 1
        if "ci" in words:
            patterns["quotative_ci"] += 1

    return patterns


def extract_proverbs(sentences: list[str]) -> list[str]:
    """Heuristic: extract likely proverbs (short, complete sentences)."""
    proverbs: list[str] = []
    seen: set[str] = set()
    for sent in sentences:
        words = sent.split()
        # Proverbs tend to be 4-15 words, declarative
        if 4 <= len(words) <= 15:
            lower = sent.lower().strip()
            if lower not in seen:
                seen.add(lower)
                # Likely proverb if it ends with period or common particles
                if lower.endswith((".", "hi")):
                    proverbs.append(sent.strip())
    return proverbs[:500]  # Cap at 500


def load_existing_dictionary() -> set[str]:
    """Load existing Zolai dictionary headwords for new-word detection."""
    dict_files = [
        Path(__file__).resolve().parents[3] / "data" / "dictionary" / "processed"
        / "dict_zo_en_master_v1.jsonl",
        Path(__file__).resolve().parents[3] / "data" / "bible" / "language_learning"
        / "vocab_index_full.jsonl",
    ]
    known: set[str] = set()
    for df in dict_files:
        if not df.exists():
            continue
        with open(df) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    # Try common key names
                    for key in ("word", "headword", "zo", "zolai"):
                        if key in entry:
                            known.add(entry[key].lower().strip())
                            break
                except (json.JSONDecodeError, KeyError):
                    continue
    return known


def run_extraction() -> None:
    """Main extraction pipeline."""
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ZOMIDAILY KNOWLEDGE EXTRACTION")
    print("=" * 60)

    # Load articles
    articles = load_articles()
    if not articles:
        print("[ERROR] No articles found. Run scraper first.", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(articles)} articles")

    total_words = sum(a.get("word_count", 0) for a in articles)
    print(f"Total words: {total_words:,}")

    # 1. Extract vocabulary
    print("\n--- Extracting vocabulary ---")
    word_freq = extract_words(articles)
    print(f"Unique words: {len(word_freq):,}")

    # Save word frequency
    vocab_file = VOCAB_DIR / "words_frequency.jsonl"
    with open(vocab_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({"word": word, "count": count}, ensure_ascii=False) + "\n" for word, count in word_freq.most_common())
    print(f"  Saved: {vocab_file}")

    # 2. Extract phrases (bigrams + trigrams)
    print("\n--- Extracting phrases ---")
    bigram_freq = extract_bigrams(articles)
    trigram_freq = extract_trigrams(articles)
    print(f"Unique bigrams:  {len(bigram_freq):,}")
    print(f"Unique trigrams: {len(trigram_freq):,}")

    phrases_file = VOCAB_DIR / "phrases.jsonl"
    with open(phrases_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({
                "phrase": phrase, "count": count, "type": "bigram"
            }, ensure_ascii=False) + "\n" for phrase, count in bigram_freq.most_common(5000))
        f.writelines(json.dumps({
                "phrase": phrase, "count": count, "type": "trigram"
            }, ensure_ascii=False) + "\n" for phrase, count in trigram_freq.most_common(2000))
    print(f"  Saved: {phrases_file}")

    # 3. Detect new words (not in existing dictionary)
    print("\n--- Detecting new words ---")
    known_words = load_existing_dictionary()
    print(f"Known dictionary words: {len(known_words):,}")

    new_words: list[dict[str, Any]] = []
    for word, count in word_freq.most_common():
        if word not in known_words and not is_english_word(word):
            if count >= 3:  # At least 3 occurrences
                new_words.append({"word": word, "count": count})
    print(f"New Zolai words (freq >= 3): {len(new_words):,}")

    new_words_file = VOCAB_DIR / "new_words.jsonl"
    with open(new_words_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(entry, ensure_ascii=False) + "\n" for entry in new_words)
    print(f"  Saved: {new_words_file}")

    # 4. Grammar patterns
    print("\n--- Detecting grammar patterns ---")
    sentences = extract_sentences(articles)
    print(f"Total sentences: {len(sentences):,}")

    patterns = detect_grammar_patterns(sentences)
    for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"  {pattern}: {count:,}")

    patterns_file = VOCAB_DIR / "grammar_patterns.jsonl"
    with open(patterns_file, "w", encoding="utf-8") as f:
        for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
            f.write(json.dumps({
                "pattern": pattern, "count": count
            }, ensure_ascii=False) + "\n")
    print(f"  Saved: {patterns_file}")

    # 5. Proverbs / wisdom sayings
    print("\n--- Extracting proverbs ---")
    proverbs = extract_proverbs(sentences)
    print(f"Likely proverbs found: {len(proverbs):,}")

    proverbs_file = VOCAB_DIR / "proverbs.jsonl"
    with open(proverbs_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({"text": p}, ensure_ascii=False) + "\n" for p in proverbs[:500])
    print(f"  Saved: {proverbs_file}")

    # 6. Category/tag distribution
    print("\n--- Category distribution ---")
    tag_counter: Counter = Counter()
    for article in articles:
        for tag in article.get("tags", []):
            tag_counter[tag] += 1
    top_tags = tag_counter.most_common(20)
    for tag, count in top_tags:
        print(f"  {tag}: {count}")

    # 7. Save extraction summary
    summary = {
        "total_articles": len(articles),
        "total_words": total_words,
        "unique_words": len(word_freq),
        "unique_bigrams": len(bigram_freq),
        "unique_trigrams": len(trigram_freq),
        "known_dictionary_words": len(known_words),
        "new_words_detected": len(new_words),
        "sentences_extracted": len(sentences),
        "grammar_patterns": patterns,
        "proverbs_found": len(proverbs),
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
    }
    summary_file = METADATA_DIR / "extraction_stats.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  Summary: {summary_file}")

    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Articles:   {len(articles):,}")
    print(f"  Words:      {len(word_freq):,} unique")
    print(f"  Phrases:    {len(bigram_freq):,} bigrams + {len(trigram_freq):,} trigrams")
    print(f"  New words:  {len(new_words):,}")
    print(f"  Proverbs:   {len(proverbs):,}")
    print(f"  Output dir: {VOCAB_DIR}")


def show_stats() -> None:
    """Show extraction statistics."""
    stats_file = METADATA_DIR / "extraction_stats.json"
    if not stats_file.exists():
        print("No extraction stats found. Run extraction first.")
        return
    with open(stats_file) as f:
        stats = json.load(f)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract knowledge from ZomiDaily articles"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show extraction statistics"
    )
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_extraction()


if __name__ == "__main__":
    main()
