#!/usr/bin/env python3
"""
Batch Myanmar translation filler using Gemini ensemble.
Fills missing Myanmar translations for Zolai dictionary entries.

Features:
- Resume capability: skips entries that already have Myanmar translations
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
from typing import List, Dict, Optional

# Add local package path
sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient
from shared.zvs_context import get_system_prompt

DB_PATH = Path(os.environ.get("DATA", "data")) / "zolai.db"
BATCH_SIZE = 50
DELAY_BETWEEN_CALLS = 1.0  # seconds

# Ensemble models for majority voting
ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
]


async def get_missing_entries(limit: int = 500) -> List[Dict]:
    """Get Zolai words missing Myanmar translations (resume-safe)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT zolai, english_clean, pos, source
        FROM dictionary
        WHERE (myanmar IS NULL OR myanmar = '')
        AND zolai GLOB '[a-z]*' AND zolai NOT GLOB '*[^a-z\-]*'
        AND english_clean IS NOT NULL AND english_clean != ''
        AND is_deleted = 0
        ORDER BY
            CASE source
                WHEN 'bible_zo_en' THEN 1
                WHEN 'supplement' THEN 2
                WHEN 'zvs_master' THEN 3
                ELSE 4
            END,
            RANDOM()
        LIMIT ?
    """, (limit,))

    entries = []
    for row in cursor:
        entries.append({
            "zolai": row["zolai"],
            "english": row["english_clean"],
            "pos": row["pos"] or "",
            "source": row["source"]
        })
    conn.close()
    return entries


async def translate_with_ensemble(client: ZolaiGeminiOpenAIClient, zolai: str, english: str) -> Dict:
    """Translate using ensemble voting."""
    prompt = f"""Translate this Zolai word to Myanmar/Burmese script.

Zolai: {zolai}
English: {english}

Reply with ONLY the Myanmar translation (no explanation)."""

    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=True)
            # Clean result
            myanmar = result.strip()
            if myanmar:
                votes[model] = myanmar
            await asyncio.sleep(DELAY_BETWEEN_CALLS)
        except Exception as e:
            print(f"  Warning: {model} failed for {zolai}: {e}")

    # Count votes
    vote_counts = {}
    for model, translation in votes.items():
        vote_counts[translation] = vote_counts.get(translation, 0) + 1

    if not vote_counts:
        return {"translation": None, "confidence": 0.0, "votes": {}, "models_used": 0}

    # Majority vote
    winner = max(vote_counts, key=vote_counts.get)
    confidence = vote_counts[winner] / len(votes)

    return {
        "translation": winner,
        "confidence": confidence,
        "votes": votes,
        "models_used": len(votes)
    }


def log_audit(conn: sqlite3.Connection, table: str, word: str, field: str,
              old_value: str, new_value: str, reason: str):
    """Write a change to the data_audit_log table."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, 0, ?, ?, ?, ?, ?)""",
        (table, field, old_value, new_value, now, reason)
    )


async def process_batch(limit: int = 500):
    """Main batch processing function with resume, progress, and audit."""
    # Initialize client
    client = ZolaiGeminiOpenAIClient()
    await client.init()

    # Get entries (resume-safe: only entries without Myanmar)
    entries = await get_missing_entries(limit)
    total = len(entries)
    print(f"Found {total} entries to translate")

    if total == 0:
        print("No entries to translate. Done.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    translated = 0
    skipped = 0
    for i, entry in enumerate(entries):
        zolai = entry["zolai"]
        english = entry["english"]

        # Resume check: verify entry still has no Myanmar
        c.execute("SELECT myanmar FROM dictionary WHERE zolai = ? AND is_deleted = 0", (zolai,))
        row = c.fetchone()
        if row and row[0]:
            skipped += 1
            continue

        print(f"\n[{i+1}/{total}] {zolai} ({english})")

        result = await translate_with_ensemble(client, zolai, english)

        if result["translation"]:
            # Log old value for audit
            old_myanmar = row[0] if row else ""

            # Update database
            c.execute("""
                UPDATE dictionary
                SET myanmar = ?,
                    update_remarks = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE zolai = ? AND (myanmar IS NULL OR myanmar = '')
            """, (result["translation"],
                  f"gemini-ensemble(conf={result['confidence']:.2f},models={result['models_used']})",
                  zolai))

            if c.rowcount > 0:
                translated += 1
                # Audit log
                log_audit(
                    conn, "dictionary", zolai, "myanmar",
                    old_myanmar or "", result["translation"],
                    f"batch_myanmar_translation: conf={result['confidence']:.2f}, models={result['models_used']}"
                )
                print(f"  ✓ {result['translation']} (conf: {result['confidence']:.2f}, models: {result['models_used']})")
            else:
                print(f"  - Already translated or not found")
        else:
            print(f"  ✗ Failed to translate")

        # Progress tracking every 50 entries
        if (i + 1) % 50 == 0:
            pct = (i + 1) / total * 100
            print(f"\n--- Progress: Processed {i+1}/{total} ({pct:.1f}%) | Translated: {translated} | Skipped: {skipped} ---")

        # Commit every 10 entries
        if (i + 1) % 10 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    print(f"\n✅ Batch complete: {translated} translations added, {skipped} skipped (already had Myanmar)")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch Myanmar translation for Zolai dictionary")
    parser.add_argument("--limit", type=int, default=500, help="Max entries to process")
    args = parser.parse_args()
    await process_batch(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
