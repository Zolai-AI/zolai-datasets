#!/usr/bin/env python3
"""
Populate dictionary_meanings table using Gemini for multi-meaning support.

For each word in dictionary, ask Gemini to find all meanings, contexts, and examples.
"""
import sys
import json
import sqlite3
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "zolai.db"
BATCH_SIZE = 50
MAX_WORDS = 500  # Start with 500 words

def get_gemini_client():
    """Get Gemini client from zolai-ai-local."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "zolai-ai-local"))
    from gemini.client_openai import ZolaiGeminiOpenAIClient
    return ZolaiGeminiOpenAIClient(model="gemini-3-flash")

async def analyze_word_meanings(client, zolai_word, english_word):
    """Ask Gemini to find all meanings for a word."""
    prompt = f"""Analyze the Zolai word "{zolai_word}" (English: "{english_word}").
Find ALL meanings and provide:

1. Multiple English meanings (if the word has more than one meaning)
2. Myanmar translations for each meaning
3. Usage context (formal/informal, noun/verb/adj)
4. Example sentences in Zolai, English, and Myanmar
5. Any collocations or common phrases

Return as JSON array:
[
  {{
    "meaning_en": "primary English meaning",
    "meaning_my": "Myanmar translation",
    "meaning_zo": "Zolai definition/context",
    "pos": "noun/verb/adj/adv",
    "context": "formal/informal/literary",
    "example_zo": "example sentence in Zolai",
    "example_en": "example sentence in English",
    "example_my": "example sentence in Myanmar",
    "is_primary": 1
  }}
]

If only one meaning exists, return array with single object.
Return ONLY the JSON array, no other text."""

    try:
        response = await client.chat(prompt)
        # Parse JSON from response
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini failed for {zolai_word}: {e}")
        return [{"meaning_en": english_word, "meaning_my": "", "meaning_zo": "", "pos": "", "context": "", "example_zo": "", "example_en": "", "example_my": "", "is_primary": 1}]

async def main():
    """Main entry point."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Get words that don't have meanings yet
    words = db.execute("""
        SELECT d.id, d.zolai, d.english_clean
        FROM dictionary d
        LEFT JOIN dictionary_meanings dm ON d.id = dm.dictionary_id
        WHERE d.is_deleted = 0
        AND d.english_clean IS NOT NULL AND d.english_clean != ''
        AND d.zolai NOT LIKE '-%'
        AND dm.id IS NULL
        LIMIT ?
    """, (MAX_WORDS,)).fetchall()

    logger.info(f"Processing {len(words)} words...")
    client = get_gemini_client()

    processed = 0
    for word in words:
        meanings = await analyze_word_meanings(client, word['zolai'], word['english_clean'])

        for meaning in meanings:
            db.execute("""
                INSERT INTO dictionary_meanings
                (dictionary_id, zolai, meaning_en, meaning_my, meaning_zo, pos, context,
                 example_zo, example_en, example_my, is_primary, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                word['id'], word['zolai'],
                meaning.get('meaning_en', ''),
                meaning.get('meaning_my', ''),
                meaning.get('meaning_zo', ''),
                meaning.get('pos', ''),
                meaning.get('context', ''),
                meaning.get('example_zo', ''),
                meaning.get('example_en', ''),
                meaning.get('example_my', ''),
                meaning.get('is_primary', 0),
                'gemini-3-flash'
            ))

        processed += 1
        if processed % 10 == 0:
            db.commit()
            logger.info(f"Processed {processed}/{len(words)} ({100*processed//len(words)}%)")

    db.commit()
    db.close()
    logger.info(f"Done! Processed {processed} words.")

if __name__ == "__main__":
    asyncio.run(main())
