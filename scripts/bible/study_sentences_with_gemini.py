#!/usr/bin/env python3
"""
Sentence Study with Gemini — Analyze Zolai sentences deeply.

Analyzes:
- Grammar structure (SOV, ergative, etc.)
- Vocabulary breakdown
- Tone patterns
- Register/formality
- Cultural context
- What you might not know how to say

Saves to: training_exercises, word_usage, translations tables
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
BATCH_SIZE = 20
MAX_SENTENCES = 200

def get_gemini_client():
    """Get Gemini client from zolai-ai-local."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "zolai-ai-local"))
    from gemini.client_openai import ZolaiGeminiOpenAIClient
    return ZolaiGeminiOpenAIClient(model="gemini-3-flash")

async def analyze_sentence(client, zo_text, en_text):
    """Ask Gemini to analyze a Zolai sentence deeply."""
    prompt = f"""Analyze this Zolai sentence for language learning:

Zolai: {zo_text}
English: {en_text}

Provide comprehensive analysis:

1. **Grammar Structure**:
   - Sentence pattern (S+O+V, S+IO+DO+V, etc.)
   - Mark ergative agent with [ERG]
   - Identify verb tense/aspect [PAST], [PRESENT], [FUTURE], [COMPLETIVE], etc.
   - Identify negation pattern (if any)
   - Identify question pattern (if any)
   - Pronoun usage

2. **Vocabulary Breakdown**:
   - Each Zolai word with English meaning
   - Note POS (noun, verb, adj, etc.)
   - Note any particles (in, a, hi, etc.)

3. **Tone Analysis**:
   - Identify tone pattern (T1, T2, T3, T4)
   - Note any tone sandhi rules

4. **Register**:
   - Formal/informal/literary
   - Who would say this? When?

5. **Cultural Context**:
   - Historical/cultural background
   - Relevance to Zomi culture

6. **What You Might Not Know**:
   - Grammar patterns that are tricky
   - Vocabulary that has multiple meanings
   - Cultural nuances
   - Common mistakes learners make

7. **Practice Sentences**:
   - 3 similar sentences for practice
   - 1 negative version
   - 1 question version

Return as JSON:
{{
  "grammar_structure": "S + O + V",
  "tense_aspect": "PRESENT",
  "negation": "none or pattern",
  "question": "none or pattern",
  "vocabulary": [{{"word": "zolai", "meaning": "english", "pos": "noun"}}],
  "tone_pattern": "T1+T3",
  "register": "neutral",
  "cultural_context": "context",
  "what_you_might_not_know": ["point1", "point2"],
  "practice_sentences": [{{"zo": "sentence", "en": "translation"}}],
  "difficulty_level": "A1/A2/B1/B2/C1/C2"
}}

Return ONLY the JSON object."""

    try:
        response = await client.chat(prompt)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini failed: {e}")
        return None

async def main():
    """Main entry point."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Get sentences from translations not yet analyzed
    sentences = db.execute("""
        SELECT source, target, source_lang
        FROM translations
        WHERE source_lang = 'zo'
        AND source IS NOT NULL AND source != ''
        LIMIT ?
    """, (MAX_SENTENCES,)).fetchall()

    logger.info(f"Analyzing {len(sentences)} sentences...")
    client = get_gemini_client()

    analyzed = 0
    for sent in sentences:
        analysis = await analyze_sentence(client, sent['source'], sent['target'])

        if analysis:
            # Save to training_exercises
            db.execute("""
                INSERT INTO training_exercises
                (exercise_type, zolai, english, source, difficulty, myanmar)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'sentence_analysis',
                sent['source'],
                sent['target'],
                'gemini_analysis',
                analysis.get('difficulty_level', 'B1'),
                json.dumps(analysis)
            ))

            # Update word_usage for words in this sentence
            vocab = analysis.get('vocabulary', [])
            for v in vocab:
                word = v.get('word', '')
                if word:
                    # Upsert word_usage
                    existing = db.execute(
                        "SELECT id FROM word_usage WHERE word = ? AND book = 'SENTENCE'",
                        (word,)
                    ).fetchone()

                    if existing:
                        db.execute("""
                            UPDATE word_usage SET total_freq = total_freq + 1
                            WHERE id = ?
                        """, (existing['id'],))
                    else:
                        db.execute("""
                            INSERT INTO word_usage (word, book, total_freq, meaning_shifts, co_occurring_words)
                            VALUES (?, 'SENTENCE', 1, ?, ?)
                        """, (
                            word,
                            json.dumps([analysis.get('tense_aspect', '')]),
                            json.dumps([v.get('meaning', '') for v in vocab[:5]])
                        ))

        analyzed += 1
        if analyzed % 10 == 0:
            db.commit()
            logger.info(f"Analyzed {analyzed}/{len(sentences)} ({100*analyzed//len(sentences)}%)")

    db.commit()
    db.close()
    logger.info(f"Done! Analyzed {analyzed} sentences.")

if __name__ == "__main__":
    asyncio.run(main())
