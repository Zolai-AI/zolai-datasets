#!/usr/bin/env python3
"""
Gemini POS Enhancement — Verify POS tags for ambiguous/rare words.
Uses local AI package with fallback to requests.
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

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

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


class RequestsGeminiClient:
    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    )

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def ask(self, _model: str, prompt: str, **_kw: object) -> str:
        if requests is None:
            raise RuntimeError("requests library not installed")
        resp = requests.post(
            self.API_URL,
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _build_client() -> object:
    if HAS_LOCAL:
        return ZolaiGeminiOpenAIClient(use_zvs_context=True)
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "No Gemini client. Install zolai-ai-local or set GEMINI_API_KEY."
        )
    return RequestsGeminiClient(api_key)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        return json.loads(match.group())
    return {}


async def verify_word(
    client: object, word: str, english: str, freq: int
) -> dict | None:
    prompt = (
        "Task: What is the POS tag for this Zolai word?\n"
        f"Word: {word}\n"
        f"English: {english}\n"
        f"Bible frequency: {freq}\n"
        "Output JSON: {\"pos\": \"NOUN\", \"confidence\": 0.9, \"reason\": \"...\"}\n"
        "Valid tags: NOUN, VERB, ADJ, ADV, PRON, DET, POST, CONJ, PART, NUM, INTJ"
    )
    try:
        if HAS_LOCAL and hasattr(client, "ask"):
            result = await client.ask(
                "gemini-3-flash", prompt, use_system_prompt=True
            )
        else:
            result = await client.ask("gemini-2.0-flash", prompt)
    except Exception as exc:
        print(f"  ERROR ({word}): {exc}")
        return None

    data = _extract_json(result)
    pos = data.get("pos", "")
    if not pos:
        print(f"  WARN ({word}): no pos in response")
        return None

    return {
        "word": word,
        "pos_tag": pos.upper(),
        "confidence": float(data.get("confidence", 1.0)),
        "reason": data.get("reason", ""),
    }


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    # Words with NULL or empty POS in dictionary
    no_pos = conn.execute(
        "SELECT zolai, english_clean FROM dictionary "
        "WHERE (pos IS NULL OR pos = '') "
        "AND english_clean IS NOT NULL AND english_clean != '' "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit // 2,),
    ).fetchall()

    # Low-frequency Bible words (< 5 occurrences)
    low_freq = conn.execute(
        "SELECT headword, english FROM vocab "
        "WHERE frequency < 5 AND frequency > 0 "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit // 2,),
    ).fetchall()

    existing = {
        row[0]
        for row in conn.execute("SELECT word FROM pos_verified").fetchall()
    }
    conn.close()

    words = []
    for word, eng in no_pos:
        if word not in existing:
            words.append((word, eng or "", 0))
    for word, eng in low_freq:
        if word not in existing:
            words.append((word, eng or "", 0))

    print(f"Words to verify: {len(words)} (no_pos: {len(no_pos)}, low_freq: {len(low_freq)})")
    client = _build_client()
    verified = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(f"  [DRY] {word:20s} → {eng[:40]}")
            verified += 1
            continue

        result = await verify_word(client, word, eng, freq)
        if result:
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO pos_verified "
                "(word, pos_tag, confidence, reason) VALUES (?, ?, ?, ?)",
                (result["word"], result["pos_tag"],
                 result["confidence"], result["reason"]),
            )
            conn.commit()
            conn.close()
            verified += 1
            print(
                f"  {word:20s} → {result['pos_tag']:6s} "
                f"(conf={result['confidence']:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\n✅ Done. Verified {verified} words.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify POS tags for ambiguous/rare Zolai words"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
