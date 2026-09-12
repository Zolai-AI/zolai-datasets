#!/usr/bin/env python3
"""Gemini Data Enrichment Pipeline — Consensus Voting (9 Models).

Uses all 9 Gemini models with majority-vote consensus to:
  Mode 1: Fill missing Myanmar translations (batch 50)
  Mode 2: Verify dictionary accuracy (batch 30)
  Mode 3: Identify/fix unknown words (batch 30)

All results logged to training_runs table.
Rate limited: 2s between calls, 3 retries with backoff.

Usage:
  python3 gemini_data_learning.py --mode myanmar --limit 50
  python3 gemini_data_learning.py --mode verify --limit 30
  python3 gemini_data_learning.py --mode unknowns --limit 30
  python3 gemini_data_learning.py --mode all --limit 50
"""
import asyncio
import os
import sqlite3
import sys
import time
from collections import Counter

# ── Gemini client import ───────────────────────────────────
BIBLE_DIR = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai",
    "zolai-datasets/scripts/bible",
)
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)
from gemini_cookies import get_gemini_client

DB_PATH = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai", "data/zolai.db"
)
MAX_RETRIES = 3
RATE_LIMIT = 2  # seconds between calls

# ALL 9 models for consensus voting
MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
    "gemini-3-flash-thinking",
    "gemini-3-flash-plus",
    "gemini-3-flash-thinking-plus",
    "gemini-3-pro-advanced",
    "gemini-3-flash-advanced",
    "gemini-3-flash-thinking-advanced",
]


def _get_conn() -> sqlite3.Connection:
    """Get a database connection with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


async def _call_gemini(
    client, prompt: str, model: str = "gemini-3-flash"
) -> tuple:
    """Call Gemini with retry + exponential backoff."""
    delay = 5
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            output = await client.generate_content(
                prompt=prompt, model=model
            )
            elapsed = time.time() - start
            text = output.text or ""
            if "<ElicitationsGroup" in text:
                text = text[
                    : text.index("<ElicitationsGroup")
                ].strip()
            return text.strip(), elapsed
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                return f"ERROR: {type(e).__name__}: {e}", 0
    return f"ERROR: {last_err}", 0


def _log_run(
    model: str,
    dataset: str,
    count: int,
    metrics: dict,
    status: str = "completed",
) -> None:
    """Log a run to training_runs table."""
    import json

    conn = _get_conn()
    conn.execute(
        "INSERT INTO training_runs "
        "(model_name, dataset_name, entry_count, "
        "metrics_json, status) VALUES (?, ?, ?, ?, ?)",
        (model, dataset, count, json.dumps(metrics), status),
    )
    conn.commit()
    conn.close()


# ── Consensus voting helper ────────────────────────────────
async def _consensus_translate(
    client, prompt: str
) -> tuple:
    """All 9 models respond, return majority-voted answer."""
    answers = []
    for model in MODELS:
        text, _ = await _call_gemini(client, prompt, model)
        await asyncio.sleep(RATE_LIMIT)
        if not text.startswith("ERROR") and text.strip():
            first_line = text.strip().split("\n")[0].strip()
            if first_line:
                answers.append(first_line)

    if not answers:
        return None, 0

    counter = Counter(answers)
    most_common, count = counter.most_common(1)[0]
    return most_common, count


# ── Mode 1: Fill Myanmar Translations ─────────────────────
async def _fill_myanmar(
    client, limit: int = 50
) -> dict:
    """Batch-translate missing Myanmar entries via consensus."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, zolai, english_clean "
        "FROM dictionary "
        "WHERE (myanmar IS NULL OR myanmar = '') "
        "AND english_clean IS NOT NULL "
        "AND LENGTH(zolai) > 1 "
        "LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "mode": "fill_myanmar",
            "total": 0, "updated": 0, "errors": 0,
        }

    updated = 0
    errors = 0

    for i, row in enumerate(rows):
        entry_id, zolai, english = row
        prompt = (
            f"Translate this Zolai word to Burmese/Myanmar.\n"
            f"Word: {zolai} (English: {english})\n"
            f"Reply with ONLY the Myanmar translation."
        )
        consensus, agreement = await _consensus_translate(
            client, prompt
        )

        if consensus and agreement >= 3:
            conn = _get_conn()
            conn.execute(
                "UPDATE dictionary "
                "SET myanmar = ?, updated_at = "
                "datetime('now') WHERE id = ?",
                (consensus, entry_id),
            )
            conn.commit()
            conn.close()
            updated += 1
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"{zolai} → {consensus} "
                f"(agreement: {agreement}/9)"
            )
        else:
            errors += 1
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"{zolai} — no consensus "
                f"({agreement}/9)"
            )

    metrics = {
        "total": len(rows),
        "updated": updated,
        "errors": errors,
        "consensus_agreement": f"{updated}/{len(rows)}",
        "models_used": len(MODELS),
    }
    _log_run("consensus-9", "fill_myanmar", updated, metrics)
    return {
        "mode": "fill_myanmar",
        "total": len(rows),
        "updated": updated,
        "errors": errors,
    }


# ── Mode 2: Verify Dictionary Accuracy ────────────────────
async def _verify_accuracy(
    client, limit: int = 30
) -> dict:
    """Verify high-frequency word translations via consensus."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT d.id, d.zolai, d.english_clean, v.frequency "
        "FROM dictionary d "
        "JOIN vocab v ON v.headword = d.zolai "
        "WHERE d.english_clean IS NOT NULL "
        "AND v.frequency > 100 "
        "ORDER BY v.frequency DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "mode": "verify_accuracy",
            "total": 0, "correct": 0, "incorrect": 0,
        }

    correct = 0
    incorrect = 0
    corrections = []

    for i, row in enumerate(rows):
        entry_id, zolai, english, _freq = row
        prompt = (
            "You are a Zolai (Tedim Chin) language expert.\n"
            "Is this translation correct?\n\n"
            f"Word: {zolai}\n"
            f"Our translation: {english}\n\n"
            "Answer: correct OR incorrect "
            "(with correct translation if wrong)\n"
            "Reply with ONLY one line: "
            "correct or incorrect: <translation>"
        )
        consensus, agreement = await _consensus_translate(
            client, prompt
        )

        if not consensus:
            continue

        text_lower = consensus.lower().strip()
        if text_lower.startswith("correct"):
            correct += 1
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"✅ {zolai}: {english}"
            )
        else:
            incorrect += 1
            suggested = (
                consensus.split(":", 1)[1].strip()
                if ":" in consensus else consensus
            )
            corrections.append({
                "id": entry_id,
                "zolai": zolai,
                "our_english": english,
                "suggestion": suggested,
                "agreement": agreement,
            })
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"❌ {zolai}: {english} → {suggested} "
                f"(agreement: {agreement}/9)"
            )

    metrics = {
        "total": len(rows),
        "correct": correct,
        "incorrect": incorrect,
        "corrections": corrections[:10],
        "models_used": len(MODELS),
    }
    _log_run("consensus-9", "verify_accuracy", len(rows), metrics)
    return {
        "mode": "verify_accuracy",
        "total": len(rows),
        "correct": correct,
        "incorrect": incorrect,
        "corrections": corrections,
    }


# ── Mode 3: Identify Unknown Words ────────────────────────
async def _identify_unknowns(
    client, limit: int = 30
) -> dict:
    """Find entries with bad English and ask all models."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, zolai, english_clean "
        "FROM dictionary "
        "WHERE english_clean IS NOT NULL "
        "AND LENGTH(zolai) > 2 "
        "AND ("
        "  english_clean LIKE '%[%' "
        "  OR english_clean LIKE '%ref:%' "
        "  OR english_clean LIKE '%verse%' "
        "  OR LENGTH(english_clean) < 2 "
        "  OR zolai = english_clean "
        ") "
        "ORDER BY RANDOM() LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "mode": "identify_unknowns",
            "total": 0, "fixed": 0,
        }

    fixed = 0
    fixes = []

    for i, row in enumerate(rows):
        entry_id, zolai, english = row
        prompt = (
            "What does this Zolai word mean in English?\n"
            f"Word: {zolai}\n"
            "Context: This appears in Bible Zolai text.\n\n"
            "Reply with ONLY the English translation."
        )
        consensus, agreement = await _consensus_translate(
            client, prompt
        )

        if (
            consensus
            and consensus.lower() != zolai.lower()
            and len(consensus) > 1
            and agreement >= 3
        ):
            conn = _get_conn()
            conn.execute(
                "UPDATE dictionary "
                "SET english_clean = ?, updated_at = "
                "datetime('now') WHERE id = ?",
                (consensus, entry_id),
            )
            conn.commit()
            conn.close()
            fixed += 1
            fixes.append({
                "zolai": zolai,
                "old_english": english,
                "new_english": consensus,
                "agreement": agreement,
            })
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"✅ {zolai}: {english} → {consensus} "
                f"(agreement: {agreement}/9)"
            )
        else:
            print(
                f"    [{i + 1}/{len(rows)}] "
                f"⚠️  {zolai} — no consensus "
                f"({agreement}/9)"
            )

    metrics = {
        "total": len(rows),
        "fixed": fixed,
        "fixes": fixes[:10],
        "models_used": len(MODELS),
    }
    _log_run("consensus-9", "identify_unknowns", fixed, metrics)
    return {
        "mode": "identify_unknowns",
        "total": len(rows),
        "fixed": fixed,
        "fixes": fixes,
    }


# ── Main ───────────────────────────────────────────────────
def main() -> None:
    """Run data enrichment pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Gemini Data Enrichment — Consensus Voting"
    )
    parser.add_argument(
        "--mode",
        choices=["myanmar", "verify", "unknowns", "all"],
        default="all",
        help="Enrichment mode",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Max entries per mode",
    )
    args = parser.parse_args()

    start = time.time()
    print("=" * 60)
    print("  GEMINI DATA ENRICHMENT — CONSENSUS VOTING")
    print("=" * 60)
    print(f"  DB:     {DB_PATH}")
    print(f"  Mode:   {args.mode}")
    print(f"  Limit:  {args.limit} per mode")
    print(f"  Models: {len(MODELS)} (majority vote)")
    print("=" * 60)

    client = get_gemini_client()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        if args.mode in ("myanmar", "all"):
            print("\n── Mode 1: Fill Myanmar (consensus) ──")
            r = loop.run_until_complete(
                _fill_myanmar(client, args.limit)
            )
            print(
                f"  Updated: {r['updated']}/{r['total']}"
            )

        if args.mode in ("verify", "all"):
            print("\n── Mode 2: Verify Accuracy (consensus) ──")
            r = loop.run_until_complete(
                _verify_accuracy(client, args.limit)
            )
            print(
                f"  Correct: {r['correct']}/{r['total']}"
            )
            print(f"  Incorrect: {r['incorrect']}")
            if r.get("corrections"):
                print("  Top corrections:")
                for c in r["corrections"][:5]:
                    print(
                        f"    {c['zolai']}: "
                        f"{c['our_english']} → "
                        f"{c['suggestion']}"
                    )

        if args.mode in ("unknowns", "all"):
            print("\n── Mode 3: Identify Unknowns (consensus) ──")
            r = loop.run_until_complete(
                _identify_unknowns(client, args.limit)
            )
            print(f"  Fixed: {r['fixed']}/{r['total']}")
    finally:
        loop.close()

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print("  ENRICHMENT COMPLETE")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
