#!/usr/bin/env python3
"""
Batch Myanmar translation filler for dictionary_en_zo table.
Translates English headwords to Myanmar via Gemini.

Features:
- Resume: skips entries already having Myanmar
- Cross-reference: uses dictionary ZO→EN table for existing translations
- Progress: saves state to JSON
- Audit: logs all changes to data_audit_log
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
PROGRESS_FILE = Path(__file__).parent / "progress_dict_en_zo.json"
BATCH_SIZE = 500
COMMIT_EVERY = 10
PROGRESS_EVERY = 50
DELAY_BETWEEN_CALLS = 1.0

ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
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
    return {"translated": 0, "skipped": 0, "failed": 0, "batches_run": 0}

def save_progress(state: dict):
    PROGRESS_FILE.write_text(json.dumps(state, indent=2))


def get_missing_entries(conn: sqlite3.Connection, limit: int = BATCH_SIZE) -> List[Dict]:
    """Get EN→ZO entries missing Myanmar, with cross-ref to ZO→EN table."""
    cursor = conn.execute("""
        SELECT e.id, e.headword, e.pos, e.source
        FROM dictionary_en_zo e
        WHERE (e.myanmar IS NULL OR e.myanmar = '')
        AND e.headword IS NOT NULL AND e.headword != ''
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))

    entries = []
    for row in cursor:
        headword = row["headword"]
        # Cross-reference: try to find Myanmar from ZO→EN table
        ref = conn.execute(
            "SELECT myanmar FROM dictionary WHERE english_clean = ? AND myanmar IS NOT NULL AND myanmar != '' LIMIT 1",
            (headword,)
        ).fetchone()

        entries.append({
            "id": row["id"],
            "headword": headword,
            "pos": row["pos"] or "",
            "source": row["source"],
            "ref_myanmar": ref[0] if ref else None,
        })
    return entries


async def translate_with_ensemble(client: ZolaiGeminiOpenAIClient, headword: str, ref_myanmar: str = None) -> Dict:
    ref_note = f"\nExisting Zolai→Myanmar translation for this word: {ref_myanmar}" if ref_myanmar else ""

    prompt = f"""Translate this English word to Myanmar/Burmese script.

English: {headword}{ref_note}

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
            print(f"  Warning: {model} failed for {headword}: {e}")
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
        ("dictionary_en_zo", "myanmar", old_val, new_val, now,
         f"batch_fill_en_zo_myanmar: conf={conf:.2f}, models={models}")
    )


async def run_batch(limit: int = BATCH_SIZE, max_batches: int = 0):
    client = ZolaiGeminiOpenAIClient(rate_limit_rpm=10, rate_limit_burst=2)
    await client.init()

    progress = load_progress()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    batch_num = progress["batches_run"]
    total_t = progress["translated"]
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

                hw = entry["headword"]
                ref = entry["ref_myanmar"]

                # Resume check
                row = c.execute("SELECT myanmar FROM dictionary_en_zo WHERE id = ?", (entry["id"],)).fetchone()
                if row and row[0]:
                    bs += 1
                    continue

                print(f"[{i+1}/{len(entries)}] {hw}", end=" ")

                result = await translate_with_ensemble(client, hw, ref)

                if result["translation"]:
                    old_val = row[0] if row else ""
                    c.execute("""
                        UPDATE dictionary_en_zo
                        SET myanmar = ?, update_remarks = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND (myanmar IS NULL OR myanmar = '')
                    """, (result["translation"],
                          f"batch(conf={result['confidence']:.2f},m={result['models_used']})",
                          entry["id"]))
                    if c.rowcount > 0:
                        bt += 1
                        log_audit(conn, hw, old_val, result["translation"],
                                  result["confidence"], result["models_used"])
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
            progress.update({"translated": total_t, "skipped": total_s, "failed": total_f,
                           "batches_run": batch_num, "last_run": datetime.now(timezone.utc).isoformat()})
            save_progress(progress)
            print(f"\nBatch {batch_num}: +{bt} translated, {bs} skipped, {bf} failed")

    finally:
        conn.commit(); conn.close(); await client.close()
        progress.update({"translated": total_t, "skipped": total_s, "failed": total_f,
                       "batches_run": batch_num, "last_run": datetime.now(timezone.utc).isoformat()})
        save_progress(progress)
        print(f"\n📊 Final: {total_t} translated, {total_s} skipped, {total_f} failed")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch fill Myanmar for dictionary EN→ZO")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=0)
    args = parser.parse_args()
    await run_batch(limit=args.limit, max_batches=args.max_batches)

if __name__ == "__main__":
    asyncio.run(main())
