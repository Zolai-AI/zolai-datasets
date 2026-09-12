#!/usr/bin/env python3
"""
Gemini Morphological Enhancement — Analyze morphology of complex words.
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
CREATE TABLE IF NOT EXISTS morph_verified (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    morphemes TEXT NOT NULL,
    root TEXT,
    POS TEXT,
    analysis_json TEXT,
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
    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
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


async def analyze_morphology(
    client: ZolaiGeminiOpenAIClient,
    word: str,
    english: str,
) -> tuple[dict, float] | None:
    """Analyze morphology using 3-model ensemble voting."""
    prompt = (
        "Task: Break down the morphology of this Zolai word.\n"
        f"Word: {word}\n"
        f"English: {english}\n"
        "Rules: Zolai is agglutinative, SOV language.\n"
        "Output JSON:\n"
        '{"root": "...", "prefix": "", "suffix": "", '
        '"morphemes": ["root"], "POS": "NOUN"}'
    )
    votes = {}
    for model in ENSEMBLE_MODELS:
        try:
            result = await client.ask(model, prompt, use_system_prompt=True)
            parsed = _extract_json(result)
            if parsed and (parsed.get("morphemes") or parsed.get("root")):
                votes[model] = parsed
        except Exception as exc:
            print(f"  WARN ({word}) {model}: {exc}")
        await asyncio.sleep(1)

    if not votes:
        print(f"  ERROR ({word}): no models returned valid response")
        return None

    final = majority_vote(votes)
    root_votes = [v.get("root", "") for v in votes.values()]
    agreement = sum(1 for r in root_votes if r == final.get("root", ""))
    confidence = agreement / len(ENSEMBLE_MODELS)

    morphemes = final.get("morphemes", [])
    if isinstance(morphemes, str):
        morphemes = [
            m.strip() for m in morphemes.split(",") if m.strip()
        ]

    root = final.get("root", "")
    pos = final.get("POS", final.get("pos", ""))

    if not morphemes and not root:
        print(f"  WARN ({word}): no morphemes in response")
        return None

    return {
        "word": word,
        "morphemes": json.dumps(morphemes, ensure_ascii=False),
        "root": root,
        "POS": pos.upper() if pos else "",
        "analysis_json": json.dumps(final, ensure_ascii=False),
    }, confidence


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    existing = {
        row[0]
        for row in conn.execute(
            "SELECT word FROM morph_verified"
        ).fetchall()
    }

    polysyllabic = conn.execute(
        "SELECT v.headword, v.english, v.frequency "
        "FROM vocab v "
        "INNER JOIN dictionary d ON d.zolai = v.headword "
        "WHERE LENGTH(v.headword) >= 14 "
        "AND v.headword NOT LIKE '% %' "
        "AND v.headword NOT LIKE '%/%' "
        "AND v.headword NOT LIKE '%,%' "
        "AND v.frequency > 2 "
        "ORDER BY v.frequency DESC, RANDOM() LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()

    words = [
        (w, eng or "", freq)
        for w, eng, freq in polysyllabic
        if w not in existing
    ]

    print(
        f"Words to analyze: {len(words)} "
        f"(from {len(polysyllabic)} long words)"
    )

    client = await _build_client()
    await client.init()
    analyzed = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(
                f"  [DRY] {word:25s} "
                f"(freq={freq}) → {eng[:30]}"
            )
            analyzed += 1
            continue

        result = await analyze_morphology(client, word, eng)
        if result:
            data, conf = result
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO morph_verified "
                "(word, morphemes, root, POS, analysis_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data["word"],
                    data["morphemes"],
                    data["root"],
                    data["POS"],
                    data["analysis_json"],
                ),
            )
            conn.commit()
            conn.close()
            analyzed += 1
            morphemes = json.loads(data["morphemes"])
            print(
                f"  {word:25s} → root={data['root']:15s} "
                f"POS={data['POS']:6s} "
                f"morphemes={len(morphemes)} "
                f"(confidence={conf:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\n✅ Done. Analyzed {analyzed} words.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze morphology of complex Zolai words via Gemini"
        )
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
