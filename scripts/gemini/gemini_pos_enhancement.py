#!/usr/bin/env python3
"""
Gemini POS Enhancement — Verify POS tags for ambiguous/rare words.
Uses Gemini directly with multi-model ensemble voting (3 models).
"""
import asyncio
import json
import os
import re
import sqlite3
import sys
import argparse
from pathlib import Path

sys.path.insert(
    0,
    os.environ.get(
        "ZOLAI_AI_LOCAL",
        "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local",
    ),
)

try:
    from gemini.client_openai import ZolaiGeminiOpenAIClient

    HAS_LOCAL = True
except ImportError:
    HAS_LOCAL = False

DB_PATH = Path(os.environ.get("DATA", "data")) / "zolai.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pos_verified (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    pos_tag TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    reason TEXT,
    source TEXT DEFAULT 'gemini',
    verified_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        return json.loads(match.group())
    return {}


# ── Multi-model ensemble voting ────────────────────────────────────────────────
ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
]


def majority_vote(votes: dict[str, dict]) -> dict:
    """Return the most common response across models (majority vote)."""
    counts: dict[str, int] = {}
    for resp in votes.values():
        key = json.dumps(resp, sort_keys=True, ensure_ascii=False)
        counts[key] = counts.get(key, 0) + 1
    best_key = max(counts, key=lambda k: counts[k])
    return json.loads(best_key)


async def _build_client() -> ZolaiGeminiOpenAIClient:
    """Build Gemini client — requires zolai-ai-local package."""
    if not HAS_LOCAL:
        raise RuntimeError(
            "zolai-ai-local package not found. "
            "Install or set ZOLAI_AI_LOCAL env var."
        )
    return ZolaiGeminiOpenAIClient(use_zvs_context=True)


async def verify_word(
    client: ZolaiGeminiOpenAIClient,
    word: str,
    english: str,
    freq: int,
) -> tuple[dict, float] | None:
    """Verify POS for a word using 3-model ensemble voting."""
    prompt = (
        "Task: What is the POS tag for this Zolai word?\n"
        f"Word: {word}\n"
        f"English: {english}\n"
        f"Bible frequency: {freq}\n"
        'Output JSON: {"pos": "NOUN", "confidence": 0.9, '
        '"reason": "..."}\n'
        "Valid tags: NOUN, VERB, ADJ, ADV, PRON, "
        "DET, POST, CONJ, PART, NUM, INTJ"
    )
    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=True)
            parsed = _extract_json(result)
            if parsed and parsed.get("pos"):
                votes[model] = parsed
        except Exception as exc:
            print(f"  WARN ({word}) {model}: {exc}")
        await asyncio.sleep(1)

    if not votes:
        print(f"  ERROR ({word}): no models returned valid response")
        return None

    final = majority_vote(votes)
    agreement = sum(
        1 for v in votes.values()
        if v.get("pos", "").upper() == final.get("pos", "").upper()
    )
    confidence = agreement / len(ENSEMBLE_MODELS)

    pos = final.get("pos", "").upper()
    if not pos:
        print(f"  WARN ({word}): no pos in response")
        return None

    return {
        "word": word,
        "pos_tag": pos,
        "confidence": float(final.get("confidence", 1.0)) * confidence,
        "reason": final.get("reason", ""),
    }, confidence


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    no_pos = conn.execute(
        "SELECT zolai, english_clean FROM dictionary "
        "WHERE (pos IS NULL OR pos = '') "
        "AND english_clean IS NOT NULL AND english_clean != '' "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit // 2,),
    ).fetchall()

    low_freq = conn.execute(
        "SELECT headword, english FROM vocab "
        "WHERE frequency < 5 AND frequency > 0 "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit // 2,),
    ).fetchall()

    existing = {
        row[0]
        for row in conn.execute(
            "SELECT word FROM pos_verified"
        ).fetchall()
    }
    conn.close()

    words = []
    for word, eng in no_pos:
        if word not in existing:
            words.append((word, eng or "", 0))
    for word, eng in low_freq:
        if word not in existing:
            words.append((word, eng or "", 0))

    print(
        f"Words to verify: {len(words)} "
        f"(no_pos: {len(no_pos)}, low_freq: {len(low_freq)})"
    )

    client = await _build_client()
    await client.init()
    verified = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(f"  [DRY] {word:20s} → {eng[:40]}")
            verified += 1
            continue

        result = await verify_word(client, word, eng, freq)
        if result:
            data, _conf = result
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO pos_verified "
                "(word, pos_tag, confidence, reason) "
                "VALUES (?, ?, ?, ?)",
                (
                    data["word"],
                    data["pos_tag"],
                    data["confidence"],
                    data["reason"],
                ),
            )
            conn.commit()
            conn.close()
            verified += 1
            print(
                f"  {word:20s} → {data['pos_tag']:6s} "
                f"(conf={data['confidence']:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\n✅ Done. Verified {verified} words.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify POS tags for ambiguous/rare Zolai words"
        )
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
