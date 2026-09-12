#!/usr/bin/env python3
"""Ingest ALL Myanmar and supplementary data into the database.

Phase 3: Full database ingestion with provenance tracking.

Reads JSONL files and upserts into the SQLite database, recording every
bulk ingestion in the audit log for traceability.

Usage:
    python ingest_all_to_db.py              # run all ingestions
    python ingest_all_to_db.py --summary    # print DB state only
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parents[3]
DATA_DIR = WORKSPACE / "data"
DB_PATH = DATA_DIR / "zolai.db"

MY_DIR = DATA_DIR / "processed" / "my"
DICT_DIR = DATA_DIR / "dictionary" / "processed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def file_hash(path: Path, length: int = 16) -> str:
    """Return truncated SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file, skipping bad lines."""
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------
class DataIngester:
    """Batch-ingest JSONL data into SQLite with provenance tracking."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.stats: dict[str, dict[str, int]] = {}

    # ---- schema helpers ------------------------------------------------
    def ensure_myanmar_columns(self) -> list[str]:
        """Add myanmar TEXT column to tables missing it."""
        tables = [
            "dictionary_en_zo",
            "grammar_patterns",
            "translations",
            "word_alignments",
            "word_collocations",
            "word_usage",
            "vocab",
            "training_exercises",
        ]
        altered: list[str] = []
        cur = self.conn.cursor()
        for t in tables:
            try:
                cur.execute(f"ALTER TABLE [{t}] ADD COLUMN myanmar TEXT")
                self.conn.commit()
                altered.append(t)
                print(f"  + myanmar column added to {t}")
            except sqlite3.OperationalError:
                pass  # column already exists
        return altered

    # ---- ingestion targets ---------------------------------------------
    def ingest_unified_myanmar(self) -> None:
        """Update dictionary.myanmar from the unified Myanmar dictionary."""
        print("\n--- dict_myanmar_master_v1.jsonl → dictionary.myanmar ---")
        path = MY_DIR / "dict_myanmar_master_v1.jsonl"
        items = load_jsonl(path)
        if not items:
            print("  (file missing or empty — skipping)")
            return

        # Build lookup: zolai -> myanmar
        zo_my: dict[str, str] = {}
        en_my: dict[str, str] = {}
        for item in items:
            my = (item.get("myanmar") or "").strip()
            if not my:
                continue
            zo = (item.get("zolai") or "").strip()
            en = (item.get("english") or "").strip()
            if zo:
                zo_my[zo.lower()] = my
            if en:
                en_my[en.lower()] = my

        updated = 0
        cur = self.conn.cursor()
        # Match by zolai
        cur.execute("SELECT id, zolai FROM dictionary WHERE myanmar IS NULL OR myanmar = ''")
        rows = cur.fetchall()
        batch: list[tuple[str, int]] = []
        for row_id, zolai in rows:
            my = zo_my.get(zolai.lower(), "")
            if my:
                batch.append((my, row_id))
        if batch:
            cur.executemany("UPDATE dictionary SET myanmar = ? WHERE id = ?", batch)
            self.conn.commit()
            updated += len(batch)

        # Match by english for remaining
        cur.execute("SELECT id, english FROM dictionary WHERE myanmar IS NULL OR myanmar = ''")
        rows = cur.fetchall()
        batch2: list[tuple[str, int]] = []
        for row_id, english in rows:
            # english might be JSON list
            try:
                en_list = json.loads(english) if english.startswith("[") else [english]
                en_val = en_list[0] if en_list else ""
            except (json.JSONDecodeError, TypeError):
                en_val = str(english or "")
            my = en_my.get(en_val.lower().strip(), "")
            if my:
                batch2.append((my, row_id))
        if batch2:
            cur.executemany("UPDATE dictionary SET myanmar = ? WHERE id = ?", batch2)
            self.conn.commit()
            updated += len(batch2)

        self.stats["dictionary"] = {"updated_myanmar": updated}
        print(f"  Updated: {updated:,}")

    def ingest_judson_bible(self) -> None:
        """Update bible_verses.myanmar from the Judson Bible."""
        print("\n--- bible_judson_v1.jsonl → bible_verses.myanmar ---")
        path = MY_DIR / "bible_judson_v1.jsonl"
        items = load_jsonl(path)
        if not items:
            print("  (file missing or empty — skipping)")
            return

        # Myanmar book name → English abbreviation mapping
        # 66 books: OT 39 + NT 27
        my_to_en: dict[str, str] = {
            # OT (39 books)
            "ကမ္ဘာဦး": "GEN", "ထွက်မြောက်": "EXO",
            "ဝတ်ပြု": "LEV", "တရားဟော": "DEU",
            "ယောရှု": "JOS", "သူကြီး": "JDG", "ရုသ": "RUT",
            "၁ ရာ": "1SA", "၂ ရာ": "2SA",
            "၁ ရာချုပ်": "1KI", "၂ ရာချုပ်": "2KI",
            "၃ ရာ": "1CH", "၄ ရာ": "2CH",
            "ဧဇရ": "EZR", "နေဟမိ": "NEH", "ဧသတာ": "EST",
            "ယောဘ": "JOB", "ဆာလံ": "PSA", "သုတ္တံ": "PRO",
            "ဒေသနာ": "ECC", "ရှောလမုန်": "SNG",
            "ဟေရှာယ": "ISA", "ယေရမိ": "JER",
            "မြည်တမ်းစကား": "LAM", "ယေဇကျေလ": "EZK",
            "ဒံယေလ": "DAN", "ဟောရှေ": "HOS",
            "ယောလ": "JOL", "အာမုတ်": "AMO",
            "သြဗဒိ": "OBA", "ယောန": "JON", "မိက္ခာ": "MIC",
            "နာဟုံ": "NAM", "ဟဗက္ကုတ်": "HAB",
            "ဇေဖနိ": "ZEP", "ဟ္ဂဲ": "HAG",
            "ဇာခရိ": "ZEC", "မာလခိ": "MAL",
            "တောလည်": "NUM",
            # NT (27 books)
            "မဿဲ": "MAT", "ရှင်မာကု": "MRK", "လုကာ": "LUK",
            "ရှင်ယောဟန်": "JHN", "တမန်တော်ဝတ္ထု": "ACT",
            "ရောမ": "ROM", "၁ ကော": "1CO", "၂ ကော": "2CO",
            "ဂလာတိ": "GAL", "ဧဖက်": "EPH",
            "ဖိလိပ္ပိ": "PHP", "ကောလောသဲ": "COL",
            "၁ သက်": "1TH", "၂ သက်": "2TH",
            "၁ တိ": "1TI", "၂ တိ": "2TI",
            "တိတု": "TIT", "ဖိလေမုန်": "PHM",
            "ဟေဗြဲ": "HEB", "၁ ပေ": "1PE", "၂ ပေ": "2PE",
            "၁ ယော": "1JN", "၂ ယော": "2JN",
            "၃ ယော": "3JN", "ယုဒ": "JUD", "ဗျာဒိတ်": "REV",
            "ယာကုပ်": "JAS",
        }

        # Build ref -> text map (using English abbreviation refs)
        cur = self.conn.cursor()
        ref_text: dict[str, str] = {}
        for item in items:
            book_my = item.get("book", "")
            chapter = item.get("chapter")
            verse = item.get("verse")
            text = (item.get("text") or "").strip()
            if not book_my or chapter is None or verse is None or not text:
                continue
            book_en = my_to_en.get(book_my, "")
            if not book_en:
                continue
            # Format: "GEN 1:1"
            ref = f"{book_en} {chapter}:{verse}"
            ref_text[ref] = text

        if not ref_text:
            print("  (no matching refs found — check book name mapping)")
            return

        # Update matching rows
        cur.execute("SELECT id, ref FROM bible_verses WHERE myanmar IS NULL OR myanmar = ''")
        rows = cur.fetchall()
        batch: list[tuple[str, int]] = []
        for row_id, ref in rows:
            if ref in ref_text:
                batch.append((ref_text[ref], row_id))
        if batch:
            cur.executemany("UPDATE bible_verses SET myanmar = ? WHERE id = ?", batch)
            self.conn.commit()

        self.stats["bible_verses"] = {"updated_myanmar": len(batch)}
        print(f"  Updated: {len(batch):,} (of {len(ref_text):,} Judson verses)")

    def ingest_en_my_index(self) -> None:
        """Upsert EN→MY reverse index into dictionary_en_zo.myanmar."""
        print("\n--- dict_en_my_index_v1.jsonl → dictionary_en_zo.myanmar ---")
        path = MY_DIR / "dict_en_my_index_v1.jsonl"
        items = load_jsonl(path)
        if not items:
            print("  (file missing or empty — skipping)")
            return

        # Build headword -> myanmar map
        hw_my: dict[str, str] = {}
        for item in items:
            en = (item.get("english") or "").strip()
            my = (item.get("myanmar") or "").strip()
            if en and my:
                hw_my[en.lower()] = my

        cur = self.conn.cursor()
        cur.execute("SELECT id, headword FROM dictionary_en_zo WHERE myanmar IS NULL OR myanmar = ''")
        rows = cur.fetchall()
        batch: list[tuple[str, int]] = []
        for row_id, hw in rows:
            my = hw_my.get(hw.lower(), "")
            if my:
                batch.append((my, row_id))
        if batch:
            cur.executemany("UPDATE dictionary_en_zo SET myanmar = ? WHERE id = ?", batch)
            self.conn.commit()

        self.stats["dictionary_en_zo"] = {"updated_myanmar": len(batch)}
        print(f"  Updated: {len(batch):,}")

    def ingest_vocab_myanmar(self) -> None:
        """Enrich vocab.myanmar from dictionary."""
        print("\n--- dictionary.myanmar → vocab.myanmar ---")
        cur = self.conn.cursor()

        # Build zolai -> myanmar from dictionary
        cur.execute(
            "SELECT zolai, myanmar FROM dictionary "
            "WHERE myanmar IS NOT NULL AND myanmar != ''"
        )
        zo_my = {r[0].lower(): r[1] for r in cur.fetchall()}

        cur.execute("SELECT id, headword FROM vocab WHERE myanmar IS NULL OR myanmar = ''")
        rows = cur.fetchall()
        batch: list[tuple[str, int]] = []
        for row_id, hw in rows:
            my = zo_my.get(hw.lower(), "")
            if my:
                batch.append((my, row_id))
        if batch:
            cur.executemany("UPDATE vocab SET myanmar = ? WHERE id = ?", batch)
            self.conn.commit()

        self.stats["vocab"] = {"updated_myanmar": len(batch)}
        print(f"  Updated: {len(batch):,}")

    def ingest_provenance(self) -> None:
        """Record file provenance for all ingested data files."""
        print("\n--- Recording provenance ---")
        files_to_track = [
            (MY_DIR / "dict_myanmar_master_v1.jsonl", "dictionary", "unified_myanmar_dict"),
            (MY_DIR / "dict_en_my_index_v1.jsonl", "dictionary_en_zo", "en_my_index"),
            (MY_DIR / "bible_judson_v1.jsonl", "bible_verses", "judson_bible"),
            (DICT_DIR / "dict_zo_en_master_v1.jsonl", "dictionary", "zo_en_master"),
            (DICT_DIR / "dict_canonical_clean.jsonl", "dictionary_en_zo", "canonical_clean"),
        ]
        cur = self.conn.cursor()
        added = 0
        for fpath, table, source in files_to_track:
            if not fpath.exists():
                continue
            fsize = fpath.stat().st_size
            fhash = file_hash(fpath)
            # Check if already tracked
            cur.execute(
                "SELECT id FROM provenance WHERE filename = ? AND sha256 = ?",
                (fpath.name, fhash),
            )
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO provenance "
                "(filename, size_bytes, sha256, row_count, source, "
                "generator_script, version, status, updated_at, change_log) "
                "VALUES (?, ?, ?, 0, ?, 'ingest_all_to_db.py', '1.0', 'active', ?, '[]')",
                (fpath.name, fsize, fhash, source, now_iso()),
            )
            added += 1
        self.conn.commit()
        self.stats["provenance"] = {"added": added}
        print(f"  Added: {added}")

    def log_all_ingestions(self) -> None:
        """Write a single audit record summarising this ingestion run."""
        print("\n--- Logging provenance to audit trail ---")
        cur = self.conn.cursor()
        summary = json.dumps(self.stats, ensure_ascii=False)
        cur.execute(
            "INSERT INTO data_audit_log "
            "(table_name, row_id, field, old_value, new_value, changed_at, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "_bulk_run",
                0,
                "phase3_ingestion",
                None,
                summary,
                now_iso(),
                "phase3_full_ingestion",
            ),
        )
        self.conn.commit()
        print(f"  Logged {len(self.stats)} ingestion targets")

    # ---- reporting -----------------------------------------------------
    def print_summary(self) -> None:
        """Print final database state."""
        print("\n" + "=" * 55)
        print("  FINAL DATABASE STATE")
        print("=" * 55)
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM [{t}]")
            total = cur.fetchone()[0]
            try:
                cur.execute(
                    f"SELECT COUNT(*) FROM [{t}] "
                    "WHERE myanmar IS NOT NULL AND myanmar != ''"
                )
                my = cur.fetchone()[0]
                if my > 0:
                    print(f"  {t:25s} {total:>10,} rows  (MY: {my:>8,})")
                else:
                    print(f"  {t:25s} {total:>10,} rows")
            except sqlite3.OperationalError:
                print(f"  {t:25s} {total:>10,} rows")
        size_mb = self.db_path.stat().st_size / 1024 / 1024
        print(f"\n  DB size: {size_mb:.1f} MB")
        print("=" * 55)

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if "--summary" in sys.argv:
        ingester = DataIngester()
        ingester.print_summary()
        ingester.close()
        return

    print("Phase 3: Full Database Ingestion with Provenance")
    print("=" * 55)
    print(f"DB: {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")

    ingester = DataIngester()

    ingester.ensure_myanmar_columns()
    ingester.ingest_unified_myanmar()
    ingester.ingest_judson_bible()
    ingester.ingest_en_my_index()
    ingester.ingest_vocab_myanmar()
    ingester.ingest_provenance()
    ingester.log_all_ingestions()
    ingester.print_summary()
    ingester.close()

    print("\nPhase 3 ingestion complete.")


if __name__ == "__main__":
    main()
