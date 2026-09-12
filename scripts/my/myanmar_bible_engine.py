#!/usr/bin/env python3
"""
Myanmar Bible Engine — Analyze Judson Bible with ZO-MY-EN parallel support.

Usage:
    python myanmar_bible_engine.py --book GEN --chapter 1 --verse 1
    python myanmar_bible_engine.py --search ဘုရား
    python myanmar_bible_engine.py --parallel GEN 1 1
    python myanmar_bible_engine.py --stats
"""
import os
import sqlite3

WORKSPACE = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DATA = os.path.join(WORKSPACE, "data")
DB_PATH = os.path.join(DATA, "zolai.db")


def get_db():
    """Connect to SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def get_verse(book, chapter, verse):
    """Get parallel verse (ZO + MY + EN)."""
    conn = get_db()
    cur = conn.execute(
        """SELECT ref, book, chapter, verse, zo_tdb77, zo_tedim2010, en_kjv, myanmar
        FROM bible_verses
        WHERE book = ? AND chapter = ? AND verse = ?""",
        (book, int(chapter), int(verse)),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def search_bible_my(query, limit=10):
    """Search Judson Bible by Myanmar text."""
    conn = get_db()
    cur = conn.execute(
        """SELECT ref, zo_tdb77, en_kjv, myanmar
        FROM bible_verses
        WHERE myanmar LIKE ? AND myanmar IS NOT NULL
        LIMIT ?""",
        (f"%{query}%", limit),
    )
    results = [dict(r) for r in cur.fetchall()]
    conn.close()
    return results


def book_stats():
    """Get stats per book for Myanmar Bible."""
    conn = get_db()
    cur = conn.execute(
        """SELECT book,
               COUNT(*) as total,
               SUM(CASE WHEN myanmar IS NOT NULL AND myanmar != '' THEN 1 ELSE 0 END) as with_my
        FROM bible_verses
        GROUP BY book
        ORDER BY MIN(rowid)"""
    )
    results = [dict(r) for r in cur.fetchall()]
    conn.close()
    return results


def parallel_display(book, chapter, verse):
    """Display parallel verse with interlinear."""
    v = get_verse(book, chapter, verse)
    if not v:
        print(f"Verse not found: {book}.{chapter}.{verse}")
        return

    print(f"\n{'=' * 60}")
    print(f"  {v['ref']}")
    print(f"{'=' * 60}")
    if v.get("myanmar"):
        print(f"\n  MY: {v['myanmar']}")
    if v.get("zo_tdb77"):
        print(f"  ZO: {v['zo_tdb77']}")
    if v.get("zo_tedim2010"):
        print(f"  Z2: {v['zo_tedim2010']}")
    if v.get("en_kjv"):
        print(f"  EN: {v['en_kjv']}")
    print()


def parallel_chapter(book, chapter, max_verses=30):
    """Display entire chapter in parallel."""
    conn = get_db()
    cur = conn.execute(
        """SELECT ref, zo_tdb77, en_kjv, myanmar
        FROM bible_verses
        WHERE book = ? AND chapter = ?
        ORDER BY verse
        LIMIT ?""",
        (book, int(chapter), max_verses),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        print(f"No verses found for {book} chapter {chapter}")
        return

    print(f"\n{'=' * 70}")
    print(f"  {book} Chapter {chapter} — {len(rows)} verses")
    print(f"{'=' * 70}")

    for row in rows:
        print(f"\n  {row['ref']}")
        if row.get("myanmar"):
            print(f"    MY: {row['myanmar']}")
        if row.get("zo_tdb77"):
            print(f"    ZO: {row['zo_tdb77']}")
        if row.get("en_kjv"):
            print(f"    EN: {row['en_kjv']}")

    print()


def overall_stats():
    """Print overall Myanmar Bible coverage."""
    conn = get_db()
    cur = conn.execute(
        """SELECT COUNT(*) as total,
               SUM(CASE WHEN myanmar IS NOT NULL AND myanmar != '' THEN 1 ELSE 0 END) as with_my
        FROM bible_verses"""
    )
    row = cur.fetchone()
    conn.close()

    total = row["total"] or 0
    with_my = row["with_my"] or 0
    pct = (with_my * 100 // total) if total > 0 else 0

    print(f"\n  Overall: {with_my}/{total} verses have Myanmar ({pct}%)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Myanmar Bible Engine")
    parser.add_argument("--book", help="Book code (e.g., GEN)")
    parser.add_argument("--chapter", type=int, help="Chapter number")
    parser.add_argument("--verse", type=int, help="Verse number")
    parser.add_argument("--search", help="Search Myanmar text")
    parser.add_argument(
        "--parallel",
        nargs=3,
        metavar=("BOOK", "CHAPTER", "VERSE"),
        help="Show parallel verse",
    )
    parser.add_argument("--chapter-parallel", nargs=2, metavar=("BOOK", "CHAPTER"),
                        help="Show entire chapter in parallel")
    parser.add_argument("--stats", action="store_true", help="Show per-book stats")
    args = parser.parse_args()

    if args.stats:
        stats = book_stats()
        print(f"\n  {'Book':8s} {'Total':>6s} {'MY':>6s} {'Coverage':>8s}")
        print("  " + "-" * 30)
        for s in stats:
            cov = s["with_my"] * 100 // s["total"] if s["total"] > 0 else 0
            print(f"  {s['book']:8s} {s['total']:>6d} {s['with_my']:>6d} {cov:>7d}%")
        overall_stats()
        print()
    elif args.search:
        results = search_bible_my(args.search)
        print(f"\n  Search: '{args.search}' — {len(results)} results\n")
        for r in results:
            print(f"  {r['ref']}")
            print(f"    MY: {r.get('myanmar', '')[:80]}")
            print(f"    ZO: {r.get('zo_tdb77', '')[:80]}")
            print(f"    EN: {r.get('en_kjv', '')[:80]}")
            print()
    elif args.parallel:
        parallel_display(
            args.parallel[0], int(args.parallel[1]), int(args.parallel[2])
        )
    elif args.chapter_parallel:
        parallel_chapter(args.chapter_parallel[0], int(args.chapter_parallel[1]))
    elif args.book and args.chapter and args.verse:
        parallel_display(args.book, args.chapter, args.verse)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
