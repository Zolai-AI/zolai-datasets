#!/usr/bin/env python3
"""Comprehensive data ingestion into SQLite with full provenance tracking.

Ingests ALL raw and processed data into the zolai.db database:
  1. Dictionary enrichment (verified, corrections, dalsuum, bible, zomidaily)
  2. Bible context (per_book, per_chapter, phrase_map, word_usage, patterns, topics)
  3. Training exercises (replace old with fresh)
  4. Raw EN→MY translations
  5. Per-word audit logging + provenance tracking

Usage:
    python ingest_all_data.py              # full ingestion
    python ingest_all_data.py --dry-run    # preview without writes
    python ingest_all_data.py --summary    # print DB state only
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parents[3]
DATA_DIR = WORKSPACE / "data"
DB_PATH = DATA_DIR / "zolai.db"

DICT_DIR = DATA_DIR / "dictionary" / "processed"
BIBLE_CONTEXT_DIR = DATA_DIR / "bible" / "context"
BIBLE_DIR = DATA_DIR / "bible"
RAW_MY_DIR = DATA_DIR / "raw" / "my"
PROCESSED_MY_DIR = DATA_DIR / "processed" / "my"

# All source files we'll ingest
SOURCE_FILES: dict[str, dict[str, Any]] = {
    "dict_verified_master": {
        "path": DICT_DIR / "dict_verified_master.jsonl",
        "description": "Verified dictionary (94K entries)",
    },
    "dict_corrections": {
        "path": DICT_DIR / "dict_corrections.jsonl",
        "description": "Dictionary corrections (22)",
    },
    "dict_dalsuum_merged": {
        "path": DICT_DIR / "dict_dalsuum_merged.jsonl",
        "description": "Dalsuum trilingual dictionary (7.8K)",
    },
    "dict_bible_combined": {
        "path": DICT_DIR / "dict_bible_combined_v1.jsonl",
        "description": "Bible-derived dictionary (4K)",
    },
    "dict_zomidaily_new": {
        "path": DICT_DIR / "dict_zomidaily_new_words.jsonl",
        "description": "Zomidaily modern words (1.4K)",
    },
    "dict_zomidaily_expanded": {
        "path": DICT_DIR / "dict_zomidaily_expanded.jsonl",
        "description": "Zomidaily expanded words (1K)",
    },
    "per_book_analysis": {
        "path": BIBLE_CONTEXT_DIR / "per_book_analysis.jsonl",
        "description": "Bible per-book analysis (65)",
    },
    "per_chapter_analysis": {
        "path": BIBLE_CONTEXT_DIR / "per_chapter_analysis.jsonl",
        "description": "Bible per-chapter analysis (1,153)",
    },
    "phrase_context_map": {
        "path": BIBLE_CONTEXT_DIR / "phrase_context_map.jsonl",
        "description": "Phrase context map (45,597)",
    },
    "word_usage_profiles": {
        "path": BIBLE_CONTEXT_DIR / "word_usage_profiles.jsonl",
        "description": "Word usage profiles (7,384)",
    },
    "sentence_patterns": {
        "path": BIBLE_CONTEXT_DIR / "sentence_patterns.jsonl",
        "description": "Bible sentence patterns (65)",
    },
    "topic_clusters": {
        "path": BIBLE_CONTEXT_DIR / "topic_clusters.jsonl",
        "description": "Bible topic clusters (12)",
    },
    "negation_exercises": {
        "path": BIBLE_DIR / "negation_exercises.jsonl",
        "description": "Negation exercises (26K)",
    },
    "question_exercises": {
        "path": BIBLE_DIR / "question_exercises.jsonl",
        "description": "Question exercises (24K)",
    },
    "pronoun_exercises": {
        "path": BIBLE_DIR / "pronoun_exercises.jsonl",
        "description": "Pronoun exercises (21K)",
    },
    "error_correction_exercises": {
        "path": BIBLE_DIR / "error_correction_exercises.jsonl",
        "description": "Error correction exercises (8K)",
    },
    "conditional_exercises": {
        "path": BIBLE_DIR / "conditional_exercises.jsonl",
        "description": "Conditional exercises (284)",
    },
    "vocab_from_bible": {
        "path": BIBLE_DIR / "vocab_from_bible.jsonl",
        "description": "Vocab from Bible (6,346)",
    },
    "all_words_frequency": {
        "path": BIBLE_DIR / "ALL_WORDS_WITH_FREQUENCY.jsonl",
        "description": "All words with frequency (2,975)",
    },
    "en_my_parallel": {
        "path": RAW_MY_DIR / "en_my_parallel.jsonl",
        "description": "EN→MY parallel (77K)",
    },
    "en_my_news": {
        "path": RAW_MY_DIR / "en_my_news.jsonl",
        "description": "EN→MY news (77K)",
    },
    "my_dictionary": {
        "path": RAW_MY_DIR / "my_dictionary.jsonl",
        "description": "MY dictionary (19K)",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def file_hash(path: Path, length: int = 16) -> str:
    """Return truncated SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file, skipping bad lines."""
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"    ⚠ {bad} bad lines skipped in {path.name}")
    return items


def truncate(text: Any, maxlen: int = 200) -> str:
    """Truncate a value for audit logging."""
    s = str(text) if text is not None else ""
    return s[:maxlen] if len(s) > maxlen else s


def safe_json(obj: Any) -> str:
    """Serialize to JSON, falling back to str."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


# ---------------------------------------------------------------------------
# Main Ingestor
# ---------------------------------------------------------------------------
class DataIngester:
    """Comprehensive data ingester with provenance tracking."""

    def __init__(self, db_path: Path = DB_PATH, dry_run: bool = False) -> None:
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats: dict[str, dict[str, int]] = {}
        self.start_time = time.time()

        if not db_path.exists():
            print(f"ERROR: Database not found at {db_path}")
            sys.exit(1)

        self.conn = sqlite3.connect(str(db_path), timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def close(self) -> None:
        self.conn.close()

    # ---- progress helper -------------------------------------------------
    def _progress(self, label: str, current: int, total: int) -> None:
        if total > 0 and current % max(1, total // 20) == 0:
            pct = current * 100 // total
            print(f"    {label}: {current:,}/{total:,} ({pct}%)")

    # ---- audit log -------------------------------------------------------
    def _audit(self, table: str, row_id: int, field: str,
               old_val: Any, new_val: Any, reason: str) -> None:
        if self.dry_run:
            return
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO data_audit_log "
            "(table_name, row_id, field, old_value, new_value, changed_at, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (table, row_id, field, truncate(old_val), truncate(new_val),
             now_iso(), reason),
        )

    def _audit_bulk(self, table: str, count: int, reason: str) -> None:
        """Log a bulk operation summary."""
        if self.dry_run:
            return
        cur = self.conn.cursor()
        summary = json.dumps({
            "table": table,
            "rows_affected": count,
            "method": reason,
            "timestamp": now_iso(),
        }, ensure_ascii=False)
        cur.execute(
            "INSERT INTO data_audit_log "
            "(table_name, row_id, field, old_value, new_value, changed_at, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (table, 0, "bulk_ingestion", None, summary, now_iso(), reason),
        )

    # ---- provenance ------------------------------------------------------
    def _record_provenance(self, key: str, file_info: dict,
                           row_count: int) -> None:
        if self.dry_run:
            return
        path = file_info["path"]
        if not path.exists():
            return
        fsize = path.stat().st_size
        fhash = file_hash(path)
        cur = self.conn.cursor()

        # Upsert: skip if same hash already recorded
        cur.execute(
            "SELECT id FROM provenance WHERE filename = ? AND sha256 = ?",
            (path.name, fhash),
        )
        existing = cur.fetchone()
        if existing:
            return

        cur.execute(
            "INSERT INTO provenance "
            "(filename, size_bytes, sha256, row_count, source, "
            "generator_script, version, status, updated_at, change_log) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path.name, fsize, fhash, row_count,
             key, "ingest_all_data.py", "2.0", "active",
             now_iso(), "[]"),
        )

    # ===================================================================
    # 1. DICTIONARY ENRICHMENT
    # ===================================================================
    def ingest_dictionary_enrichment(self) -> None:
        """Enrich existing dictionary entries from multiple sources."""
        print("\n=== 1. DICTIONARY ENRICHMENT ===")
        cur = self.conn.cursor()
        total_changes = 0

        # 1a. Verified master → update verified + english_clean
        print("\n  [1a] dict_verified_master.jsonl → dictionary.verified + english_clean")
        verified = load_jsonl(SOURCE_FILES["dict_verified_master"]["path"])
        if verified:
            # Build zolai → record lookup
            verified_map: dict[str, dict] = {}
            for rec in verified:
                zo = (rec.get("zolai") or "").strip().lower()
                if zo:
                    verified_map[zo] = rec

            # Get existing rows
            cur.execute("SELECT id, zolai, english_clean FROM dictionary")
            existing = cur.fetchall()
            batch_updates: list[tuple[str, int]] = []
            changes = 0
            for row_id, zolai_val, old_clean in existing:
                rec = verified_map.get(zolai_val.lower())
                if not rec:
                    continue
                new_clean = rec.get("english_clean", "")
                if new_clean and new_clean != (old_clean or ""):
                    batch_updates.append((new_clean, row_id))
                    self._audit("dictionary", row_id, "english_clean",
                                old_clean, new_clean, "verified_master")
                    changes += 1
            if batch_updates and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET english_clean = ?, "
                    "entry_version = 'verified_v1' WHERE id = ?",
                    batch_updates,
                )
                self.conn.commit()
            total_changes += changes
            self.stats["dict_verified"] = {"matched": len(verified_map),
                                            "updated": changes}
            print(f"    Matched: {len(verified_map):,}, Updated: {changes:,}")

        # 1b. Corrections → apply to english_clean
        print("\n  [1b] dict_corrections.jsonl → dictionary.english_clean")
        corrections = load_jsonl(SOURCE_FILES["dict_corrections"]["path"])
        if corrections:
            corr_map: dict[str, dict] = {}
            for rec in corrections:
                zo = (rec.get("zolai") or "").strip().lower()
                if zo:
                    corr_map[zo] = rec

            cur.execute("SELECT id, zolai, english_clean FROM dictionary")
            existing = cur.fetchall()
            batch_corr: list[tuple[str, int]] = []
            corr_count = 0
            for row_id, zolai_val, old_clean in existing:
                rec = corr_map.get(zolai_val.lower())
                if not rec:
                    continue
                new_clean = rec.get("new_english_clean", "")
                if new_clean and new_clean != (old_clean or ""):
                    batch_corr.append((new_clean, row_id))
                    self._audit("dictionary", row_id, "english_clean",
                                old_clean, new_clean,
                                f"correction: {rec.get('reason', '')}")
                    corr_count += 1
                    # Log to audit_findings
                    cur.execute(
                        "INSERT INTO audit_findings "
                        "(finding_type, word, old_value, new_value, source, "
                        "confidence, created_at, verified_by, entry_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        ("correction", zolai_val, truncate(old_clean),
                         truncate(new_clean), "dict_corrections",
                         "high", now_iso(), "system", row_id),
                    )
            if batch_corr and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET english_clean = ? WHERE id = ?",
                    batch_corr,
                )
                self.conn.commit()
            total_changes += corr_count
            self.stats["dict_corrections"] = {"applied": corr_count}
            print(f"    Applied: {corr_count:,}")

        # 1c. Dalsuum merged → fill missing myanmar + add new entries
        print("\n  [1c] dict_dalsuum_merged.jsonl → dictionary.myanmar + new entries")
        dalsuum = load_jsonl(SOURCE_FILES["dict_dalsuum_merged"]["path"])
        if dalsuum:
            dalsuum_map: dict[str, dict] = {}
            for rec in dalsuum:
                zo = (rec.get("zolai_normalized") or rec.get("zolai_word") or "").strip().lower()
                if zo:
                    dalsuum_map[zo] = rec

            # Fill missing myanmar
            cur.execute(
                "SELECT id, zolai, myanmar FROM dictionary "
                "WHERE myanmar IS NULL OR myanmar = ''"
            )
            empty_my = cur.fetchall()
            my_updates: list[tuple[str, int]] = []
            my_count = 0
            for row_id, zolai_val, _ in empty_my:
                rec = dalsuum_map.get(zolai_val.lower())
                if not rec:
                    continue
                my_text = rec.get("myanmar_word") or rec.get("headword") or ""
                if my_text.strip():
                    my_updates.append((my_text.strip(), row_id))
                    self._audit("dictionary", row_id, "myanmar",
                                "", my_text, "dalsuum_merged")
                    my_count += 1
            if my_updates and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET myanmar = ? WHERE id = ?",
                    my_updates,
                )
                self.conn.commit()
            total_changes += my_count
            self.stats["dict_dalsuum"] = {"myanmar_filled": my_count}
            print(f"    Myanmar filled: {my_count:,}")

        # 1d. Bible combined → fill missing english_clean from bible definitions
        print("\n  [1d] dict_bible_combined_v1.jsonl → dictionary.english_clean")
        bible_dict = load_jsonl(SOURCE_FILES["dict_bible_combined"]["path"])
        if bible_dict:
            bible_map: dict[str, dict] = {}
            for rec in bible_dict:
                zo = (rec.get("zolai") or "").strip().lower()
                if zo:
                    bible_map[zo] = rec

            cur.execute(
                "SELECT id, zolai, english_clean FROM dictionary "
                "WHERE english_clean IS NULL OR english_clean = ''"
            )
            empty_en = cur.fetchall()
            en_updates: list[tuple[str, int]] = []
            en_count = 0
            for row_id, zolai_val, _ in empty_en:
                rec = bible_map.get(zolai_val.lower())
                if not rec:
                    continue
                en_text = rec.get("english", "")
                if en_text.strip():
                    en_updates.append((en_text.strip(), row_id))
                    self._audit("dictionary", row_id, "english_clean",
                                "", en_text, "bible_combined")
                    en_count += 1
            if en_updates and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET english_clean = ? WHERE id = ?",
                    en_updates,
                )
                self.conn.commit()
            total_changes += en_count
            self.stats["dict_bible"] = {"english_filled": en_count}
            print(f"    English filled: {en_count:,}")

        # 1e. Zomidaily new words → add new entries + fill myanmar
        print("\n  [1e] dict_zomidaily_new_words.jsonl → dictionary.myanmar")
        zomi_new = load_jsonl(SOURCE_FILES["dict_zomidaily_new"]["path"])
        if zomi_new:
            zomi_map: dict[str, dict] = {}
            for rec in zomi_new:
                zo = (rec.get("zo") or "").strip().lower()
                if zo:
                    zomi_map[zo] = rec

            cur.execute(
                "SELECT id, zolai, myanmar FROM dictionary "
                "WHERE myanmar IS NULL OR myanmar = ''"
            )
            empty_my2 = cur.fetchall()
            my_updates2: list[tuple[str, int]] = []
            my_count2 = 0
            for row_id, zolai_val, _ in empty_my2:
                rec = zomi_map.get(zolai_val.lower())
                if not rec:
                    continue
                # Zomidaily entries use 'en' as English (Burmese) or 'en' field
                en_text = rec.get("en", "")
                if en_text.strip() and en_text != f"*[untranslated, freq={rec.get('freq', 0)}]*":
                    my_updates2.append((en_text.strip(), row_id))
                    self._audit("dictionary", row_id, "myanmar",
                                "", en_text, "zomidaily_new")
                    my_count2 += 1
            if my_updates2 and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET myanmar = ? WHERE id = ?",
                    my_updates2,
                )
                self.conn.commit()
            total_changes += my_count2
            self.stats["dict_zomi_new"] = {"myanmar_filled": my_count2}
            print(f"    Myanmar filled: {my_count2:,}")

        # 1f. Zomidaily expanded → fill remaining
        print("\n  [1f] dict_zomidaily_expanded.jsonl → dictionary.myanmar")
        zomi_exp = load_jsonl(SOURCE_FILES["dict_zomidaily_expanded"]["path"])
        if zomi_exp:
            zomi_exp_map: dict[str, dict] = {}
            for rec in zomi_exp:
                zo = (rec.get("zo") or "").strip().lower()
                if zo:
                    zomi_exp_map[zo] = rec

            cur.execute(
                "SELECT id, zolai, myanmar FROM dictionary "
                "WHERE myanmar IS NULL OR myanmar = ''"
            )
            empty_my3 = cur.fetchall()
            my_updates3: list[tuple[str, int]] = []
            my_count3 = 0
            for row_id, zolai_val, _ in empty_my3:
                rec = zomi_exp_map.get(zolai_val.lower())
                if not rec:
                    continue
                en_text = rec.get("en", "")
                if en_text.strip() and en_text != f"[emphasis particle]":
                    my_updates3.append((en_text.strip(), row_id))
                    self._audit("dictionary", row_id, "myanmar",
                                "", en_text, "zomidaily_expanded")
                    my_count3 += 1
            if my_updates3 and not self.dry_run:
                cur.executemany(
                    "UPDATE dictionary SET myanmar = ? WHERE id = ?",
                    my_updates3,
                )
                self.conn.commit()
            total_changes += my_count3
            self.stats["dict_zomi_exp"] = {"myanmar_filled": my_count3}
            print(f"    Myanmar filled: {my_count3:,}")

        self._audit_bulk("dictionary", total_changes,
                         "dictionary_enrichment_v2")
        self._record_provenance("dict_verified_master",
                                SOURCE_FILES["dict_verified_master"], len(verified))
        self._record_provenance("dict_corrections",
                                SOURCE_FILES["dict_corrections"], len(corrections))
        self._record_provenance("dict_dalsuum_merged",
                                SOURCE_FILES["dict_dalsuum_merged"], len(dalsuum))
        self._record_provenance("dict_bible_combined",
                                SOURCE_FILES["dict_bible_combined"], len(bible_dict))
        self._record_provenance("dict_zomidaily_new",
                                SOURCE_FILES["dict_zomidaily_new"], len(zomi_new))
        self._record_provenance("dict_zomidaily_expanded",
                                SOURCE_FILES["dict_zomidaily_expanded"], len(zomi_exp))
        print(f"\n  TOTAL dictionary changes: {total_changes:,}")

    # ===================================================================
    # 2. BIBLE CONTEXT INGESTION
    # ===================================================================
    def ingest_bible_context(self) -> None:
        """Ingest all 6 Bible context files."""
        print("\n=== 2. BIBLE CONTEXT INGESTION ===")
        cur = self.conn.cursor()
        total_inserted = 0

        # 2a. Per-book analysis → bible_context (analysis_type="book")
        print("\n  [2a] per_book_analysis.jsonl → bible_context")
        book_data = load_jsonl(SOURCE_FILES["per_book_analysis"]["path"])
        if book_data:
            rows = []
            for rec in book_data:
                book = rec.get("book", "")
                data_json = safe_json(rec)
                rows.append((book, None, "book", data_json))
            if rows and not self.dry_run:
                cur.executemany(
                    "INSERT INTO bible_context (book, chapter, analysis_type, data) "
                    "VALUES (?, ?, ?, ?)",
                    rows,
                )
                self.conn.commit()
            total_inserted += len(rows)
            self.stats["bible_context_book"] = {"inserted": len(rows)}
            print(f"    Inserted: {len(rows):,}")
            self._record_provenance("per_book_analysis",
                                    SOURCE_FILES["per_book_analysis"], len(rows))

        # 2b. Per-chapter analysis → bible_context (analysis_type="chapter")
        print("\n  [2b] per_chapter_analysis.jsonl → bible_context")
        chap_data = load_jsonl(SOURCE_FILES["per_chapter_analysis"]["path"])
        if chap_data:
            rows = []
            for rec in chap_data:
                book = rec.get("book", "")
                chap_str = rec.get("chapter", "")
                try:
                    chap_num = int(chap_str)
                except (ValueError, TypeError):
                    chap_num = None
                data_json = safe_json(rec)
                rows.append((book, chap_num, "chapter", data_json))
            if rows and not self.dry_run:
                cur.executemany(
                    "INSERT INTO bible_context (book, chapter, analysis_type, data) "
                    "VALUES (?, ?, ?, ?)",
                    rows,
                )
                self.conn.commit()
            total_inserted += len(rows)
            self.stats["bible_context_chapter"] = {"inserted": len(rows)}
            print(f"    Inserted: {len(rows):,}")
            self._record_provenance("per_chapter_analysis",
                                    SOURCE_FILES["per_chapter_analysis"],
                                    len(rows))

        # 2c. Topic clusters → bible_context (analysis_type="topic")
        print("\n  [2c] topic_clusters.jsonl → bible_context")
        topics = load_jsonl(SOURCE_FILES["topic_clusters"]["path"])
        if topics:
            rows = []
            for rec in topics:
                topic = rec.get("topic", "unknown")
                data_json = safe_json(rec)
                rows.append((topic, None, "topic", data_json))
            if rows and not self.dry_run:
                cur.executemany(
                    "INSERT INTO bible_context (book, chapter, analysis_type, data) "
                    "VALUES (?, ?, ?, ?)",
                    rows,
                )
                self.conn.commit()
            total_inserted += len(rows)
            self.stats["bible_context_topic"] = {"inserted": len(rows)}
            print(f"    Inserted: {len(rows):,}")
            self._record_provenance("topic_clusters",
                                    SOURCE_FILES["topic_clusters"], len(rows))

        # 2d. Sentence patterns → grammar_patterns (new patterns)
        print("\n  [2d] sentence_patterns.jsonl → grammar_patterns")
        sent_pats = load_jsonl(SOURCE_FILES["sentence_patterns"]["path"])
        if sent_pats:
            # Get existing pattern_ids to avoid duplicates
            cur.execute("SELECT pattern_id FROM grammar_patterns")
            existing_ids = {r[0] for r in cur.fetchall()}

            rows = []
            for i, rec in enumerate(sent_pats):
                pid = f"sentence_pattern_{i}"
                if pid in existing_ids:
                    continue
                book = rec.get("book", "")
                pattern_desc = (
                    f"{rec.get('book_name', '')} "
                    f"(SOV: {rec.get('sov_rate', 0):.1%}, "
                    f"neg: {rec.get('negation_rate', 0):.1%}, "
                    f"Q: {rec.get('question_rate', 0):.1%})"
                )
                tense_dist = rec.get("tense_distribution", {})
                examples = json.dumps(tense_dist, ensure_ascii=False)
                rows.append((
                    pid, f"book_pattern_{book}", pattern_desc,
                    "sentence_pattern", examples,
                    rec.get("verse_count", 0),
                ))
            if rows and not self.dry_run:
                cur.executemany(
                    "INSERT OR IGNORE INTO grammar_patterns "
                    "(pattern_id, pattern, description, function, examples, frequency) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    rows,
                )
                self.conn.commit()
            total_inserted += len(rows)
            self.stats["grammar_patterns"] = {"inserted": len(rows)}
            print(f"    Inserted: {len(rows):,}")
            self._record_provenance("sentence_patterns",
                                    SOURCE_FILES["sentence_patterns"], len(rows))

        # 2e. Word usage profiles → word_usage (update existing)
        print("\n  [2e] word_usage_profiles.jsonl → word_usage")
        word_profiles = load_jsonl(SOURCE_FILES["word_usage_profiles"]["path"])
        if word_profiles:
            # Build word → profiles
            word_map: dict[str, list[dict]] = {}
            for rec in word_profiles:
                w = (rec.get("word") or "").strip().lower()
                if w:
                    word_map.setdefault(w, []).append(rec)

            # Get existing words
            cur.execute("SELECT id, word, book FROM word_usage")
            existing_usage = cur.fetchall()
            existing_map: dict[str, list[tuple[int, str]]] = {}
            for uid, word_val, book_val in existing_usage:
                key = (word_val or "").lower()
                existing_map.setdefault(key, []).append((uid, book_val))

            # Update existing entries with enriched data
            updates = 0
            inserts = 0
            seen_pairs: set[tuple[str, str]] = set()
            for w, profiles in word_map.items():
                for prof in profiles:
                    book = prof.get("per_book_distribution", "")
                    if isinstance(book, list) and book:
                        book = book[0] if isinstance(book[0], str) else str(book[0])
                    elif not isinstance(book, str):
                        book = str(book)

                    key = (w.lower(), str(book))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)

                    # Check if exists
                    existing_entries = existing_map.get(w.lower(), [])
                    found = False
                    for uid, existing_book in existing_entries:
                        if existing_book == book:
                            # Update existing
                            new_freq = prof.get("total_freq", 0)
                            cur.execute(
                                "SELECT total_freq FROM word_usage WHERE id = ?",
                                (uid,),
                            )
                            old_freq = cur.fetchone()
                            if old_freq and old_freq[0] != new_freq:
                                if not self.dry_run:
                                    cur.execute(
                                        "UPDATE word_usage SET total_freq = ?, "
                                        "meaning_shifts = ?, co_occurring_words = ? "
                                        "WHERE id = ?",
                                        (new_freq,
                                         safe_json(prof.get("meaning_shifts", [])),
                                         safe_json(prof.get("all_translations", [])),
                                         uid),
                                    )
                                updates += 1
                            found = True
                            break

                    if not found:
                        # Insert new
                        new_freq = prof.get("total_freq", 0)
                        if not self.dry_run:
                            cur.execute(
                                "INSERT INTO word_usage "
                                "(word, book, total_freq, meaning_shifts, "
                                "co_occurring_words) VALUES (?, ?, ?, ?, ?)",
                                (w, book, new_freq,
                                 safe_json(prof.get("meaning_shifts", [])),
                                 safe_json(prof.get("all_translations", []))),
                            )
                        inserts += 1

            if not self.dry_run:
                self.conn.commit()
            total_inserted += updates + inserts
            self.stats["word_usage_profiles"] = {
                "updated": updates, "inserted": inserts
            }
            print(f"    Updated: {updates:,}, Inserted: {inserts:,}")
            self._record_provenance("word_usage_profiles",
                                    SOURCE_FILES["word_usage_profiles"],
                                    len(word_profiles))

        # 2f. Phrase context map → word_usage (as phrase records)
        print("\n  [2f] phrase_context_map.jsonl → word_usage")
        phrase_map = load_jsonl(SOURCE_FILES["phrase_context_map"]["path"])
        if phrase_map:
            # Store phrase context data in word_usage as compound phrases
            phrase_inserts = 0
            batch: list[tuple[str, str, int, str, str]] = []
            for rec in phrase_map:
                phrase = rec.get("phrase", "")
                freq = rec.get("frequency", 0)
                is_idiom = rec.get("is_idiomatic", False)
                locations = safe_json(rec.get("locations", []))
                ctx_words = safe_json(rec.get("context_words", []))
                if phrase:
                    batch.append((
                        phrase, f"phrase:{rec.get('type', 'bigram')}",
                        freq, locations, ctx_words,
                    ))
                    phrase_inserts += 1
                    if len(batch) >= 5000:
                        if not self.dry_run:
                            cur.executemany(
                                "INSERT INTO word_usage "
                                "(word, book, total_freq, meaning_shifts, "
                                "co_occurring_words) VALUES (?, ?, ?, ?, ?)",
                                batch,
                            )
                            self.conn.commit()
                        batch = []
            if batch and not self.dry_run:
                cur.executemany(
                    "INSERT INTO word_usage "
                    "(word, book, total_freq, meaning_shifts, "
                    "co_occurring_words) VALUES (?, ?, ?, ?, ?)",
                    batch,
                )
                self.conn.commit()
            total_inserted += phrase_inserts
            self.stats["phrase_context_map"] = {"inserted": phrase_inserts}
            print(f"    Inserted: {phrase_inserts:,}")
            self._record_provenance("phrase_context_map",
                                    SOURCE_FILES["phrase_context_map"],
                                    phrase_inserts)

        self._audit_bulk("bible_context", total_inserted,
                         "bible_context_ingestion_v2")
        print(f"\n  TOTAL bible context rows: {total_inserted:,}")

    # ===================================================================
    # 3. TRAINING EXERCISES (REPLACE)
    # ===================================================================
    def ingest_training_exercises(self) -> None:
        """Clear old exercises and insert fresh."""
        print("\n=== 3. TRAINING EXERCISES (REPLACE) ===")
        cur = self.conn.cursor()
        total_inserted = 0

        exercise_configs = [
            ("negation", "negation_exercises",
             "negation", "medium",
             ["instruction", "input", "output", "negation_type", "reference"]),
            ("question", "question_exercises",
             "question", "medium",
             ["instruction", "input", "output", "question_type", "reference"]),
            ("pronoun", "pronoun_exercises",
             "pronoun", "medium",
             ["instruction", "input", "output", "grammar_point", "reference"]),
            ("error_correction", "error_correction_exercises",
             "error_correction", "hard",
             ["instruction", "input", "output", "error_type", "reference"]),
            ("conditional", "conditional_exercises",
             "conditional", "hard",
             ["instruction", "input", "output", "grammar_point", "reference"]),
        ]

        # Count old
        cur.execute("SELECT COUNT(*) FROM training_exercises")
        old_count = cur.fetchone()[0]
        print(f"  Old exercises: {old_count:,}")

        # Clear old
        if not self.dry_run:
            cur.execute("DELETE FROM training_exercises")
            self.conn.commit()
        print(f"  Cleared old exercises")

        for name, source_key, ex_type, difficulty, _ in exercise_configs:
            print(f"\n  [3] {name}_exercises.jsonl → training_exercises")
            data = load_jsonl(SOURCE_FILES[source_key]["path"])
            if not data:
                continue

            batch: list[tuple] = []
            for rec in data:
                zolai_text = rec.get("output", "")
                eng_text = rec.get("input", "")
                if not zolai_text or not eng_text:
                    continue
                ref = rec.get("reference", "")
                source_val = f"{name}_exercises:{ref}"
                batch.append((
                    ex_type, zolai_text, eng_text,
                    source_val, difficulty,
                ))

            # Insert in batches
            for i in range(0, len(batch), 5000):
                chunk = batch[i:i + 5000]
                if not self.dry_run:
                    cur.executemany(
                        "INSERT INTO training_exercises "
                        "(exercise_type, zolai, english, source, difficulty) "
                        "VALUES (?, ?, ?, ?, ?)",
                        chunk,
                    )
                    self.conn.commit()
                total_inserted += len(chunk)
                self._progress(f"    {name}", i + len(chunk), len(batch))

            self.stats[f"exercise_{name}"] = {"inserted": len(batch)}
            print(f"    Inserted: {len(batch):,}")
            self._record_provenance(source_key, SOURCE_FILES[source_key],
                                    len(batch))

        self._audit_bulk("training_exercises", total_inserted,
                         "training_exercises_replace_v2")
        print(f"\n  TOTAL exercises inserted: {total_inserted:,}")

    # ===================================================================
    # 4. RAW EN→MY TRANSLATIONS
    # ===================================================================
    def ingest_raw_en_my(self) -> None:
        """Ingest raw EN→MY parallel data into translations table."""
        print("\n=== 4. RAW EN→MY TRANSLATIONS ===")
        cur = self.conn.cursor()
        total_inserted = 0

        # 4a. en_my_parallel
        print("\n  [4a] en_my_parallel.jsonl → translations (en→my)")
        parallel = load_jsonl(SOURCE_FILES["en_my_parallel"]["path"])
        if parallel:
            batch: list[tuple] = []
            for rec in parallel:
                en_text = rec.get("en", "").strip()
                my_text = rec.get("my", "").strip()
                if not en_text or not my_text:
                    continue
                source_val = rec.get("source", "en_my_parallel")
                batch.append((
                    en_text, my_text, "en→my",
                    f"parallel:{source_val}", 0.8,
                ))

            for i in range(0, len(batch), 5000):
                chunk = batch[i:i + 5000]
                if not self.dry_run:
                    cur.executemany(
                        "INSERT INTO translations "
                        "(source, target, direction, reference, confidence) "
                        "VALUES (?, ?, ?, ?, ?)",
                        chunk,
                    )
                    self.conn.commit()
                total_inserted += len(chunk)
                self._progress("    parallel", i + len(chunk), len(batch))

            self.stats["en_my_parallel"] = {"inserted": len(batch)}
            print(f"    Inserted: {len(batch):,}")
            self._record_provenance("en_my_parallel",
                                    SOURCE_FILES["en_my_parallel"], len(batch))

        # 4b. en_my_news
        print("\n  [4b] en_my_news.jsonl → translations (en→my)")
        news = load_jsonl(SOURCE_FILES["en_my_news"]["path"])
        if news:
            batch2: list[tuple] = []
            for rec in news:
                en_text = rec.get("en", "").strip()
                my_text = rec.get("my", "").strip()
                if not en_text or not my_text:
                    continue
                source_val = rec.get("source", "en_my_news")
                tagged = "political" if rec.get("tags") else "clean"
                batch2.append((
                    en_text, my_text, "en→my",
                    f"news:{source_val}:{tagged}", 0.7,
                ))

            for i in range(0, len(batch2), 5000):
                chunk = batch2[i:i + 5000]
                if not self.dry_run:
                    cur.executemany(
                        "INSERT INTO translations "
                        "(source, target, direction, reference, confidence) "
                        "VALUES (?, ?, ?, ?, ?)",
                        chunk,
                    )
                    self.conn.commit()
                total_inserted += len(chunk)
                self._progress("    news", i + len(chunk), len(batch2))

            self.stats["en_my_news"] = {"inserted": len(batch2)}
            print(f"    Inserted: {len(batch2):,}")
            self._record_provenance("en_my_news",
                                    SOURCE_FILES["en_my_news"], len(batch2))

        # 4c. my_dictionary → dictionary_en_zo (Myanmar words with meanings)
        print("\n  [4c] my_dictionary.jsonl → dictionary_en_zo (myanmar)")
        my_dict = load_jsonl(SOURCE_FILES["my_dictionary"]["path"])
        if my_dict:
            # Check existing headwords to avoid duplicates
            cur.execute("SELECT headword FROM dictionary_en_zo")
            existing_hw = {r[0] for r in cur.fetchall()}

            batch3: list[tuple] = []
            for rec in my_dict:
                word = rec.get("word", "").strip()
                meaning = rec.get("meaning", "").strip()
                pos = rec.get("pos", "").strip()
                if not word:
                    continue
                # Skip if already exists
                if word in existing_hw:
                    continue
                translations = json.dumps([meaning], ensure_ascii=False)
                batch3.append((
                    word, translations, meaning[:100] if meaning else "",
                    pos, "Rickaym/Burmese-Dictionary",
                ))
                existing_hw.add(word)  # avoid intra-batch dupes

            for i in range(0, len(batch3), 5000):
                chunk = batch3[i:i + 5000]
                if not self.dry_run:
                    cur.executemany(
                        "INSERT INTO dictionary_en_zo "
                        "(headword, translations, translations_clean, pos, source) "
                        "VALUES (?, ?, ?, ?, ?)",
                        chunk,
                    )
                    self.conn.commit()
                total_inserted += len(chunk)
                self._progress("    my_dict", i + len(chunk), len(batch3))

            self.stats["my_dictionary"] = {"inserted": len(batch3)}
            print(f"    Inserted: {len(batch3):,}")
            self._record_provenance("my_dictionary",
                                    SOURCE_FILES["my_dictionary"], len(batch3))

        self._audit_bulk("translations", total_inserted,
                         "raw_en_my_ingestion_v2")
        print(f"\n  TOTAL EN→MY rows: {total_inserted:,}")

    # ===================================================================
    # 5. VOCAB ENRICHMENT
    # ===================================================================
    def ingest_vocab_enrichment(self) -> None:
        """Enrich vocab table from Bible vocab files."""
        print("\n=== 5. VOCAB ENRICHMENT ===")
        cur = self.conn.cursor()
        total_updated = 0

        # 5a. vocab_from_bible → fill missing examples
        print("\n  [5a] vocab_from_bible.jsonl → vocab.examples")
        vocab_bible = load_jsonl(SOURCE_FILES["vocab_from_bible"]["path"])
        if vocab_bible:
            vocab_map: dict[str, dict] = {}
            for rec in vocab_bible:
                w = (rec.get("word") or "").strip().lower()
                if w:
                    vocab_map[w] = rec

            cur.execute(
                "SELECT id, headword, examples FROM vocab "
                "WHERE examples = '[]' OR examples IS NULL"
            )
            empty_ex = cur.fetchall()
            ex_updates: list[tuple[str, int]] = []
            for row_id, hw, _ in empty_ex:
                rec = vocab_map.get(hw.lower())
                if not rec:
                    continue
                ex_list = rec.get("examples", [])
                if ex_list:
                    ex_json = safe_json(ex_list[:5])
                    ex_updates.append((ex_json, row_id))
                    self._audit("vocab", row_id, "examples",
                                "[]", truncate(ex_json), "vocab_from_bible")
                    total_updated += 1
            if ex_updates and not self.dry_run:
                cur.executemany(
                    "UPDATE vocab SET examples = ? WHERE id = ?",
                    ex_updates,
                )
                self.conn.commit()
            self.stats["vocab_bible"] = {"examples_filled": len(ex_updates)}
            print(f"    Examples filled: {len(ex_updates):,}")
            self._record_provenance("vocab_from_bible",
                                    SOURCE_FILES["vocab_from_bible"],
                                    len(vocab_bible))

        # 5b. ALL_WORDS_WITH_FREQUENCY → fill missing frequency
        print("\n  [5b] ALL_WORDS_WITH_FREQUENCY.jsonl → vocab.frequency")
        freq_words = load_jsonl(SOURCE_FILES["all_words_frequency"]["path"])
        if freq_words:
            freq_map: dict[str, dict] = {}
            for rec in freq_words:
                w = (rec.get("word") or "").strip().lower()
                if w:
                    freq_map[w] = rec

            cur.execute(
                "SELECT id, headword, frequency FROM vocab "
                "WHERE frequency = 0 OR frequency IS NULL"
            )
            zero_freq = cur.fetchall()
            freq_updates: list[tuple[int, int]] = []
            for row_id, hw, _ in zero_freq:
                rec = freq_map.get(hw.lower())
                if not rec:
                    continue
                new_freq = rec.get("frequency", 0)
                if new_freq > 0:
                    freq_updates.append((new_freq, row_id))
                    self._audit("vocab", row_id, "frequency",
                                0, new_freq, "all_words_frequency")
                    total_updated += 1
            if freq_updates and not self.dry_run:
                cur.executemany(
                    "UPDATE vocab SET frequency = ? WHERE id = ?",
                    freq_updates,
                )
                self.conn.commit()
            self.stats["vocab_freq"] = {"frequency_filled": len(freq_updates)}
            print(f"    Frequency filled: {len(freq_updates):,}")
            self._record_provenance("all_words_frequency",
                                    SOURCE_FILES["all_words_frequency"],
                                    len(freq_words))

        self._audit_bulk("vocab", total_updated, "vocab_enrichment_v2")
        print(f"\n  TOTAL vocab enrichments: {total_updated:,}")

    # ===================================================================
    # 6. PROVENANCE SUMMARY
    # ===================================================================
    def finalize_provenance(self) -> None:
        """Record a summary provenance entry for this run."""
        print("\n=== 6. PROVENANCE FINALIZATION ===")
        if self.dry_run:
            print("  (dry-run: skipping)")
            return
        cur = self.conn.cursor()
        summary = json.dumps({
            "script": "ingest_all_data.py",
            "version": "2.0",
            "run_timestamp": now_iso(),
            "duration_seconds": round(time.time() - self.start_time, 1),
            "stats": self.stats,
        }, ensure_ascii=False)
        cur.execute(
            "INSERT INTO provenance "
            "(filename, size_bytes, sha256, row_count, source, "
            "generator_script, version, status, updated_at, change_log) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ingest_all_data_run", 0, "run_summary",
             sum(s.get("inserted", s.get("updated", s.get("rows_affected", 0)))
                 for s in self.stats.values()),
             "full_ingestion", "ingest_all_data.py", "2.0", "active",
             now_iso(), summary),
        )
        self.conn.commit()
        print(f"  Provenance summary recorded")

    # ===================================================================
    # SUMMARY
    # ===================================================================
    def print_summary(self) -> None:
        """Print final database state."""
        elapsed = time.time() - self.start_time
        print(f"\n{'=' * 60}")
        print(f"  INGESTION COMPLETE  ({elapsed:.1f}s)")
        if self.dry_run:
            print("  *** DRY RUN — no changes written ***")
        print(f"{'=' * 60}")
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            if t in ("sqlite_sequence",):
                continue
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
        print(f"  Duration: {elapsed:.1f}s")
        print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    dry_run = "--dry-run" in sys.argv
    summary_only = "--summary" in sys.argv

    if summary_only:
        ingester = DataIngester(dry_run=False)
        ingester.print_summary()
        ingester.close()
        return

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Comprehensive Data Ingestion {'(DRY RUN)' if dry_run else ''}")
    print(f"DB: {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"Workspace: {WORKSPACE}")

    ingester = DataIngester(dry_run=dry_run)

    # Run all ingestion phases
    ingester.ingest_dictionary_enrichment()
    ingester.ingest_bible_context()
    ingester.ingest_training_exercises()
    ingester.ingest_raw_en_my()
    ingester.ingest_vocab_enrichment()
    ingester.finalize_provenance()

    # Print summary
    ingester.print_summary()
    ingester.close()


if __name__ == "__main__":
    main()
