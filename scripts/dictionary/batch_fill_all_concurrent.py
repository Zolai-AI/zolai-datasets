#!/usr/bin/env python3
"""
Unified concurrent batch fill — Gemini API parallel, DB writes sequential.

Replaces three separate sequential scripts with ONE concurrent script:
  - dictionary (ZO→EN)     → Myanmar translation
  - dictionary_en_zo (EN→ZO) → Myanmar translation
  - vocabulary              → Myanmar translation (cross-ref first, then Gemini)

Architecture:
  1. Read missing entries from ALL 3 tables simultaneously
  2. Send Gemini API calls concurrently (asyncio.gather + semaphore)
  3. Write results to DB sequentially (one connection, one writer)

Features:
- Resume: skips entries already having Myanmar
- Cross-reference: fills vocabulary from dictionary table first (free)
- Concurrency: configurable parallel Gemini calls via semaphore
- Graceful shutdown: SIGINT/SIGTERM finish current batch
- Audit: logs all changes to data_audit_log
- Progress: saves state to JSON, prints per-batch summary
"""

import asyncio
import sqlite3
import json
import os
import sys
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient

DB_PATH = Path(os.environ.get("DATA", "/home/peter/Documents/Projects/zolai-ai/data")) / "zolai.db"
SCRIPT_DIR = Path(__file__).parent
PROGRESS_FILE = SCRIPT_DIR / "progress_unified_concurrent.json"

# Defaults (overridable via CLI)
DEFAULT_CONCURRENCY = 5
DEFAULT_BATCH_SIZE = 200
DEFAULT_MAX_BATCHES = 0  # 0 = unlimited
COMMIT_EVERY = 20
PROGRESS_EVERY = 50
DELAY_BETWEEN = 0.3

# Graceful shutdown
_shutdown = False
def _signal_handler(sig, frame):
    global _shutdown
    print("\n⚠️  Graceful shutdown requested. Finishing current batch...")
    _shutdown = True
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ---------------------------------------------------------------------------
# Task definitions: select, update, prompt, input/key extraction
# ---------------------------------------------------------------------------
TASKS = {
    "dict_zo_en": {
        "label": "Dictionary ZO→EN",
        "select": """
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
        """,
        "update": """
            UPDATE dictionary
            SET myanmar = ?, update_remarks = ?, updated_at = CURRENT_TIMESTAMP
            WHERE zolai = ? AND (myanmar IS NULL OR myanmar = '') AND is_deleted = 0
        """,
        "prompt_template": """Translate this Zolai (Tedim Chin) word to Myanmar/Burmese script.

Zolai: {zolai}
English: {english}

Reply with ONLY the Myanmar translation (no explanation, no quotes).""",
        "input_fn": lambda row: {"zolai": row[0], "english": row[1] or ""},
        "update_key": lambda row: (row[0],),  # zolai
        "update_args_fn": lambda myanmar, conf, key: (myanmar, f"batch(conf={conf:.2f})", *key),
        "audit_table": "dictionary",
    },
    "dict_en_zo": {
        "label": "Dictionary EN→ZO",
        "select": """
            SELECT e.id, e.headword, e.pos, e.source
            FROM dictionary_en_zo e
            WHERE (e.myanmar IS NULL OR e.myanmar = '')
            AND e.headword IS NOT NULL AND e.headword != ''
            ORDER BY RANDOM()
            LIMIT ?
        """,
        "update": """
            UPDATE dictionary_en_zo
            SET myanmar = ?, update_remarks = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND (myanmar IS NULL OR myanmar = '')
        """,
        "prompt_template": """Translate this English word to Myanmar/Burmese script.

English: {english}{ref_note}

Reply with ONLY the Myanmar translation (no explanation, no quotes).""",
        "input_fn": lambda row: {"english": row[1], "id": row[0]},
        "update_key": lambda row: (row[0],),  # id
        "update_args_fn": lambda myanmar, conf, key: (myanmar, f"batch(conf={conf:.2f})", *key),
        "audit_table": "dictionary_en_zo",
    },
    "vocab": {
        "label": "Vocabulary",
        "select": """
            SELECT v.id, v.headword, v.english
            FROM vocabulary v
            WHERE (v.myanmar IS NULL OR v.myanmar = '')
            AND v.headword IS NOT NULL AND v.headword != ''
            AND v.english IS NOT NULL AND v.english != ''
            ORDER BY v.frequency DESC, RANDOM()
            LIMIT ?
        """,
        "update": """
            UPDATE vocabulary
            SET myanmar = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND (myanmar IS NULL OR myanmar = '')
        """,
        "prompt_template": """Translate this Zolai (Tedim Chin) word to Myanmar/Burmese script.

Zolai: {zolai}
English: {english}

Reply with ONLY the Myanmar translation (no explanation, no quotes).""",
        "input_fn": lambda row: {"zolai": row[1], "english": row[2], "id": row[0]},
        "update_key": lambda row: (row[0],),  # id
        "update_args_fn": lambda myanmar, conf, key: (myanmar, *key),
        "audit_table": "vocabulary",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {
        "dict_zo_en": {"translated": 0, "skipped": 0, "failed": 0},
        "dict_en_zo": {"translated": 0, "skipped": 0, "failed": 0},
        "vocab":      {"translated": 0, "skipped": 0, "failed": 0},
        "batches_run": 0,
        "cross_filled": 0,
    }

def save_progress(state: dict):
    PROGRESS_FILE.write_text(json.dumps(state, indent=2))

def validate_myanmar(text: str) -> bool:
    """Check if text contains Myanmar script characters."""
    if not text:
        return False
    return any('\u1000' <= c <= '\u109f' for c in text)

def log_audit(conn: sqlite3.Connection, table: str, word: str,
              old_val: str, new_val: str, reason: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO data_audit_log (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, 0, ?, ?, ?, ?, ?)""",
        (table, "myanmar", old_val, new_val, now, reason)
    )


# ---------------------------------------------------------------------------
# Cross-fill: populate vocabulary.myanmar from dictionary table (free)
# ---------------------------------------------------------------------------
def cross_fill_vocabulary(conn: sqlite3.Connection) -> int:
    """Fill vocabulary Myanmar from dictionary table where headword matches zolai."""
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


# ---------------------------------------------------------------------------
# Gemini translation (single call, concurrency-controlled by semaphore)
# ---------------------------------------------------------------------------
async def translate_one(client: ZolaiGeminiOpenAIClient, prompt: str,
                        semaphore: asyncio.Semaphore) -> Dict:
    """Translate a single word via Gemini, with concurrency limit."""
    async with semaphore:
        try:
            result = await client.ask("gemini-3-flash", prompt, use_system_prompt=False)
            myanmar = result.strip().strip('"').strip("'")
            if validate_myanmar(myanmar):
                return {"translation": myanmar, "confidence": 1.0}
            return {"translation": None, "confidence": 0.0}
        except Exception as e:
            await asyncio.sleep(1)
            return {"translation": None, "confidence": 0.0, "error": str(e)}


# ---------------------------------------------------------------------------
# EN→ZO cross-reference: look up existing Myanmar from ZO→EN table
# ---------------------------------------------------------------------------
def get_en_zo_ref_myanmar(conn: sqlite3.Connection, headword: str) -> str | None:
    """Try to find an existing Myanmar translation via the ZO→EN dictionary."""
    row = conn.execute(
        "SELECT myanmar FROM dictionary WHERE english_clean = ? AND myanmar IS NOT NULL AND myanmar != '' AND is_deleted = 0 LIMIT 1",
        (headword,)
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Main concurrent loop
# ---------------------------------------------------------------------------
async def run_unified(limit: int = DEFAULT_BATCH_SIZE, max_batches: int = DEFAULT_MAX_BATCHES,
                      concurrency: int = DEFAULT_CONCURRENCY):
    """Main loop: read all 3 tables, translate concurrently, write sequentially."""

    # Phase 0: Cross-fill vocabulary from dictionary (free, instant)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cross_filled = cross_fill_vocabulary(conn)
    conn.close()
    print(f"✅ Cross-filled {cross_filled} vocabulary entries from dictionary table")

    # Phase 1: Init Gemini client
    client = ZolaiGeminiOpenAIClient(rate_limit_rpm=10, rate_limit_burst=5)
    await client.init()
    semaphore = asyncio.Semaphore(concurrency)

    # Single DB connection for sequential writes
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    progress = load_progress()
    progress["cross_filled"] = progress.get("cross_filled", 0) + cross_filled

    # Per-table cumulative stats (resume from progress)
    stats = {}
    for tt in TASKS:
        stats[tt] = {
            "translated": progress[tt]["translated"],
            "skipped": progress[tt]["skipped"],
            "failed": progress[tt]["failed"],
        }

    batch_num = progress["batches_run"]

    try:
        while not _shutdown:
            if max_batches > 0 and batch_num >= max_batches:
                print(f"\nReached max batches ({max_batches}). Stopping.")
                break

            batch_num += 1
            total_this_round = 0

            # Phase 2: Read missing entries from ALL 3 tables
            all_tasks = {}  # task_type -> [(key, inputs, prompt)]
            for task_type, task in TASKS.items():
                rows = conn.execute(task["select"], (limit,)).fetchall()
                if not rows:
                    continue

                entries = []
                for row in rows:
                    inputs = task["input_fn"](row)
                    key = task["update_key"](row)

                    # EN→ZO: add cross-reference note if available
                    extra = {}
                    if task_type == "dict_en_zo":
                        ref = get_en_zo_ref_myanmar(conn, inputs.get("english", ""))
                        extra["ref_note"] = f"\nExisting Zolai→Myanmar translation for this word: {ref}" if ref else ""

                    prompt = task["prompt_template"].format(**inputs, **extra)
                    entries.append((key, inputs, prompt))
                all_tasks[task_type] = entries
                total_this_round += len(entries)

            if not all_tasks:
                print("\n✅ All tables fully translated!")
                break

            print(f"\n{'='*60}")
            print(f"BATCH {batch_num} | {total_this_round} entries across {len(all_tasks)} tables")
            for tt, entries in all_tasks.items():
                print(f"  {TASKS[tt]['label']}: {len(entries)}")
            print(f"{'='*60}")

            # Phase 3: Translate ALL entries concurrently via Gemini
            all_prompts = []  # [(task_type, key, inputs, prompt)]
            for task_type, entries in all_tasks.items():
                for key, inputs, prompt in entries:
                    all_prompts.append((task_type, key, inputs, prompt))

            async def translate_with_context(item):
                task_type, key, inputs, prompt = item
                result = await translate_one(client, prompt, semaphore)
                return task_type, key, inputs, result

            results = await asyncio.gather(
                *[translate_with_context(item) for item in all_prompts],
                return_exceptions=True
            )

            # Phase 4: Write results to DB sequentially
            batch_translated = {tt: 0 for tt in TASKS}
            batch_failed = {tt: 0 for tt in TASKS}
            written = 0

            for result in results:
                if isinstance(result, Exception):
                    continue
                task_type, key, inputs, translation = result
                task = TASKS[task_type]

                if translation.get("translation"):
                    args = task["update_args_fn"](
                        translation["translation"],
                        translation["confidence"],
                        key,
                    )
                    conn.execute(task["update"], args)
                    batch_translated[task_type] += 1
                    written += 1
                    # Audit log
                    log_audit(conn, task["audit_table"], str(key[0]),
                              "", translation["translation"],
                              f"batch_concurrent(conf={translation['confidence']:.2f})")
                else:
                    batch_failed[task_type] += 1

                # Periodic commit during write phase
                if written % COMMIT_EVERY == 0 and written > 0:
                    conn.commit()

            conn.commit()

            # Update cumulative stats
            for tt in TASKS:
                stats[tt]["translated"] += batch_translated[tt]
                stats[tt]["failed"] += batch_failed[tt]

            # Print batch summary
            print(f"\nBatch {batch_num} done:")
            for tt in TASKS:
                t = batch_translated[tt]
                f = batch_failed[tt]
                print(f"  {TASKS[tt]['label']}: +{t} translated, {f} failed")

            # Save progress
            for tt in TASKS:
                progress[tt]["translated"] = stats[tt]["translated"]
                progress[tt]["skipped"] = stats[tt]["skipped"]
                progress[tt]["failed"] = stats[tt]["failed"]
            progress["batches_run"] = batch_num
            progress["last_run"] = datetime.now(timezone.utc).isoformat()
            save_progress(progress)

    finally:
        conn.commit()
        conn.close()
        await client.close()

        # Final summary
        print(f"\n{'='*60}")
        print("📊 FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"  Cross-filled from dictionary: {progress.get('cross_filled', 0)}")
        total_t = 0
        total_f = 0
        for tt in TASKS:
            t = stats[tt]["translated"]
            f = stats[tt]["failed"]
            total_t += t
            total_f += f
            print(f"  {TASKS[tt]['label']}: {t} translated, {f} failed")
        print(f"  ─────────────────────────")
        print(f"  TOTAL: {total_t} translated, {total_f} failed")
        print(f"  Batches run: {batch_num}")
        print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unified concurrent batch fill — Myanmar translations for all 3 tables")
    parser.add_argument("--limit", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Entries per table per batch round (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--max-batches", type=int, default=DEFAULT_MAX_BATCHES,
                        help="Max batch rounds (0=unlimited)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Max concurrent Gemini API calls (default: {DEFAULT_CONCURRENCY})")
    args = parser.parse_args()

    print(f"🚀 Unified Concurrent Batch Fill")
    print(f"   DB: {DB_PATH}")
    print(f"   Concurrency: {args.concurrency}")
    print(f"   Batch size: {args.limit} per table")
    print(f"   Max batches: {args.max_batches or 'unlimited'}")

    await run_unified(
        limit=args.limit,
        max_batches=args.max_batches,
        concurrency=args.concurrency,
    )


if __name__ == "__main__":
    asyncio.run(main())
