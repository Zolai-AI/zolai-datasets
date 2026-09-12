#!/usr/bin/env python3
"""
Gemini POS Gold Dataset — Generate gold-standard POS tags from Bible verses.
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


async def pos_tag_verse(
    voter: EnsembleVoter,
    sentence: str,
    ref: str,
) -> tuple[dict, float] | None:
    """POS tag a sentence using ensemble voting."""
    result = await voter.vote_pos_sentence(sentence)
    parsed = result.get("result")
    if not parsed:
        print(f"  ERROR ({ref}): no valid response")
        return None

    pairs = parsed if isinstance(parsed, list) else []
    tokens = [p[0] for p in pairs if isinstance(p, list) and len(p) >= 2]
    tags = [p[1] for p in pairs if isinstance(p, list) and len(p) >= 2]

    return {
        "sentence": sentence,
        "tokens": json.dumps(tokens, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "source_verse": ref,
    }, result["confidence"]


async def run(args: argparse.Namespace) -> None:
    if not HAS_ENSEMBLE:
        print("ERROR: ensemble_voter module not found in zolai-ai-local.")
        return

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

    voter = EnsembleVoter(strategy=args.strategy)
    await voter.init()

    tagged = 0

    for ref, zo in rows:
        if ref in existing:
            continue
        if args.dry_run:
            print(f"  [DRY] {ref}: {zo[:60]}...")
            tagged += 1
            continue

        result = await pos_tag_verse(voter, zo, ref)
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
                    f"gemini-ensemble({args.strategy},{conf:.2f})",
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

    print(f"\nDone. Tagged {tagged} verses.")
    await voter.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate gold POS tags from Bible verses via Gemini"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--strategy",
        choices=["fast", "accurate", "full", "reasoning"],
        default="fast",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
