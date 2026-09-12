#!/usr/bin/env python3
"""
Gemini Embedding Validation — Create word similarity test set from Bible
co-occurrence. Uses EnsembleVoter with multi-model ensemble voting.
"""
import asyncio
import os
import random
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


def _generate_pairs(
    conn: sqlite3.Connection, limit: int
) -> list[tuple]:
    """Generate word pairs from Bible co-occurrence."""
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
            "WHERE ref = ? "
            "AND zolai_word IS NOT NULL AND zolai_word != ''",
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
    voter: EnsembleVoter,
    word1: str,
    english1: str,
    word2: str,
    english2: str,
) -> tuple[dict, float] | None:
    """Rate semantic similarity using ensemble voting."""
    result = await voter.vote_similarity(word1, english1, word2, english2)
    parsed = result.get("result")
    if not parsed or parsed.get("similarity") is None:
        print(f"  ERROR ({word1}<->{word2}): no valid response")
        return None

    conf = result["confidence"]

    return {
        "word1": word1,
        "word2": word2,
        "english1": english1,
        "english2": english2,
        "similarity": float(parsed["similarity"]),
        "reason": parsed.get("reason", ""),
    }, conf


async def run(args: argparse.Namespace) -> None:
    if not HAS_ENSEMBLE:
        print("ERROR: ensemble_voter module not found in zolai-ai-local.")
        return

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

    todo = [
        (w1, w2, e1, e2)
        for w1, w2, e1, e2 in pairs
        if tuple(sorted([w1, w2])) not in existing
    ]

    print(
        f"Pairs to rate: {len(todo)} "
        f"(from {len(pairs)} generated, {len(existing)} existing)"
    )

    voter = EnsembleVoter(strategy=args.strategy)
    await voter.init()
    rated = 0

    for w1, w2, e1, e2 in todo:
        if args.dry_run:
            print(f"  [DRY] {w1:15s} <-> {w2:15s}")
            rated += 1
            continue

        result = await rate_similarity(voter, w1, e1, w2, e2)
        if result:
            data, conf = result
            conn = get_db()
            conn.execute(
                "INSERT OR IGNORE INTO word_similarity "
                "(word1, word2, english1, english2, "
                "similarity, reason, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    data["word1"],
                    data["word2"],
                    data["english1"],
                    data["english2"],
                    data["similarity"],
                    data["reason"],
                    f"gemini-ensemble({args.strategy},{conf:.2f})",
                ),
            )
            conn.commit()
            conn.close()
            rated += 1
            print(
                f"  {w1:15s} <-> {w2:15s} "
                f"sim={data['similarity']:.2f} "
                f"(confidence={conf:.2f})"
            )
        await asyncio.sleep(1)

    print(f"\nDone. Rated {rated} pairs.")
    await voter.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create word similarity test set via Gemini"
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
