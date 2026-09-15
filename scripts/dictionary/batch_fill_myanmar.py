#!/usr/bin/env python3
"""
Batch Myanmar translation filler for dictionary (ZO→EN) table.
Uses Gemini ensemble with majority voting.

Features:
- Resume: skips entries already having Myanmar
- Progress: saves state to JSON, prints every 50 entries
- Audit: logs all changes to data_audit_log
- Re-runnable: safe to run multiple times
"""

import asyncio
import sqlite3
import json
import os
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient

DB_PATH = Path(os.environ.get("DATA", "/home/peter/Documents/Projects/zolai-ai/data")) / "zolai.db"
PROGRESS_FILE = Path(__file__).parent / "progress_dict_zo_en.json"
BATCH_SIZE = 500
COMMIT_EVERY = 10
PROGRESS_EVERY = 50
DELAY_BETWEEN_CALLS = 1.0

ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
]

# Graceful shutdown
_shutdown = False
def _signal_handler(sig, frame):
    global _shutdown
    print("\n⚠️  Graceful shutdown requested. Finishing current entry...")
    _shutdown = True
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"translated": 0, "skipped": 0, "failed": 0, "batches_run": 0, "last_zolai": None}

def save_progress(state: dict):
    PROGRESS_FILE.write_text(json.dumps(state, indent=2))


def get_missing_entries(conn: sqlite3.Connection, limit: int = BATCH_SIZE) -> List[Dict]:
    cursor = conn.execute("""
        SELECT zolai, english_clean, pos, source
        FROM dictionary
        WHERE (myanmar IS NULL OR myanmar = '')
        AND zolai GLOB '[a-z]*' AND zolai NOT GLOB '*[^a-z-]*'
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
    return [{"zolai": r["zolai"], "english": r["english_clean"],
             "pos": r["pos"] or "", "source": r["source"]} for r in cursor]


async def translate_with_ensemble(client: ZolaiGeminiOpenAIClient, zolai: str, english: str) -> Dict:
    prompt = f"""Translate this Zolai (Tedim Chin) word to Myanmar/Burmese script.

Zolai: {zolai}
English: {english}

Reply with ONLY the Myanmar translation (no explanation, no quotes)."""

    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=False)
            myanmar = result.strip().strip('"').strip("'")
            if myanmar and any('\u1000' <= c <= '\u109f' for c in myanmar):
                votes[model] = myanmar
            await asyncio.sleep(DELAY_BETWEEN_CALLS)
        except Exception as e:
            print(f"  Warning: {model} failed for {zolai}: {e}")
            await asyncio.sleep(2)

    if not votes:
        return {"translation": None, "confidence": 0.0, "models_used": 0}

    vote_counts = {}
    for model, translation in votes.items():
        vote_counts[translation] = vote_counts.get(translation, 0) + 1

    winner = max(vote_counts, key=vote_counts.get)
    confidence = vote_counts[winner] / len(votes)
    return {"translation": winner, "confidence": confidence, "models_used": len(votes)}


def log_audit(conn: sqlite3.Connection, word: str, old_val: str, new_val: str, conf: float, models: int):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, 0, ?, ?, ?, ?, ?)""",
        ("dictionary", "myanmar", old_val, new_val, now,
         f"batch_fill_myanmar: conf={conf:.2f}, models={models}")
    )


async def run_batch(limit: int = BATCH_SIZE, max_batches: int = 0):
    client = ZolaiGeminiOpenAIClient(rate_limit_rpm=10, rate_limit_burst=2)
    await client.init()

    progress = load_progress()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    batch_num = progress["batches_run"]
    total_translated = progress["translated"]
    total_skipped = progress["skipped"]
    total_failed = progress["failed"]

    try:
        while not _shutdown:
            if max_batches > 0 and batch_num >= max_batches:
                print(f"Reached max batches ({max_batches}). Stopping.")
                break

            entries = get_missing_entries(conn, limit)
            if not entries:
                print("✅ No more entries to translate. Done!")
                break

            batch_num += 1
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num} | {len(entries)} entries | Total translated: {total_translated}")
            print(f"{'='*60}")

            batch_translated = 0
            batch_skipped = 0
            batch_failed = 0

            for i, entry in enumerate(entries):
                if _shutdown:
                    break

                zolai = entry["zolai"]
                english = entry["english"]

                # Resume check
                row = c.execute("SELECT myanmar FROM dictionary WHERE zolai = ? AND is_deleted = 0", (zolai,)).fetchone()
                if row and row[0]:
                    batch_skipped += 1
                    continue

                print(f"[{i+1}/{len(entries)}] {zolai} ({english[:40]})", end=" ")

                result = await translate_with_ensemble(client, zolai, english)

                if result["translation"]:
                    old_val = row[0] if row else ""
                    c.execute("""
                        UPDATE dictionary
                        SET myanmar = ?, update_remarks = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE zolai = ? AND (myanmar IS NULL OR myanmar = '') AND is_deleted = 0
                    """, (result["translation"],
                          f"batch(conf={result['confidence']:.2f},m={result['models_used']})",
                          zolai))
                    if c.rowcount > 0:
                        batch_translated += 1
                        log_audit(conn, zolai, old_val, result["translation"],
                                  result["confidence"], result["models_used"])
                        print(f"✓ {result['translation']} ({result['confidence']:.0%})")
                    else:
                        print("- already done")
                        batch_skipped += 1
                else:
                    print("✗ failed")
                    batch_failed += 1

                if (i + 1) % COMMIT_EVERY == 0:
                    conn.commit()

                if (i + 1) % PROGRESS_EVERY == 0:
                    pct = (i + 1) / len(entries) * 100
                    print(f"  --- Batch progress: {i+1}/{len(entries)} ({pct:.0f}%) ---")

            conn.commit()
            total_translated += batch_translated
            total_skipped += batch_skipped
            total_failed += batch_failed

            progress.update({
                "translated": total_translated,
                "skipped": total_skipped,
                "failed": total_failed,
                "batches_run": batch_num,
                "last_run": datetime.now(timezone.utc).isoformat(),
            })
            save_progress(progress)

            print(f"\nBatch {batch_num} done: +{batch_translated} translated, {batch_skipped} skipped, {batch_failed} failed")
            print(f"Running totals: {total_translated} translated, {total_skipped} skipped, {total_failed} failed")

    finally:
        conn.commit()
        conn.close()
        await client.close()
        progress.update({
            "translated": total_translated,
            "skipped": total_skipped,
            "failed": total_failed,
            "batches_run": batch_num,
            "last_run": datetime.now(timezone.utc).isoformat(),
        })
        save_progress(progress)
        print(f"\n📊 Final: {total_translated} translated, {total_skipped} skipped, {total_failed} failed across {batch_num} batches")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch fill Myanmar for dictionary ZO→EN")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help="Entries per batch")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches (0=unlimited)")
    args = parser.parse_args()
    await run_batch(limit=args.limit, max_batches=args.max_batches)


if __name__ == "__main__":
    asyncio.run(main())
