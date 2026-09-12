#!/usr/bin/env python3
"""Gemini Translation Pipeline — Fill missing Myanmar/English data.

Uses Gemini via pcore-brain API to translate missing data.
Stores results with full provenance tracking.

Usage:
    python gemini_translate.py --fill-my --limit 100
    python gemini_translate.py --fill-en --limit 100
    python gemini_translate.py --fill-all --limit 500
    python gemini_translate.py --batch --batch-size 50
    python gemini_translate.py --status
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime, timezone

WORKSPACE = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DATA = os.path.join(WORKSPACE, "data")
DB_PATH = os.path.join(DATA, "zolai.db")

# Gemini API config via pcore-brain
PCORE_BRAIN_URL = os.environ.get(
    "PCORE_BRAIN_URL",
    "https://pcore-brain.peterlianpi.site/v1/chat/completions",
)
PCORE_BRAIN_KEY = os.environ.get(
    "PCORE_BRAIN_KEY",
    "",
)
TRANSLATION_MODEL = "auto"


def get_db() -> sqlite3.Connection:
    """Open SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def find_missing_my(conn: sqlite3.Connection, limit: int = 100) -> list:
    """Find dictionary entries missing Myanmar translations."""
    cur = conn.execute(
        """
        SELECT id, zolai, english FROM dictionary
        WHERE (myanmar IS NULL OR myanmar = '')
          AND english IS NOT NULL AND english != ''
        ORDER BY RANDOM() LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def find_missing_en(conn: sqlite3.Connection, limit: int = 100) -> list:
    """Find entries missing English translations."""
    cur = conn.execute(
        """
        SELECT id, zolai, myanmar FROM dictionary
        WHERE (english IS NULL OR english = '' OR english = '[]')
          AND zolai IS NOT NULL AND zolai != ''
        ORDER BY RANDOM() LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def call_gemini(prompt: str, system_prompt: str | None = None) -> str | None:
    """Call Gemini via pcore-brain API.

    Returns the assistant content string, or None on failure.
    """
    try:
        import requests
    except ImportError:
        print("  ERROR: requests library not installed. pip install requests")
        return None

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            PCORE_BRAIN_URL,
            json={
                "model": TRANSLATION_MODEL,
                "messages": messages,
                "task": "zolai",
                "max_tokens": 200,
                "temperature": 0.1,
            },
            headers={
                "Content-Type": "application/json",
                "x-api-key": PCORE_BRAIN_KEY,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return content.strip() if content else None
        print(f"  API HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  API error: {e}")
    return None


def translate_to_myanmar(zolai: str, english: str) -> str | None:
    """Translate Zolai/English word to Myanmar (Burmese) script."""
    prompt = (
        f"Translate the following Zolai/Tedim Chin word to Myanmar (Burmese) "
        f"script.\n\n"
        f"Zolai word: {zolai}\n"
        f"English meaning: {english}\n\n"
        f"Return ONLY the Myanmar translation, nothing else. "
        f"If multiple meanings, use the most common one separated by /."
    )
    system = (
        "You are a Zolai-Tedim Chin to Myanmar (Burmese) translation expert. "
        "Return ONLY the Myanmar script translation, no explanations."
    )
    result = call_gemini(prompt, system)
    if result:
        # Clean up: strip quotes, take first line only
        result = result.strip().strip('"').strip("'")
        if "\n" in result:
            result = result.split("\n")[0].strip()
        # Remove common prefixes the model might add
        for prefix in [
            "Myanmar:", "Burmese:", "Translation:", "Answer:",
        ]:
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix) :].strip()
    return result if result else None


def translate_to_english(zolai: str, myanmar: str) -> str | None:
    """Translate Zolai/Myanmar word to English."""
    prompt = (
        f"Translate the following Zolai/Tedim Chin word to English.\n\n"
        f"Zolai word: {zolai}\n"
        f"Myanmar text: {myanmar}\n\n"
        f"Return ONLY the English translation, nothing else. "
        f"If multiple meanings, use the most common one."
    )
    system = (
        "You are a Zolai-Tedim Chin to English translation expert. "
        "Return ONLY the English translation, no explanations."
    )
    result = call_gemini(prompt, system)
    if result:
        result = result.strip().strip('"').strip("'")
        if "\n" in result:
            result = result.split("\n")[0].strip()
        for prefix in [
            "English:", "Translation:", "Answer:", "Meaning:",
        ]:
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix) :].strip()
    return result if result else None


def store_translation(
    conn: sqlite3.Connection,
    row_id: int,
    field: str,
    old_value: str | None,
    new_value: str,
    source: str = "gemini_flash",
) -> None:
    """Store translation update with audit provenance."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        f"UPDATE dictionary SET {field} = ?, updated_at = ? WHERE id = ?",
        (new_value, now, row_id),
    )
    conn.execute(
        """INSERT INTO data_audit_log
           (table_name, row_id, field, old_value, new_value, changed_at, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "dictionary",
            row_id,
            field,
            old_value,
            new_value,
            now,
            f"gemini_translation:{source}",
        ),
    )


def fill_missing_my(
    limit: int = 100, dry_run: bool = False
) -> dict[str, int]:
    """Fill missing Myanmar translations. Returns stats dict."""
    conn = get_db()
    entries = find_missing_my(conn, limit)
    total = len(entries)
    print(f"Found {total} entries missing Myanmar translations")

    filled = 0
    skipped = 0
    errors = 0
    for i, row in enumerate(entries, 1):
        row_id = row["id"]
        zolai = row["zolai"]
        english = row["english"]
        # Truncate long english for display
        en_short = english[:40] + ("..." if len(english) > 40 else "")
        print(f"  [{i}/{total}] {zolai} ({en_short})")

        my = translate_to_myanmar(zolai, english)
        if my:
            print(f"    -> {my}")
            if not dry_run:
                store_translation(conn, row_id, "myanmar", None, my)
                conn.commit()
            filled += 1
        else:
            skipped += 1

        # Rate limit: 1 req/sec
        time.sleep(1.0)

    conn.close()
    print(f"\nFilled: {filled}, Skipped: {skipped}, Errors: {errors}")
    return {"filled": filled, "skipped": skipped, "errors": errors}


def fill_missing_en(
    limit: int = 100, dry_run: bool = False
) -> dict[str, int]:
    """Fill missing English translations. Returns stats dict."""
    conn = get_db()
    entries = find_missing_en(conn, limit)
    total = len(entries)
    print(f"Found {total} entries missing English translations")

    filled = 0
    skipped = 0
    errors = 0
    for i, row in enumerate(entries, 1):
        row_id = row["id"]
        zolai = row["zolai"]
        myanmar = row["myanmar"] or ""
        print(f"  [{i}/{total}] {zolai}")

        en = translate_to_english(zolai, myanmar)
        if en:
            print(f"    -> {en}")
            if not dry_run:
                store_translation(conn, row_id, "english", None, en)
                conn.commit()
            filled += 1
        else:
            skipped += 1

        time.sleep(1.0)

    conn.close()
    print(f"\nFilled: {filled}, Skipped: {skipped}, Errors: {errors}")
    return {"filled": filled, "skipped": skipped, "errors": errors}


def show_status() -> None:
    """Show database translation coverage status."""
    conn = get_db()
    with conn:
        total = conn.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0]
        my_filled = conn.execute(
            "SELECT COUNT(*) FROM dictionary "
            "WHERE myanmar IS NOT NULL AND myanmar != ''"
        ).fetchone()[0]
        en_filled = conn.execute(
            "SELECT COUNT(*) FROM dictionary "
            "WHERE english IS NOT NULL AND english != '' AND english != '[]'"
        ).fetchone()[0]
        both = conn.execute(
            "SELECT COUNT(*) FROM dictionary "
            "WHERE myanmar IS NOT NULL AND myanmar != '' "
            "AND english IS NOT NULL AND english != '' AND english != '[]'"
        ).fetchone()[0]

    conn.close()
    my_pct = my_filled / total * 100 if total else 0
    en_pct = en_filled / total * 100 if total else 0
    both_pct = both / total * 100 if total else 0

    print("Dictionary Translation Coverage")
    print("=" * 40)
    print(f"  Total entries:      {total:>7,}")
    print(f"  Myanmar filled:     {my_filled:>7,} ({my_pct:.1f}%)")
    print(f"  English filled:     {en_filled:>7,} ({en_pct:.1f}%)")
    print(f"  Both filled:        {both:>7,} ({both_pct:.1f}%)")
    print(f"  Missing Myanmar:    {total - my_filled:>7,}")
    print(f"  Missing English:    {total - en_filled:>7,}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini Translation Pipeline — fill missing Myanmar/English",
    )
    parser.add_argument(
        "--fill-my", action="store_true",
        help="Fill missing Myanmar translations",
    )
    parser.add_argument(
        "--fill-en", action="store_true",
        help="Fill missing English translations",
    )
    parser.add_argument(
        "--fill-all", action="store_true",
        help="Fill all missing translations (Myanmar + English)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show database translation coverage",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max entries to translate per direction",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview translations without writing to DB",
    )
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if not (args.fill_my or args.fill_en or args.fill_all):
        parser.print_help()
        print("\nExample: python gemini_translate.py --fill-my --limit 50")
        return

    print("Gemini Translation Pipeline")
    print("=" * 40)
    if args.dry_run:
        print("  DRY RUN — no DB writes\n")

    if args.fill_my or args.fill_all:
        print("\n--- Filling Myanmar translations ---\n")
        fill_missing_my(args.limit, args.dry_run)

    if args.fill_en or args.fill_all:
        print("\n--- Filling English translations ---\n")
        fill_missing_en(args.limit, args.dry_run)


if __name__ == "__main__":
    main()
