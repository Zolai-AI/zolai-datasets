#!/usr/bin/env python3
"""Phase 7: Dedup & Validate — check integrity after integration."""
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"

# ZVS 2018 forbidden forms (lowercase for matching)
ZVS_FORBIDDEN = {
    "pathian": "pasian",
    "ram": "gam",
    "fapa": "tapa",
    "bawipa": "topa",
    "siangpahrang": "kumpipa",
}


def validate(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()
    errors = []

    # 1. Row counts
    tables = [
        "bible_verses", "dictionary", "tongsan_articles",
        "zolai_songs", "translations",
    ]
    print("=== Row Counts ===")
    for t in tables:
        try:
            cur.execute(f"SELECT count(*) FROM [{t}]")
            count = cur.fetchone()[0]
            print(f"  {t}: {count}")
        except sqlite3.OperationalError:
            print(f"  {t}: TABLE NOT FOUND")
            errors.append(f"Table {t} missing")

    # 2. Duplicate refs in bible_verses
    print("\n=== Bible Dedup ===")
    cur.execute(
        "SELECT ref, count(*) c FROM bible_verses GROUP BY ref HAVING c > 1"
    )
    dupes = cur.fetchall()
    if dupes:
        errors.append(f"{len(dupes)} duplicate refs in bible_verses")
        print(f"  DUPLICATES: {len(dupes)}")
        for ref, cnt in dupes[:5]:
            print(f"    {ref}: {cnt}x")
    else:
        print("  No duplicate refs — OK")

    # 3. Duplicate headwords in dictionary
    print("\n=== Dictionary Dedup ===")
    cur.execute(
        "SELECT zolai, count(*) c FROM dictionary GROUP BY zolai HAVING c > 1"
    )
    dupes = cur.fetchall()
    if dupes:
        errors.append(f"{len(dupes)} duplicate headwords in dictionary")
        print(f"  DUPLICATES: {len(dupes)}")
        for hw, cnt in dupes[:5]:
            print(f"    {hw}: {cnt}x")
    else:
        print("  No duplicate headwords — OK")

    # 4. NULL coverage on new bible columns
    print("\n=== Bible Column Coverage ===")
    for col in ["zo_tedim1932", "zo_hcl06", "zo_fcl", "myanmar_judson"]:
        cur.execute(f"SELECT count(*) FROM bible_verses WHERE {col} IS NOT NULL")
        filled = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bible_verses")
        total = cur.fetchone()[0]
        pct = (filled / total * 100) if total else 0
        print(f"  {col}: {filled}/{total} ({pct:.1f}%)")

    # 5. ZVS 2018 check on new Zolai text (sample)
    print("\n=== ZVS 2018 Compliance (sample) ===")
    cur.execute(
        "SELECT ref, zo_tedim1932 FROM bible_verses WHERE zo_tedim1932 IS NOT NULL LIMIT 200"
    )
    violations = 0
    for ref, text in cur.fetchall():
        lower = text.lower()
        for forbidden, correct in ZVS_FORBIDDEN.items():
            # Word boundary check
            if f" {forbidden} " in f" {lower} ":
                violations += 1
                if violations <= 3:
                    print(f"  VIOLATION: {ref} — '{forbidden}' → should be '{correct}'")
    if violations == 0:
        print("  No violations in sample — OK")
    else:
        print(f"  Total violations in sample: {violations}")

    # 6. Tongsan articles check
    print("\n=== Tongsan Articles ===")
    try:
        cur.execute("SELECT count(*) FROM tongsan_articles WHERE content != ''")
        with_content = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM tongsan_articles")
        total = cur.fetchone()[0]
        print(f"  Total: {total}, with content: {with_content}")
    except sqlite3.OperationalError:
        print("  Table not found")

    # 7. Songs check
    print("\n=== Zolai Songs ===")
    try:
        cur.execute("SELECT collection, count(*) FROM zolai_songs GROUP BY collection")
        for coll, cnt in cur.fetchall():
            print(f"  {coll}: {cnt} songs")
    except sqlite3.OperationalError:
        print("  Table not found")

    conn.close()

    if errors:
        print(f"\n❌ VALIDATION FAILED: {len(errors)} issues")
        for e in errors:
            print(f"  - {e}")
        return False
    print("\n✅ VALIDATION PASSED")
    return True


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    ok = validate(db)
    sys.exit(0 if ok else 1)
