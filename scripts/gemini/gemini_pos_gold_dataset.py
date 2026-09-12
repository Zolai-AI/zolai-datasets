#!/usr/bin/env python3
"""
Gemini POS Gold Dataset — Generate gold-standard POS tags from Bible verses.
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
POS_TAGS = (
    "NOUN VERB ADJ ADV PRON DET POST CONJ PART NUM INTJ PUNCT"
)

# ── Table creation ────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pos_gold (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence TEXT NOT NULL,
    tokens TEXT NOT NULL,
    tags TEXT NOT NULL,
    source_verse TEXT,
    source TEXT DEFAULT 'gemini',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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


# ── Fallback requests client ──────────────────────────────────────────────────
class RequestsGeminiClient:
    """Minimal synchronous Gemini client using requests."""

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
        client = ZolaiGeminiOpenAIClient(use_zvs_context=True)
        return client
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "No Gemini client available. "
            "Install zolai-ai-local or set GEMINI_API_KEY."
        )
    return RequestsGeminiClient(api_key)


def _extract_json(text: str) -> list:
    """Extract JSON array from Gemini response."""
    match = re.search(r"\[[\s\S]*?\]", text)
    if match:
        return json.loads(match.group())
    return []


async def pos_tag_verse(
    client: object,
    sentence: str,
    ref: str,
) -> dict | None:
    prompt = (
        "Task: POS Tag this Zolai sentence word by word.\n"
        f"Rules: {POS_TAGS}\n"
        "Output format: JSON array of [word, tag] pairs.\n"
        f"Sentence: {sentence}"
    )
    try:
        if HAS_LOCAL and hasattr(client, "ask"):
            result = await client.ask("gemini-3-flash", prompt, use_system_prompt=True)
        else:
            result = await client.ask("gemini-2.0-flash", prompt)
    except Exception as exc:
        print(f"  ERROR ({ref}): {exc}")
        return None

    pairs = _extract_json(result)
    if not pairs:
        print(f"  WARN ({ref}): no JSON pairs in response")
        return None

    tokens = [p[0] for p in pairs if isinstance(p, list) and len(p) >= 2]
    tags = [p[1] for p in pairs if isinstance(p, list) and len(p) >= 2]
    return {
        "sentence": sentence,
        "tokens": json.dumps(tokens, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "source_verse": ref,
    }


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    # Check if we already have data for dedup
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT source_verse FROM pos_gold"
        ).fetchall()
    }

    # Fetch verses
    rows = conn.execute(
        "SELECT ref, zo_tdb77 FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL AND zo_tdb77 != '' "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()

    print(f"Fetched {len(rows)} verses, {len(existing)} already tagged.")
    client = _build_client()
    tagged = 0

    for ref, zo in rows:
        if ref in existing:
            continue
        if args.dry_run:
            print(f"  [DRY] {ref}: {zo[:60]}...")
            tagged += 1
            continue

        result = await pos_tag_verse(client, zo, ref)
        if result:
            conn = get_db()
            conn.execute(
                "INSERT INTO pos_gold (sentence, tokens, tags, source_verse) "
                "VALUES (?, ?, ?, ?)",
                (result["sentence"], result["tokens"], result["tags"], result["source_verse"]),
            )
            conn.commit()
            conn.close()
            tagged += 1
            tokens = json.loads(result["tokens"])
            print(f"  {ref}: {len(tokens)} tokens tagged")
        await asyncio.sleep(1)

    print(f"\n✅ Done. Tagged {tagged} verses.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate gold POS tags from Bible verses via Gemini"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
