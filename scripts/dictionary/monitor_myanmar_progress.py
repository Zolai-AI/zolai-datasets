#!/usr/bin/env python3
"""
Monitor Myanmar translation progress across all tables.
Shows current state, rates, and ETA.

Usage:
    python monitor_myanmar_progress.py
    python monitor_myanmar_progress.py --watch 60  # refresh every 60s
"""

import sqlite3
import json
import os
import sys
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("DATA", "/home/peter/Documents/Projects/zolai-ai/data")) / "zolai.db"
SCRIPT_DIR = Path(__file__).parent


def load_progress(filename: str) -> dict:
    f = SCRIPT_DIR / filename
    if f.exists():
        return json.loads(f.read_text())
    return {}


def get_table_stats(conn: sqlite3.Connection) -> dict:
    stats = {}

    # Dictionary ZO→EN
    c = conn.execute("SELECT COUNT(*) FROM dictionary WHERE is_deleted = 0")
    total = c.fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM dictionary WHERE myanmar IS NOT NULL AND myanmar != '' AND is_deleted = 0")
    done = c.fetchone()[0]
    stats["dictionary_zo_en"] = {"total": total, "done": done, "missing": total - done}

    # Dictionary EN→ZO
    c = conn.execute("SELECT COUNT(*) FROM dictionary_en_zo")
    total = c.fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM dictionary_en_zo WHERE myanmar IS NOT NULL AND myanmar != ''")
    done = c.fetchone()[0]
    stats["dictionary_en_zo"] = {"total": total, "done": done, "missing": total - done}

    # Vocabulary
    c = conn.execute("SELECT COUNT(*) FROM zolai_vocabulary")
    total = c.fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM zolai_vocabulary WHERE myanmar IS NOT NULL AND myanmar != ''")
    done = c.fetchone()[0]
    stats["vocabulary"] = {"total": total, "done": done, "missing": total - done}

    return stats


def print_dashboard():
    conn = sqlite3.connect(str(DB_PATH))
    stats = get_table_stats(conn)
    conn.close()

    progress_files = {
        "dictionary_zo_en": "progress_dict_zo_en.json",
        "dictionary_en_zo": "progress_dict_en_zo.json",
        "vocabulary": "progress_vocab.json",
    }

    print(f"\n{'='*70}")
    print(f"📊 MYANMAR TRANSLATION PROGRESS — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    total_missing = 0
    total_done = 0

    for key, label in [("dictionary_zo_en", "Dictionary ZO→EN"),
                        ("dictionary_en_zo", "Dictionary EN→ZO"),
                        ("vocabulary", "Vocabulary")]:
        s = stats[key]
        pct = s["done"] / s["total"] * 100 if s["total"] > 0 else 0
        bar_len = 30
        filled = int(bar_len * s["done"] / s["total"]) if s["total"] > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"\n  {label}")
        print(f"    [{bar}] {pct:.1f}%")
        print(f"    Done: {s['done']:,} | Missing: {s['missing']:,} | Total: {s['total']:,}")

        # Load progress file
        p = load_progress(progress_files.get(key, ""))
        if p:
            print(f"    Batches: {p.get('batches_run', 0)} | "
                  f"Last run: {p.get('last_run', 'never')}")

        total_missing += s["missing"]
        total_done += s["done"]

    print(f"\n{'='*70}")
    overall_pct = total_done / (total_done + total_missing) * 100 if (total_done + total_missing) > 0 else 0
    print(f"  OVERALL: {total_done:,} done / {total_missing:,} missing ({overall_pct:.1f}%)")
    print(f"{'='*70}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Monitor Myanmar translation progress")
    parser.add_argument("--watch", type=int, default=0, help="Refresh interval in seconds (0=once)")
    args = parser.parse_args()

    if args.watch > 0:
        while True:
            print_dashboard()
            time.sleep(args.watch)
    else:
        print_dashboard()


if __name__ == "__main__":
    main()
