#!/usr/bin/env python3
"""
Batch Myanmar translation filler for vocabulary table.
Cross-references dictionary table first, then uses Gemini for remaining.

Features:
- Resume: skips entries already having Myanmar
- Cross-reference: fills from dictionary table first (free)
- Gemini fallback: translates remaining via ensemble
- Progress: saves state to JSON
- Audit: logs all changes
"""

import asyncio
import sqlite3
import json
import os
import sys
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient

DB_PATH = Path(os.environ.get("DATA", "/home/peter/Documents/Projects/zolai-ai/data")) / "zolai.db"
PROGRESS_FILE = Path(__file__).parent / "progress_vocab.json"
BATCH_SIZE = 500
COMMIT_EVERY = 10
PROGRESS_EVERY = 50
DELAY_BETWEEN_CALLS = 0.5

ENSEMBLE_MODELS = [
    "gemini-3-flash",
]

_shutdown = False
def _signal_handler(sig, frame):
    global _shutdown
    print("\n⚠️  Graceful shutdown...")
    _shutdown = True
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"cross_filled": 0, "gemini_translated": 0, "skipped": 0, "failed": 0, "batches_run": 0}

def save_progress(state: dict):
    PROGRESS_FILE.write_text(json.dumps(state, indent=2))


def cross_fill_from_dictionary(conn: sqlite3.Connection) -> int:
    """Fill vocabulary Myanmar from dictionary table where possible."""
    cursor = conn.execute("""
        UPDATE vocabulary
        SET myanmar = (
            SELECT d.myanmar FROM dictionary d
            WHERE d.zolai = vocabulary.headword
            AND d.myanmar IS NOT NULL AND d.myanmar != ''
            AND d.is_deleted = 0
            LIMIT 1
        )
        WHERE (vocabulary.myanmar IS NULL OR vocabulary.myanmar = '')
        AND EXISTS (
            SELECT 1 FROM dictionary d
            WHERE d.zolai = vocabulary.headword
            AND d.myanmar IS NOT NULL AND d.myanmar != ''
            AND d.is_deleted = 0
        )
    """)
    conn.commit()
    return cursor.rowcount


def get_missing_entries(conn: sqlite3.Connection, limit: int = BATCH_SIZE) -> List[Dict]:
    cursor = conn.execute("""
        SELECT v.id, v.headword, v.english, NULL as pos
        FROM vocabulary v
        WHERE (v.myanmar IS NULL OR v.myanmar = '')
        AND v.headword IS NOT NULL AND v.headword != ''
        AND v.english IS NOT NULL AND v.english != ''
        ORDER BY v.frequency DESC, RANDOM()
        LIMIT ?
    """, (limit,))
    return [{"id": r["id"], "zolai": r["headword"], "english": r["english"],
             "pos": r["pos"] or ""} for r in cursor]


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


def log_audit(conn: sqlite3.Connection, word: str, old_val: str, new_val: str, reason: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, 0, ?, ?, ?, ?, ?)""",
        ("vocabulary", "myanmar", old_val, new_val, now, reason)
    )


async def run_batch(limit: int = BATCH_SIZE, max_batches: int = 0):
    # Phase 1: Cross-fill from dictionary (free, instant)
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row
    cross_filled = cross_fill_from_dictionary(conn)
    print(f"✅ Cross-filled {cross_filled} entries from dictionary table")
    conn.close()

    # Phase 2: Gemini translation for remaining
    client = ZolaiGeminiOpenAIClient(rate_limit_rpm=10, rate_limit_burst=2)
    await client.init()

    progress = load_progress()
    progress["cross_filled"] = progress.get("cross_filled", 0) + cross_filled
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row
    c = conn.cursor()

    batch_num = progress["batches_run"]
    total_t = progress["gemini_translated"]
    total_s = progress["skipped"]
    total_f = progress["failed"]

    try:
        while not _shutdown:
            if max_batches > 0 and batch_num >= max_batches:
                break

            entries = get_missing_entries(conn, limit)
            if not entries:
                print("✅ No more entries to translate.")
                break

            batch_num += 1
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num} | {len(entries)} entries | Total: {total_t} translated")
            print(f"{'='*60}")

            bt, bs, bf = 0, 0, 0
            for i, entry in enumerate(entries):
                if _shutdown:
                    break

                zolai = entry["zolai"]
                english = entry["english"]

                row = c.execute("SELECT myanmar FROM vocabulary WHERE id = ?", (entry["id"],)).fetchone()
                if row and row[0]:
                    bs += 1
                    continue

                print(f"[{i+1}/{len(entries)}] {zolai} ({english[:30]})", end=" ")

                result = await translate_with_ensemble(client, zolai, english)

                if result["translation"]:
                    old_val = row[0] if row else ""
                    c.execute("""
                        UPDATE vocabulary
                        SET myanmar = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND (myanmar IS NULL OR myanmar = '')
                    """, (result["translation"], entry["id"]))
                    if c.rowcount > 0:
                        bt += 1
                        log_audit(conn, zolai, old_val, result["translation"],
                                  f"batch(conf={result['confidence']:.2f},m={result['models_used']})")
                        print(f"✓ {result['translation']} ({result['confidence']:.0%})")
                    else:
                        print("- already done")
                        bs += 1
                else:
                    print("✗ failed")
                    bf += 1

                if (i + 1) % COMMIT_EVERY == 0:
                    conn.commit()
                if (i + 1) % PROGRESS_EVERY == 0:
                    print(f"  --- {i+1}/{len(entries)} ({(i+1)/len(entries)*100:.0f}%) ---")

            conn.commit()
            total_t += bt; total_s += bs; total_f += bf
            progress.update({"gemini_translated": total_t, "skipped": total_s, "failed": total_f,
                           "batches_run": batch_num, "last_run": datetime.now(timezone.utc).isoformat()})
            save_progress(progress)
            print(f"\nBatch {batch_num}: +{bt} translated, {bs} skipped, {bf} failed")

    finally:
        conn.commit(); conn.close(); await client.close()
        progress.update({"gemini_translated": total_t, "skipped": total_s, "failed": total_f,
                       "batches_run": batch_num, "last_run": datetime.now(timezone.utc).isoformat()})
        save_progress(progress)
        print(f"\n📊 Final: {progress['cross_filled']} cross-filled + {total_t} gemini-translated, {total_s} skipped, {total_f} failed")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch fill Myanmar for vocabulary")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=0)
    args = parser.parse_args()
    await run_batch(limit=args.limit, max_batches=args.max_batches)

if __name__ == "__main__":
    asyncio.run(main())
