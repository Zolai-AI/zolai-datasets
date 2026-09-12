#!/usr/bin/env python3
"""Phase 7: Dedup & Validate — check integrity after integration."""
import os
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
REF_DIR = "/home/peter/Documents/Projects/zolai-ai/data/reference/grammar"

# ZVS 2018 forbidden forms (lowercase for matching)
ZVS_FORBIDDEN = {
    "pathian": "pasian",
    "ram": "gam",
    "fapa": "tapa",
    "bawipa": "topa",
    "siangpahrang": "kumpipa",
}

# Minimum expected song counts per collection
SONG_MINIMUMS = {
    "Tedim Labu": 500,
    "Khanlawnna Late": 200,
    "Zomi Worship Collective": 300,
    "Gospel": 5,
}


def validate(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()
    errors = []

    # 1. Row counts
    tables = [
        "bible_verses", "dictionary", "articles",
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
        try:
            cur.execute(f"SELECT count(*) FROM bible_verses WHERE {col} IS NOT NULL")
            filled = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bible_verses")
            total = cur.fetchone()[0]
            pct = (filled / total * 100) if total else 0
            print(f"  {col}: {filled}/{total} ({pct:.1f}%)")
        except sqlite3.OperationalError:
            print(f"  {col}: column not found")

    # 5. ZVS 2018 check on new Zolai text (sample)
    print("\n=== ZVS 2018 Compliance (sample) ===")
    try:
        cur.execute(
            "SELECT ref, zo_tedim1932 FROM bible_verses "
            "WHERE zo_tedim1932 IS NOT NULL LIMIT 200"
        )
        violations = 0
        for ref, text in cur.fetchall():
            lower = text.lower()
            for forbidden, correct in ZVS_FORBIDDEN.items():
                if f" {forbidden} " in f" {lower} ":
                    violations += 1
                    if violations <= 3:
                        print(
                            f"  VIOLATION: {ref} — "
                            f"'{forbidden}' → should be '{correct}'"
                        )
        if violations == 0:
            print("  No violations in sample — OK")
        else:
            print(f"  Total violations in sample: {violations}")
    except sqlite3.OperationalError:
        print("  Table/columns not found")

    # 6. Articles check
    print("\n=== Articles ===")
    try:
        cur.execute("SELECT count(*) FROM articles WHERE content != ''")
        with_content = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM articles")
        total = cur.fetchone()[0]
        print(f"  Total: {total}, with content: {with_content}")
    except sqlite3.OperationalError:
        print("  Table not found")

    # 7. Songs — per-collection counts with minimums
    print("\n=== Zolai Songs (per collection) ===")
    try:
        cur.execute(
            "SELECT collection, count(*) FROM zolai_songs GROUP BY collection"
        )
        collection_counts = {row[0]: row[1] for row in cur.fetchall()}
        total_songs = 0
        for coll, cnt in sorted(collection_counts.items()):
            status = "OK"
            if coll in SONG_MINIMUMS:
                if cnt < SONG_MINIMUMS[coll]:
                    status = f"BELOW MIN ({SONG_MINIMUMS[coll]})"
                    errors.append(
                        f"{coll}: {cnt} songs < minimum {SONG_MINIMUMS[coll]}"
                    )
            print(f"  {coll}: {cnt} songs [{status}]")
            total_songs += cnt
        print(f"  TOTAL: {total_songs} songs")
        if total_songs < 1000:
            errors.append(f"Total songs {total_songs} < 1,000 minimum")
            print("  ⚠ Total below 1,000 minimum")
    except sqlite3.OperationalError:
        print("  Table not found")

    # 8. Reference files from PDF conversion
    print("\n=== Reference Files (data/reference/grammar/) ===")
    if os.path.isdir(REF_DIR):
        md_files = [f for f in os.listdir(REF_DIR) if f.endswith(".md")]
        txt_files = [f for f in os.listdir(REF_DIR) if f.endswith(".txt")]
        print(f"  Markdown files: {len(md_files)}")
        print(f"  Text files: {len(txt_files)}")
        # Check for at least some PDF-converted files
        pdf_converted = [
            f for f in md_files
            if f.startswith(("Zolai_Simbu_Tan_", "lesson_"))
            or f == "Zolai_Standard_Format_kaggle.md"
        ]
        print(f"  PDF-converted files: {len(pdf_converted)}")
        if len(pdf_converted) < 5:
            errors.append(
                f"Only {len(pdf_converted)} PDF-converted files "
                f"(expected >= 5)"
            )
    else:
        print("  Directory not found")
        errors.append(f"{REF_DIR} not found")

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
