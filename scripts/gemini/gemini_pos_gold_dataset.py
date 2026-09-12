#!/usr/bin/env python3
"""
Gemini POS Gold Dataset — Generate gold-standard POS tags from Bible verses.
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


def _extract_json(text: str) -> list:
    """Extract JSON array from Gemini response."""
    match = re.search(r"\[[\s\S]*?\]", text)
    if match:
        return json.loads(match.group())
    return []


# ── Multi-model ensemble voting ────────────────────────────────────────────────
ENSEMBLE_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
]


def majority_vote(votes: dict[str, list]) -> list:
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


async def pos_tag_verse(
    client: ZolaiGeminiOpenAIClient,
    sentence: str,
    ref: str,
) -> tuple[dict, float] | None:
    """POS tag a sentence using 3-model ensemble voting."""
    prompt = (
        "Task: POS Tag this Zolai sentence word by word.\n"
        f"Rules: {POS_TAGS}\n"
        "Output format: JSON array of [word, tag] pairs.\n"
        f"Sentence: {sentence}"
    )
    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=True)
            parsed = _extract_json(result)
            if parsed:
                votes[model] = parsed
        except Exception as exc:
            print(f"  WARN ({ref}) {model}: {exc}")
        await asyncio.sleep(1)

    if not votes:
        print(f"  ERROR ({ref}): no models returned valid response")
        return None

    final_tags = majority_vote(votes)
    confidence = len({json.dumps(v, sort_keys=True) for v in votes.values()}) / len(ENSEMBLE_MODELS)
    confidence = 1.0 - confidence  # More agreement = higher confidence

    pairs = final_tags
    tokens = [p[0] for p in pairs if isinstance(p, list) and len(p) >= 2]
    tags = [p[1] for p in pairs if isinstance(p, list) and len(p) >= 2]

    return {
        "sentence": sentence,
        "tokens": json.dumps(tokens, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "source_verse": ref,
    }, confidence


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    existing = {
        row[0]
        for row in conn.execute(
            "SELECT source_verse FROM pos_gold"
        ).fetchall()
    }

    rows = conn.execute(
        "SELECT ref, zo_tdb77 FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL AND zo_tdb77 != '' "
        "ORDER BY RANDOM() LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()

    print(f"Fetched {len(rows)} verses, {len(existing)} already tagged.")

    client = await _build_client()
    await client.init()

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
            data, conf = result
            conn = get_db()
            conn.execute(
                "INSERT INTO pos_gold "
                "(sentence, tokens, tags, source_verse, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data["sentence"],
                    data["tokens"],
                    data["tags"],
                    data["source_verse"],
                    f"gemini-ensemble({conf:.2f})",
                ),
            )
            conn.commit()
            conn.close()
            tagged += 1
            tokens = json.loads(data["tokens"])
            print(
                f"  {ref}: {len(tokens)} tokens "
                f"tagged (confidence={conf:.2f})"
            )
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
