#!/usr/bin/env python3
"""
Bible Study Analyzer — Use Gemini to analyze Bible verses deeply.

Analyzes grammar, vocabulary, sentence patterns, and cultural context.
Saves results to bible_study_analysis table.
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
MAX_VERSES = 200

def get_gemini_client():
    """Get Gemini client from zolai-ai-local."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "zolai-ai-local"))
    from gemini.client_openai import ZolaiGeminiOpenAIClient
    return ZolaiGeminiOpenAIClient(model="gemini-3-flash")

async def analyze_verse(client, ref, zo_text, en_text):
    """Ask Gemini to analyze a Bible verse deeply."""
    prompt = f"""Analyze this Zolai Bible verse for language learning:

Reference: {ref}
Zolai: {zo_text}
English: {en_text}

Provide detailed analysis:

1. **Grammar Analysis**:
   - Sentence structure (SOV, ergative, etc.)
   - Verb tense/aspect (past, present, future, completive, etc.)
   - Negation pattern (if any)
   - Question pattern (if any)
   - Pronoun usage

2. **Vocabulary List**:
   - Key Zolai words with English meanings
   - Note any polysemous words (multiple meanings)
   - Note any compound words

3. **Sentence Pattern**:
   - Pattern: e.g., S + O + V, S + IO + DO + V
   - Mark ergative agent with [ERG]

4. **Tense/Aspect**:
   - Identify main verb tense/aspect
   - Mark with brackets: [PAST], [PRESENT], [FUTURE], [COMPLETIVE], etc.

5. **Cultural Context**:
   - Historical/cultural background
   - Relevance to Zomi culture

6. **Study Notes**:
   - Learning points for students
   - Common mistakes to avoid

Return as JSON:
{{
  "grammar_analysis": "detailed grammar analysis",
  "vocabulary_list": [{{"word": "zolai", "meaning": "english", "notes": "usage"}}],
  "sentence_pattern": "S + O + V",
  "tense_aspect": "PAST/PRESENT/FUTURE",
  "negation_pattern": "negation type or none",
  "question_pattern": "question type or none",
  "cultural_context": "cultural background",
  "study_notes": "learning points",
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
        logger.error(f"Gemini failed for {ref}: {e}")
        return None

async def main():
    """Main entry point."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Get verses not yet analyzed
    verses = db.execute("""
        SELECT b.ref, b.zo_tdb77, b.en_kJV
        FROM bible_verses b
        LEFT JOIN bible_study_analysis bsa ON b.ref = bsa.ref
        WHERE b.zo_tdb77 IS NOT NULL AND b.zo_tdb77 != ''
        AND bsa.id IS NULL
        LIMIT ?
    """, (MAX_VERSES,)).fetchall()

    logger.info(f"Analyzing {len(verses)} verses...")
    client = get_gemini_client()

    analyzed = 0
    for verse in verses:
        analysis = await analyze_verse(client, verse['ref'], verse['zo_tdb77'], verse['en_kJV'])

        if analysis:
            db.execute("""
                INSERT INTO bible_study_analysis
                (ref, book, chapter, verse, zo_text, en_text, grammar_analysis,
                 vocabulary_list, sentence_pattern, tense_aspect, negation_pattern,
                 question_pattern, cultural_context, study_notes, difficulty_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                verse['ref'],
                verse['ref'].split()[0] if ' ' in verse['ref'] else '',
                int(verse['ref'].split(':')[0].split()[-1]) if ':' in verse['ref'] else 0,
                int(verse['ref'].split(':')[1]) if ':' in verse['ref'] else 0,
                verse['zo_tdb77'],
                verse['en_kJV'],
                analysis.get('grammar_analysis', ''),
                json.dumps(analysis.get('vocabulary_list', [])),
                analysis.get('sentence_pattern', ''),
                analysis.get('tense_aspect', ''),
                analysis.get('negation_pattern', ''),
                analysis.get('question_pattern', ''),
                analysis.get('cultural_context', ''),
                analysis.get('study_notes', ''),
                analysis.get('difficulty_level', 'B1')
            ))

        analyzed += 1
        if analyzed % 10 == 0:
            db.commit()
            logger.info(f"Analyzed {analyzed}/{len(verses)} ({100*analyzed//len(verses)}%)")

    db.commit()
    db.close()
    logger.info(f"Done! Analyzed {analyzed} verses.")

if __name__ == "__main__":
    asyncio.run(main())
