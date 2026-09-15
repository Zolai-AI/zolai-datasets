#!/usr/bin/env python3
"""
Batch Myanmar translation filler for dictionary_en_zo table.
Fills missing Myanmar translations for English→Zolai entries.

Features:
- Resume capability: skips entries that already have Myanmar
- Progress tracking: prints "Processed X/Y (Z%)" every 50 entries
- Audit logging: writes changes to data_audit_log table
"""

import asyncio
import sqlite3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

# Add local package path
sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient
from shared.zvs_context import get_system_prompt

DB_PATH = Path(os.environ.get("DATA", "data")) / "zolai.db"
DELAY_BETWEEN_CALLS = 1.0  # seconds

ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
]


def log_audit(conn: sqlite3.Connection, table: str, word: str, field: str,
              old_value: str, new_value: str, reason: str):
    """Write a change to the data_audit_log table."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, 0, ?, ?, ?, ?, ?)""",
        (table, field, old_value, new_value, now, reason)
    )


async def get_missing_entries(limit: int = 500) -> List[Dict]:
    """Get English→Zolai entries missing Myanmar translations."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT english, translations, pos, source
        FROM dictionary_en_zo
        WHERE (myanmar IS NULL OR myanmar = '')
        AND english IS NOT NULL AND english != ''
        AND is_deleted = 0
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))

    entries = []
    for row in cursor:
        entries.append({
            "english": row["english"],
            "translations": row["translations"] or "",
            "pos": row["pos"] or "",
            "source": row["source"]
        })
    conn.close()
    return entries


async def translate_with_ensemble(client: ZolaiGeminiOpenAIClient, english: str, translations: str) -> Dict:
    """Translate using ensemble voting."""
    prompt = f"""Translate to Myanmar (Burmese): {english} = {translations}. Return ONLY the Myanmar word."""

    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=True)
            myanmar = result.strip()
            if myanmar:
                votes[model] = myanmar
            await asyncio.sleep(DELAY_BETWEEN_CALLS)
        except Exception as e:
            print(f"  Warning: {model} failed for {english}: {e}")

    vote_counts = {}
    for model, translation in votes.items():
        vote_counts[translation] = vote_counts.get(translation, 0) + 1

    if not vote_counts:
        return {"translation": None, "confidence": 0.0, "votes": {}, "models_used": 0}

    winner = max(vote_counts, key=vote_counts.get)
    confidence = vote_counts[winner] / len(votes)

    return {
        "translation": winner,
        "confidence": confidence,
        "votes": votes,
        "models_used": len(votes)
    }


async def process_batch(limit: int = 500):
    """Main batch processing with resume, progress, and audit."""
    client = ZolaiGeminiOpenAIClient()
    await client.init()

    entries = await get_missing_entries(limit)
    total = len(entries)
    print(f"Found {total} entries to translate")

    if total == 0:
        print("No entries to translate. Done.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    translated = 0
    for i, entry in enumerate(entries):
        english = entry["english"]
        translations = entry["translations"]

        # Resume check
        c.execute("SELECT myanmar FROM dictionary_en_zo WHERE english = ? AND is_deleted = 0", (english,))
        row = c.fetchone()
        if row and row[0]:
            continue

        print(f"\n[{i+1}/{total}] {english} = {translations[:50]}")

        result = await translate_with_ensemble(client, english, translations)

        if result["translation"]:
            old_myanmar = row[0] if row else ""

            c.execute("""
                UPDATE dictionary_en_zo
                SET myanmar = ?,
                    update_remarks = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE english = ? AND (myanmar IS NULL OR myanmar = '')
            """, (result["translation"],
                  f"batch_en_zo(conf={result['confidence']:.2f},models={result['models_used']})",
                  english))

            if c.rowcount > 0:
                translated += 1
                log_audit(
                    conn, "dictionary_en_zo", english, "myanmar",
                    old_myanmar or "", result["translation"],
                    f"batch_fix_en_zo_myanmar: conf={result['confidence']:.2f}"
                )
                print(f"  ✓ {result['translation']} (conf: {result['confidence']:.2f})")
            else:
                print(f"  - Already translated or not found")
        else:
            print(f"  ✗ Failed to translate")

        if (i + 1) % 50 == 0:
            pct = (i + 1) / total * 100
            print(f"\n--- Progress: Processed {i+1}/{total} ({pct:.1f}%) | Translated: {translated} ---")

        if (i + 1) % 10 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    print(f"\n✅ Batch complete: {translated} translations added")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch Myanmar translation for dictionary_en_zo")
    parser.add_argument("--limit", type=int, default=500, help="Max entries to process")
    args = parser.parse_args()
    await process_batch(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
