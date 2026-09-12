#!/usr/bin/env python3
"""
Gemini Embedding Validation — Create word similarity test set from Bible co-occurrence.
Uses local AI package with fallback to requests.
"""
import asyncio
import json
import os
import random
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
CREATE TABLE IF NOT EXISTS word_similarity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word1 TEXT NOT NULL,
    word2 TEXT NOT NULL,
    english1 TEXT,
    english2 TEXT,
    similarity REAL NOT NULL,
    reason TEXT,
    source TEXT DEFAULT 'gemini',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word1, word2)
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
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _generate_pairs(conn: sqlite3.Connection, limit: int) -> list[tuple]:
    """Generate word pairs from Bible co-occurrence."""
    # Pick random verses that have 2+ aligned words
    verse_rows = conn.execute(
        "SELECT ref FROM word_alignments "
        "WHERE zolai_word IS NOT NULL AND zolai_word != '' "
        "GROUP BY ref HAVING COUNT(*) >= 2 "
        "ORDER BY RANDOM() LIMIT ?",
        (limit * 5,),
    ).fetchall()

    pairs: dict[tuple[str, str], tuple[str, str]] = {}
    for (ref,) in verse_rows:
        words = conn.execute(
            "SELECT zolai_word, english_word "
            "FROM word_alignments "
            "WHERE ref = ? AND zolai_word IS NOT NULL AND zolai_word != ''",
            (ref,),
        ).fetchall()
        if len(words) < 2:
            continue
        w1, w2 = random.sample(words, 2)
        key = tuple(sorted([w1[0], w2[0]]))
        if key[0] != key[1] and key not in pairs:
            pairs[key] = (w1[1] or "", w2[1] or "")
        if len(pairs) >= limit:
            break

    return [(k[0], k[1], v[0], v[1]) for k, v in pairs.items()]


async def rate_similarity(
    client: object,
    word1: str,
    english1: str,
    word2: str,
    english2: str,
) -> dict | None:
    prompt = (
        "Task: Rate semantic similarity between these Zolai words (0.0 to 1.0).\n"
        f"Word 1: {word1} ({english1})\n"
        f"Word 2: {word2} ({english2})\n"
        "Output JSON: {\"similarity\": 0.85, \"reason\": \"...\"}"
    )
    try:
        if HAS_LOCAL and hasattr(client, "ask"):
            result = await client.ask(
                "gemini-3-flash", prompt, use_system_prompt=True
            )
        else:
            result = await client.ask("gemini-2.0-flash", prompt)
    except Exception as exc:
        print(f"  ERROR ({word1}↔{word2}): {exc}")
        return None

    data = _extract_json(result)
    sim = data.get("similarity")
    if sim is None:
        print(f"  WARN ({word1}↔{word2}): no similarity in response")
        return None

    return {
        "word1": word1,
        "word2": word2,
        "english1": english1,
        "english2": english2,
        "similarity": float(sim),
        "reason": data.get("reason", ""),
    }


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    existing = {
        tuple(row)
        for row in conn.execute(
            "SELECT word1, word2 FROM word_similarity"
        ).fetchall()
    }

    pairs = _generate_pairs(conn, args.limit)
    conn.close()

    # Filter already-done
    todo = [
        (w1, w2, e1, e2)
        for w1, w2, e1, e2 in pairs
        if tuple(sorted([w1, w2])) not in existing
    ]

    print(f"Pairs to rate: {len(todo)} (from {len(pairs)} generated, {len(existing)} existing)")
    client = _build_client()
    rated = 0

    for w1, w2, e1, e2 in todo:
        if args.dry_run:
            print(f"  [DRY] {w1:15s} ↔ {w2:15s}")
            rated += 1
            continue

        result = await rate_similarity(client, w1, e1, w2, e2)
        if result:
            conn = get_db()
            conn.execute(
                "INSERT OR IGNORE INTO word_similarity "
                "(word1, word2, english1, english2, similarity, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (result["word1"], result["word2"], result["english1"],
                 result["english2"], result["similarity"], result["reason"]),
            )
            conn.commit()
            conn.close()
            rated += 1
            print(
                f"  {w1:15s} ↔ {w2:15s} "
                f"sim={result['similarity']:.2f}"
            )
        await asyncio.sleep(1)

    print(f"\n✅ Done. Rated {rated} pairs.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create word similarity test set via Gemini"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
