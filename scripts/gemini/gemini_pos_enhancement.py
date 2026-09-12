#!/usr/bin/env python3
"""
Gemini POS Enhancement — Verify POS tags for ambiguous/rare words.
Uses EnsembleVoter with multi-model ensemble voting (configurable).
"""
import asyncio
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


async def verify_word(
    voter: EnsembleVoter,
    word: str,
    english: str,
    freq: int,
) -> tuple[dict, float] | None:
    """Verify POS for a word using ensemble voting."""
    result = await voter.vote_pos(word, english)
    parsed = result.get("result")
    if not parsed or not parsed.get("pos"):
        print(f"  ERROR ({word}): no valid POS response")
        return None

    pos = parsed["pos"].upper()
    conf = result["confidence"]

    return {
        "word": word,
        "pos_tag": pos,
        "confidence": float(parsed.get("confidence", 1.0)) * conf,
        "reason": parsed.get("reason", ""),
    }, conf


async def run(args: argparse.Namespace) -> None:
    if not HAS_ENSEMBLE:
        print("ERROR: ensemble_voter module not found in zolai-ai-local.")
        return

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

    voter = EnsembleVoter(strategy=args.strategy)
    await voter.init()
    verified = 0

    for word, eng, freq in words:
        if args.dry_run:
            print(f"  [DRY] {word:20s} -> {eng[:40]}")
            verified += 1
            continue

        result = await verify_word(voter, word, eng, freq)
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
                f"  {word:20s} -> {data['pos_tag']:6s} "
                f"(conf={data['confidence']:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\nDone. Verified {verified} words.")
    await voter.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify POS tags for ambiguous/rare Zolai words"
        )
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument(
        "--strategy",
        choices=["fast", "accurate", "full", "reasoning"],
        default="fast",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
