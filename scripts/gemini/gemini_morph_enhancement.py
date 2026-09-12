#!/usr/bin/env python3
"""
Gemini Morphological Enhancement — Analyze morphology of complex words.
Uses EnsembleVoter with multi-model ensemble voting (configurable).
"""
import asyncio
import json
import os
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
    from ensemble_voter import EnsembleVoter

    HAS_ENSEMBLE = True
except ImportError:
    HAS_ENSEMBLE = False

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


async def analyze_morphology(
    voter: EnsembleVoter,
    word: str,
    english: str,
) -> tuple[dict, float] | None:
    """Analyze morphology using ensemble voting."""
    result = await voter.vote_morphology(word)
    parsed = result.get("result")
    if not parsed or not (parsed.get("morphemes") or parsed.get("root")):
        print(f"  ERROR ({word}): no valid morphology response")
        return None

    morphemes = parsed.get("morphemes", [])
    if isinstance(morphemes, str):
        morphemes = [
            m.strip() for m in morphemes.split(",") if m.strip()
        ]

    root = parsed.get("root", "")
    pos = parsed.get("POS", parsed.get("pos", ""))
    conf = result["confidence"]

    return {
        "word": word,
        "morphemes": json.dumps(morphemes, ensure_ascii=False),
        "root": root,
        "POS": pos.upper() if pos else "",
        "analysis_json": json.dumps(parsed, ensure_ascii=False),
    }, conf


async def run(args: argparse.Namespace) -> None:
    if not HAS_ENSEMBLE:
        print("ERROR: ensemble_voter module not found in zolai-ai-local.")
        return

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

    voter = EnsembleVoter(strategy=args.strategy)
    await voter.init()
    analyzed = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(
                f"  [DRY] {word:25s} "
                f"(freq={freq}) -> {eng[:30]}"
            )
            analyzed += 1
            continue

        result = await analyze_morphology(voter, word, eng)
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
                f"  {word:25s} -> root={data['root']:15s} "
                f"POS={data['POS']:6s} "
                f"morphemes={len(morphemes)} "
                f"(confidence={conf:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\nDone. Analyzed {analyzed} words.")
    await voter.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze morphology of complex Zolai words via Gemini"
        )
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--strategy",
        choices=["fast", "accurate", "full", "reasoning"],
        default="fast",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
