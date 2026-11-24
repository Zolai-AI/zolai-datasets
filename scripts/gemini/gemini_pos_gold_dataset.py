#!/usr/bin/env python3
"""
Gemini POS Gold Dataset — Generate gold-standard POS tags from Bible verses.
Uses EnsembleVoter with multi-model ensemble voting (configurable).
"""
import asyncio
import hashlib
from datetime import datetime, timezone
import json
import os
import sqlite3
import sys
import argparse
from pathlib import Path

# Dual-engine DB access: sqlite by default, ZOLAI_DB_URL switches to postgres.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect, db_path, data_root
# sqlite-only: PRAGMA / AUTOINCREMENT / INSERT OR REPLACE / sqlite_master
# / FTS5 have no PostgreSQL equivalent; run this script on the sqlite engine.

sys.path.insert(
    0,
    os.environ.get(
        "ZOLAI_AI_LOCAL",
        str(data_root().parent / "zolai-ai-local"),
    ),
)

try:
    from ensemble_voter import EnsembleVoter

    HAS_ENSEMBLE = True
except ImportError:
    HAS_ENSEMBLE = False

DB_PATH = db_path()
POS_TAGS = (
    "NOUN VERB ADJ ADV PRON DET POST CONJ PART NUM INTJ PUNCT"
)

# ── Canonical target ─────────────────────────────────────────────────────────
# The core DB already owns this shape: ``canonical_sentences`` holds
# (text, tokens, pos_tags) with provenance in verified_by/source_hash, which is
# what zolai-core reads for sentence-level POS gold. Creating a parallel
# ``pos_gold`` table inside the shared store would leave a second, unroutable
# copy of the same annotation set.
INSERT_SENTENCE_SQL = """
INSERT INTO canonical_sentences
    (text, tokens, pos_tags, source_hash, verified_at, verified_by, version,
     created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def _source_hash(ref: str, tokens_json: str) -> str:
    """16-hex digest matching the ``canonical_sentences.source_hash`` format."""
    return hashlib.sha256(f"{ref}|{tokens_json}".encode("utf-8")).hexdigest()[:16]


def get_db() -> sqlite3.Connection:
    conn = connect(str(DB_PATH))
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_table(conn) -> None:
    """No-op: ``canonical_sentences`` is created and owned by zolai-core.

    Kept so existing call sites read the same; the script must never DDL the
    shared store.
    """
    return


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

    # Provenance is recorded as verified_by='gemini-ensemble:<ref>'; the verse ref
    # itself is no longer a column, so de-duplicate on that marker instead.
    existing = {
        row[0].rsplit(":", 1)[-1]
        for row in conn.execute(
            "SELECT verified_by FROM canonical_sentences "
            "WHERE verified_by LIKE 'gemini-ensemble:%'"
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
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                INSERT_SENTENCE_SQL,
                (
                    data["sentence"],
                    data["tokens"],
                    data["tags"],
                    _source_hash(data["source_verse"], data["tokens"]),
                    now,
                    f"gemini-ensemble:{data['source_verse']}",
                    1,
                    now,
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
