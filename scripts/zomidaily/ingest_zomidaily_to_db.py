#!/usr/bin/env python3
"""
Ingest ZomiDaily data into zolai.db.

Sources:
- articles/ (12,966 JSON files) → articles table + bible_verses for training
- vocabulary/words_frequency.jsonl → word_usage
- vocabulary/grammar_patterns.jsonl → grammar_patterns
- vocabulary/new_words.jsonl → dictionary (new words)
- vocabulary/phrases.jsonl → phrases
- vocabulary/proverbs.jsonl → proverbs

Also extracts:
- Vocabulary from articles
- POS patterns
- Sentence structures
"""
import json
import sqlite3
import logging
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"
ZOMIDAILY_PATH = Path(__file__).resolve().parents[3] / "data" / "raw" / "zomidaily"


def ingest_word_frequency(conn):
    """Ingest words_frequency.jsonl into word_usage."""
    freq_file = ZOMIDAILY_PATH / "vocabulary" / "words_frequency.jsonl"
    if not freq_file.exists():
        logger.warning("words_frequency.jsonl not found")
        return 0

    count = 0
    with open(freq_file) as f:
        for line in f:
            data = json.loads(line.strip())
            word = data.get('word', '').strip()
            freq = data.get('count', 0)

            if word and len(word) > 1:
                existing = conn.execute(
                    "SELECT id FROM word_usage WHERE word = ? AND book = 'ZOMIDAILY'",
                    (word,)
                ).fetchone()

                if existing:
                    conn.execute(
                        "UPDATE word_usage SET total_freq = ? WHERE id = ?",
                        (freq, existing['id'])
                    )
                else:
                    conn.execute(
                        "INSERT INTO word_usage (word, book, total_freq, meaning_shifts, co_occurring_words) VALUES (?, 'ZOMIDAILY', ?, '[]', '[]')",
                        (word, freq)
                    )
                count += 1

    conn.commit()
    logger.info(f"Ingested {count} word frequencies")
    return count


def ingest_grammar_patterns(conn):
    """Ingest grammar_patterns.jsonl into grammar_patterns table."""
    patterns_file = ZOMIDAILY_PATH / "vocabulary" / "grammar_patterns.jsonl"
    if not patterns_file.exists():
        logger.warning("grammar_patterns.jsonl not found")
        return 0

    count = 0
    with open(patterns_file) as f:
        for line in f:
            data = json.loads(line.strip())
            pattern = data.get('pattern', '')
            freq = data.get('count', 0)

            if pattern:
                existing = conn.execute(
                    "SELECT id FROM grammar_patterns WHERE pattern = ?",
                    (pattern,)
                ).fetchone()

                if not existing:
                    conn.execute("""
                        INSERT INTO grammar_patterns (pattern_id, pattern, description, function, examples, frequency)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        f"ZOMIDAILY_{pattern}",
                        pattern,
                        f"From ZomiDaily corpus (freq: {freq})",
                        'corpus_discovered',
                        '',
                        freq
                    ))
                    count += 1

    conn.commit()
    logger.info(f"Ingested {count} grammar patterns")
    return count


def ingest_phrases(conn):
    """Ingest phrases.jsonl into phrases table."""
    phrases_file = ZOMIDAILY_PATH / "vocabulary" / "phrases.jsonl"
    if not phrases_file.exists():
        logger.warning("phrases.jsonl not found")
        return 0

    count = 0
    with open(phrases_file) as f:
        for line in f:
            data = json.loads(line.strip())
            phrase = data.get('phrase', '')
            freq = data.get('count', 0)
            ptype = data.get('type', '')

            if phrase:
                existing = conn.execute(
                    "SELECT id FROM phrases WHERE zolai = ?",
                    (phrase,)
                ).fetchone()

                if not existing:
                    conn.execute("""
                        INSERT INTO phrases (zolai, english, frequency, examples)
                        VALUES (?, ?, ?, ?)
                    """, (
                        phrase,
                        f"ZomiDaily phrase ({ptype})",
                        freq,
                        json.dumps({'type': ptype, 'count': freq})
                    ))
                    count += 1

    conn.commit()
    logger.info(f"Ingested {count} phrases")
    return count


def ingest_proverbs(conn):
    """Ingest proverbs.jsonl into proverbs table."""
    proverbs_file = ZOMIDAILY_PATH / "vocabulary" / "proverbs.jsonl"
    if not proverbs_file.exists():
        logger.warning("proverbs.jsonl not found")
        return 0

    count = 0
    with open(proverbs_file) as f:
        for line in f:
            data = json.loads(line.strip())
            text = data.get('text', '')

            if text:
                existing = conn.execute(
                    "SELECT id FROM proverbs WHERE zolai = ?",
                    (text[:100],)
                ).fetchone()

                if not existing:
                    conn.execute("""
                        INSERT INTO proverbs (zolai, english, source, category)
                        VALUES (?, ?, ?, ?)
                    """, (
                        text,
                        '',
                        'zomidaily',
                        'corpus'
                    ))
                    count += 1

    conn.commit()
    logger.info(f"Ingested {count} proverbs")
    return count


def ingest_articles(conn):
    """Ingest articles into articles table and extract vocabulary."""
    articles_dir = ZOMIDAILY_PATH / "articles"
    if not articles_dir.exists():
        logger.warning("articles directory not found")
        return 0

    count = 0
    word_counter = Counter()

    for json_file in sorted(articles_dir.glob("*.json"))[:1000]:  # Start with 1000
        try:
            with open(json_file) as f:
                data = json.load(f)

            article_id = data.get('id')
            title = data.get('title', '')
            content = data.get('content', '')
            date = data.get('date', '')
            tags = data.get('tags', [])

            if content:
                # Insert into articles table
                conn.execute("""
                    INSERT OR IGNORE INTO articles (id, title, content, source)
                    VALUES (?, ?, ?, ?)
                """, (article_id, title, content[:5000], 'zomidaily'))

                # Extract words for frequency
                words = content.split()
                for word in words:
                    clean = word.strip('.,!?;:"\'()-').lower()
                    if len(clean) > 2:
                        word_counter[clean] += 1

                count += 1

        except Exception as e:
            logger.error(f"Failed to process {json_file}: {e}")

    # Update word frequencies from articles
    for word, freq in word_counter.most_common(5000):
        existing = conn.execute(
            "SELECT id FROM word_usage WHERE word = ? AND book = 'ZOMIDAILY_ARTICLES'",
            (word,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE word_usage SET total_freq = total_freq + ? WHERE id = ?",
                (freq, existing['id'])
            )
        else:
            conn.execute(
                "INSERT INTO word_usage (word, book, total_freq, meaning_shifts, co_occurring_words) VALUES (?, 'ZOMIDAILY_ARTICLES', ?, '[]', '[]')",
                (word, freq)
            )

    conn.commit()
    logger.info(f"Ingested {count} articles, extracted {len(word_counter)} unique words")
    return count


def main():
    """Main entry point."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    logger.info("=== Starting ZomiDaily Ingestion ===")

    results = {
        'word_frequency': ingest_word_frequency(conn),
        'grammar_patterns': ingest_grammar_patterns(conn),
        'phrases': ingest_phrases(conn),
        'proverbs': ingest_proverbs(conn),
        'articles': ingest_articles(conn),
    }

    conn.close()

    logger.info("=== Ingestion Complete ===")
    for k, v in results.items():
        logger.info(f"  {k}: {v}")

    return results


if __name__ == "__main__":
    main()
