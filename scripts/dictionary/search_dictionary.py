#!/usr/bin/env python3
"""Look up a Tedim Zolai word in the core database.

Reads the canonical ``data/zolai.db`` (the same store ``zolai-core`` owns and the
API serves). Engine-agnostic: set ``ZOLAI_DB_URL`` to a ``postgresql://…`` URL to
query a PostgreSQL deployment instead — no code change.

Usage:
    python scripts/dictionary/search_dictionary.py pasian
    python scripts/dictionary/search_dictionary.py hello --en
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Dual-engine DB access: sqlite by default, ZOLAI_DB_URL switches to postgres.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect, db_path, row_to_dict

DB_PATH = db_path()

# Only the columns callers actually print — keeps output stable as the core
# schema grows and avoids dumping audit/internal fields.
_COLUMNS = (
    "zolai, english, english_clean, myanmar, pos, pos_canonical, syllables, "
    "syllable_count, source, source_type, review_status, confidence"
)


def _rows(cur) -> list[dict]:
    return [row_to_dict(r) for r in cur.fetchall()]


def search(query: str, *, english: bool = False) -> int:
    """Print matches for a Zolai headword (or an English term with ``--en``).

    Returns the number of entries shown, so callers can exit non-zero on a miss.
    """
    if not DB_PATH.exists() and not os.environ.get("ZOLAI_DB_URL", "").strip():
        print(f"Error: Database {DB_PATH} not found.")
        print("The core database lives beside the workspace in data/zolai.db;")
        print("set ZOLAI_DB_PATH, ZOLAI_DATA_ROOT or ZOLAI_DB_URL to relocate it.")
        return 0

    query = query.strip()
    if not query:
        print("Nothing to search for.")
        return 0

    conn = connect(DB_PATH)
    c = conn.cursor()
    results: list[dict] = []

    # 1. Exact headword (ZO → EN)
    c.execute(
        f"SELECT {_COLUMNS} FROM dictionary "
        "WHERE lower(zolai) = ? AND COALESCE(is_deleted, 0) = 0",
        (query.lower(),),
    )
    results.extend(_rows(c))

    # 2. English → Zolai via the reverse dictionary
    if not results or english:
        c.execute(
            "SELECT headword, translations, translations_clean, pos, myanmar "
            "FROM dictionary_en_zo WHERE lower(headword) = ?",
            (query.lower(),),
        )
        for r in _rows(c):
            results.append(
                {
                    "zolai": r["translations_clean"] or r["translations"],
                    "english": r["headword"],
                    "pos": r["pos"],
                    "myanmar": r["myanmar"],
                    "_via": "dictionary_en_zo",
                }
            )

    # 3. Senses/examples from the meanings table, keyed by headword
    if results:
        c.execute(
            "SELECT dictionary_id, meaning_en, example_zo, example_en "
            "FROM dictionary_meanings WHERE dictionary_id IN "
            "(SELECT id FROM dictionary WHERE lower(zolai) = ?) LIMIT 10",
            (query.lower(),),
        )
        meanings = _rows(c)
        if meanings:
            results[0]["_meanings"] = meanings

    # 4. Prefix fallback — Zolai is agglutinative, so an exact miss is common
    if not results:
        c.execute(
            f"SELECT {_COLUMNS} FROM dictionary "
            "WHERE zolai LIKE ? AND COALESCE(is_deleted, 0) = 0 LIMIT 10",
            (f"{query.lower()}%",),
        )
        results = _rows(c)
        if results:
            print(f"No exact match for '{query}'. Prefix matches:")
        else:
            # Last resort: substring, still bounded so it cannot scan the whole
            # 84k-row table into memory.
            c.execute(
                f"SELECT {_COLUMNS} FROM dictionary "
                "WHERE zolai LIKE ? AND COALESCE(is_deleted, 0) = 0 LIMIT 10",
                (f"%{query.lower()}%",),
            )
            results = _rows(c)
            print(f"No exact or prefix match for '{query}'. Substring matches:" if results
                  else f"No matches for '{query}'.")

    for data in results:
        print("-" * 60)
        print(f"WORD:        {data.get('zolai') or data.get('english')}")
        if data.get("english"):
            print(f"ENGLISH:     {data['english']}")
        if data.get("english_clean"):
            print(f"  (clean)    {data['english_clean']}")
        if data.get("pos") or data.get("pos_canonical"):
            print(f"POS:         {data.get('pos_canonical') or data['pos']}")
        if data.get("syllables"):
            print(f"SYLLABLES:   {data['syllables']}"
                  + (f" ({data['syllable_count']})" if data.get("syllable_count") else ""))
        if data.get("myanmar"):
            print(f"MYANMAR:     {data['myanmar']}")
        if data.get("source"):
            print(f"SOURCE:      {data['source']}"
                  + (f" [{data['source_type']}]" if data.get("source_type") else ""))
        if data.get("_via"):
            print(f"FOUND VIA:   {data['_via']}")
        for m in data.get("_meanings", []):
            if m.get("meaning_en"):
                print(f"MEANING:     {m['meaning_en']}")
            if m.get("example_zo"):
                print(f"  e.g. ZO:   {m['example_zo']}")
            if m.get("example_en"):
                print(f"       EN:   {m['example_en']}")

    conn.close()
    return len(results)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("Usage: python scripts/dictionary/search_dictionary.py <word> [--en]")
        raise SystemExit(2)
    search(" ".join(args), english="--en" in sys.argv)
