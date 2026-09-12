#!/usr/bin/env python3
"""
Gemini Morphological Enhancement — Analyze morphology of complex words.
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
    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def analyze_morphology(
    client: object,
    word: str,
    english: str,
) -> dict | None:
    prompt = (
        "Task: Break down the morphology of this Zolai word.\n"
        f"Word: {word}\n"
        f"English: {english}\n"
        "Rules: Zolai is agglutinative, SOV language.\n"
        "Output JSON:\n"
        '{"root": "...", "prefix": "", "suffix": "", '
        '"morphemes": ["root"], "POS": "NOUN"}'
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
    morphemes = data.get("morphemes", [])
    if isinstance(morphemes, str):
        morphemes = [m.strip() for m in morphemes.split(",") if m.strip()]

    root = data.get("root", "")
    pos = data.get("POS", data.get("pos", ""))

    if not morphemes and not root:
        print(f"  WARN ({word}): no morphemes in response")
        return None

    return {
        "word": word,
        "morphemes": json.dumps(morphemes, ensure_ascii=False),
        "root": root,
        "POS": pos.upper() if pos else "",
        "analysis_json": json.dumps(data, ensure_ascii=False),
    }


async def run(args: argparse.Namespace) -> None:
    conn = get_db()
    ensure_table(conn)

    existing = {
        row[0]
        for row in conn.execute("SELECT word FROM morph_verified").fetchall()
    }

    # Words with 4+ syllables from vocab (actual Zolai words)
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

    words = [(w, eng or "", freq) for w, eng, freq in polysyllabic if w not in existing]

    print(f"Words to analyze: {len(words)} (from {len(polysyllabic)} long words)")
    client = _build_client()
    analyzed = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(f"  [DRY] {word:25s} (freq={freq}) → {eng[:30]}")
            analyzed += 1
            continue

        result = await analyze_morphology(client, word, eng)
        if result:
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO morph_verified "
                "(word, morphemes, root, POS, analysis_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (result["word"], result["morphemes"], result["root"],
                 result["POS"], result["analysis_json"]),
            )
            conn.commit()
            conn.close()
            analyzed += 1
            morphemes = json.loads(result["morphemes"])
            print(
                f"  {word:25s} → root={result['root']:15s} "
                f"POS={result['POS']:6s} morphemes={len(morphemes)}"
            )
        await asyncio.sleep(1)

    print(f"\n✅ Done. Analyzed {analyzed} words.")
    if hasattr(client, "close"):
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze morphology of complex Zolai words via Gemini"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
