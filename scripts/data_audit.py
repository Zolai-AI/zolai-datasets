#!/usr/bin/env python3
"""Comprehensive Data Audit — cross-validates all Zolai data sources.

Six audit classes:
  1. DictionaryAccuracyAuditor  — dict vs Bible alignments mismatch detection
  2. PhraseCoverageAuditor      — phrase attestation in Bible corpus
  3. VocabularyGapAuditor       — Bible words missing from dictionary
  4. RealWorldVsBibleAuditor    — modern corpus words vs Bible vocabulary
  5. UnknownWordDetector        — union of all sources minus dictionary
  6. GeminiCrossChecker         — AI verification of questionable entries

Usage:
  python data_audit.py --all                    # Run all 6 audits
  python data_audit.py --dict-accuracy          # Individual audit
  python data_audit.py --phrase-coverage        # Individual audit
  python data_audit.py --vocab-gaps             # Individual audit
  python data_audit.py --real-world             # Individual audit
  python data_audit.py --unknown-words          # Individual audit
  python data_audit.py --gemini-check           # Gemini batch verification
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Data paths (relative to workspace root) ─────────────────────────
WORKSPACE = Path("/home/peter/Documents/Projects/zolai-ai")
DATA_ROOT = WORKSPACE / "data"
DICT_PATH = DATA_ROOT / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
BIBLE_PATH = DATA_ROOT / "bible" / "parallel_corpus_v1.jsonl"
ALIGN_PATH = DATA_ROOT / "bible" / "word_alignments_v1.jsonl"
PHRASES_PATH = DATA_ROOT / "bible" / "phrases_v1.jsonl"
CORPUS_PATH = DATA_ROOT / "corpus" / "corpus_unified_v1.jsonl"
LOG_DIR = DATA_ROOT / "audit_logs"
CORPUS_SAMPLE_LIMIT = 100_000  # first N lines of corpus_unified


# ── Helpers ──────────────────────────────────────────────────────────

def ensure_log_dir() -> Path:
    """Create audit_logs directory if missing."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def load_jsonl_streaming(path: Path, limit: int | None = None):
    """Yield dicts from a JSONL file without loading all into memory."""
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
            count += 1
            if limit is not None and count >= limit:
                return


def load_jsonl_list(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load JSONL into a list (for small-to-medium files)."""
    return list(load_jsonl_streaming(path, limit))


def ts() -> str:
    """Timestamp string."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def print_progress(label: str, current: int, total: int, every: int = 1000) -> None:
    """Print progress line every `every` items."""
    if current % every == 0 or current == total:
        pct = current / total * 100 if total else 0
        print(f"  [{label}] {current:>8,}/{total:>8,} ({pct:5.1f}%)", flush=True)


def save_json(data: Any, path: Path) -> None:
    """Write JSON to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"  Saved JSON → {path}")


def save_md(lines: list[str], path: Path) -> None:
    """Write markdown to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  Saved MD → {path}")


# =====================================================================
# 1. DICTIONARY ACCURACY AUDITOR
# =====================================================================

class DictionaryAccuracyAuditor:
    """Compare dict headword EN translations against Bible word alignments.

    Loads word_alignments_v1.jsonl (385K pairs).  For every unique ZO headword,
    collects all EN translations from alignments.  Then loads the dictionary
    and checks whether the dict's EN meaning appears among the Bible
    alignments for that word.
    """

    def __init__(self) -> None:
        self._bible_translations: dict[str, Counter[str]] = {}
        self._loaded = False

    def _load_alignments(self) -> None:
        if self._loaded:
            return
        print(f"\n{'='*60}")
        print("1. DICTIONARY ACCURACY AUDITOR")
        print(f"{'='*60}")
        print(f"  Loading {ALIGN_PATH.name} (streaming)...")
        for count, row in enumerate(load_jsonl_streaming(ALIGN_PATH), 1):
            zo = row.get("zo_word", "").strip().lower()
            en = row.get("en_word", "").strip()
            if zo and en and en != "-1":
                self._bible_translations.setdefault(zo, Counter())[en] += 1
            print_progress("load_align", count, 385_120)
        self._loaded = True
        print(f"  Loaded {len(self._bible_translations):,} unique ZO words from alignments")

    def run(self) -> dict[str, Any]:
        self._load_alignments()

        print(f"  Loading dictionary from {DICT_PATH.name}...")
        dict_entries = load_jsonl_list(DICT_PATH)
        print(f"  Loaded {len(dict_entries):,} dictionary entries")

        mismatches: list[dict[str, Any]] = []
        no_alignment: list[dict[str, Any]] = []
        checked = 0

        for entry in dict_entries:
            zo = entry.get("zolai", "").strip().lower()
            en_raw = entry.get("english_clean", "") or str(entry.get("english", ""))
            if isinstance(en_raw, list):
                en_raw = ", ".join(en_raw)
            en_clean = en_raw.strip().lower()
            if not zo or len(zo) < 2 or not en_clean:
                continue

            checked += 1
            print_progress("check", checked, len(dict_entries), every=5000)

            if zo not in self._bible_translations:
                no_alignment.append({
                    "zolai": zo,
                    "dict_en": en_clean[:120],
                    "note": "no Bible alignment found",
                })
                continue

            # Check if dict's first meaning word appears in Bible translations
            bible_ens = self._bible_translations[zo]
            en_words = {w.strip().lower() for w in en_clean.split(",")}
            # Simple containment check
            found = False
            for ew in en_words:
                for bet in bible_ens:
                    if ew in bet or bet in ew:
                        found = True
                        break
                if found:
                    break

            if not found:
                top_bible = bible_ens.most_common(5)
                mismatches.append({
                    "zolai": zo,
                    "dict_en": en_clean[:120],
                    "bible_top": [{"en": e, "count": c} for e, c in top_bible],
                    "bible_total": sum(bible_ens.values()),
                    "severity": "HIGH",
                })

        result = {
            "audit": "dict_accuracy",
            "timestamp": ts(),
            "total_dict_entries": len(dict_entries),
            "checked": checked,
            "mismatches": len(mismatches),
            "no_alignment": len(no_alignment),
            "mismatch_details": mismatches[:200],  # cap output
            "no_alignment_sample": no_alignment[:100],
        }

        print(f"\n  RESULT: {len(mismatches):,} mismatches, "
              f"{len(no_alignment):,} words with no alignment")
        return result


# =====================================================================
# 2. PHRASE COVERAGE AUDITOR
# =====================================================================

class PhraseCoverageAuditor:
    """Check each phrase against the Bible parallel corpus for attestation."""

    def __init__(self) -> None:
        self._bible_zo: list[str] = []

    def run(self) -> dict[str, Any]:
        print(f"\n{'='*60}")
        print("2. PHRASE COVERAGE AUDITOR")
        print(f"{'='*60}")

        # Stream Bible verses into a searchable list of Zolai text
        print("  Loading Bible Zolai text (streaming)...")
        for count, row in enumerate(load_jsonl_streaming(BIBLE_PATH), 1):
            zo = row.get("zo_tdb77", "") or row.get("zo_tedim2010", "")
            if zo:
                self._bible_zo.append(zo.lower())
            print_progress("load_bible", count, 31_102)
        print(f"  Loaded {len(self._bible_zo):,} verses")

        # Load phrases
        print(f"  Loading phrases from {PHRASES_PATH.name}...")
        phrases = load_jsonl_list(PHRASES_PATH)
        print(f"  Loaded {len(phrases):,} phrases")

        zero_attested: list[dict[str, Any]] = []
        low_attested: list[dict[str, Any]] = []
        checked = 0

        # Join Bible text for faster substring search
        bible_joined = "\n".join(self._bible_zo)

        for phrase in phrases:
            zo = phrase.get("zo", "").strip().lower()
            if not zo:
                continue
            checked += 1
            print_progress("check", checked, len(phrases), every=500)

            count_match = bible_joined.count(zo)
            freq = phrase.get("frequency", 0)

            entry = {
                "phrase": zo,
                "declared_freq": freq,
                "bible_attestation": count_match,
            }

            if count_match == 0:
                entry["severity"] = "HIGH"
                entry["note"] = "zero Bible attestation"
                zero_attested.append(entry)
            elif count_match < 3:
                entry["severity"] = "MEDIUM"
                entry["note"] = "very low attestation"
                low_attested.append(entry)

        result = {
            "audit": "phrase_coverage",
            "timestamp": ts(),
            "total_phrases": len(phrases),
            "checked": checked,
            "zero_attested": len(zero_attested),
            "low_attested": len(low_attested),
            "zero_attested_details": zero_attested[:200],
            "low_attested_details": low_attested[:100],
        }

        print(f"\n  RESULT: {len(zero_attested):,} zero-attested, "
              f"{len(low_attested):,} low-attestation phrases")
        return result


# =====================================================================
# 3. VOCABULARY GAP AUDITOR
# =====================================================================

class VocabularyGapAuditor:
    """Find Bible words that are NOT in the dictionary — the coverage gaps."""

    def __init__(self) -> None:
        self._dict_headwords: set[str] = set()

    def run(self) -> dict[str, Any]:
        print(f"\n{'='*60}")
        print("3. VOCABULARY GAP AUDITOR")
        print(f"{'='*60}")

        # Load dictionary headwords (small enough for a set)
        print("  Loading dictionary headwords...")
        for count, row in enumerate(load_jsonl_streaming(DICT_PATH), 1):
            z = row.get("zolai", "").strip().lower()
            if z and len(z) >= 2:
                self._dict_headwords.add(z)
            print_progress("load_dict", count, 93_931, every=5000)
        print(f"  Loaded {len(self._dict_headwords):,} dictionary headwords")

        # Stream Bible verses and extract unique words
        print("  Streaming Bible verses...")
        bible_freq: Counter[str] = Counter()
        for verse_count, row in enumerate(load_jsonl_streaming(BIBLE_PATH), 1):
            zo = row.get("zo_tdb77", "") or row.get("zo_tedim2010", "")
            if zo:
                tokens = _tokenize_zolai(zo)
                bible_freq.update(tokens)
            print_progress("bible", verse_count, 31_102)
        print(f"  Extracted {len(bible_freq):,} unique Zolai words from Bible")

        # Find gaps
        gaps: list[dict[str, Any]] = []
        for word, freq in bible_freq.most_common():
            if word not in self._dict_headwords:
                gaps.append({
                    "word": word,
                    "bible_freq": freq,
                    "severity": "HIGH" if freq >= 50 else "MEDIUM" if freq >= 10 else "LOW",
                })

        result = {
            "audit": "vocab_gaps",
            "timestamp": ts(),
            "bible_unique_words": len(bible_freq),
            "dict_headwords": len(self._dict_headwords),
            "gaps_count": len(gaps),
            "gaps_high": sum(1 for g in gaps if g["severity"] == "HIGH"),
            "gaps_medium": sum(1 for g in gaps if g["severity"] == "MEDIUM"),
            "gaps_low": sum(1 for g in gaps if g["severity"] == "LOW"),
            "gaps_details": gaps[:500],
        }

        print(f"\n  RESULT: {len(gaps):,} Bible words missing from dictionary "
              f"({sum(1 for g in gaps if g['severity']=='HIGH'):,} high-freq)")
        return result


# =====================================================================
# 4. REAL-WORLD VS BIBLE AUDITOR
# =====================================================================

class RealWorldVsBibleAuditor:
    """Compare modern corpus vocabulary against Bible vocabulary.

    Samples first 100K lines of corpus_unified_v1.jsonl, extracts words,
    compares against Bible vocabulary to find modern-only words, and
    cross-checks against dictionary.
    """

    def __init__(self) -> None:
        self._bible_words: set[str] = set()
        self._dict_headwords: set[str] = set()

    def run(self) -> dict[str, Any]:
        print(f"\n{'='*60}")
        print("4. REAL-WORLD VS BIBLE AUDITOR")
        print(f"{'='*60}")

        # Load Bible words
        print("  Loading Bible vocabulary (streaming)...")
        bible_freq: Counter[str] = Counter()
        for count, row in enumerate(load_jsonl_streaming(BIBLE_PATH), 1):
            zo = row.get("zo_tdb77", "") or row.get("zo_tedim2010", "")
            if zo:
                tokens = _tokenize_zolai(zo)
                bible_freq.update(tokens)
            print_progress("bible", count, 31_102)
        self._bible_words = set(bible_freq.keys())
        print(f"  Loaded {len(self._bible_words):,} Bible words")

        # Load dictionary headwords
        print("  Loading dictionary headwords...")
        for dict_count, row in enumerate(load_jsonl_streaming(DICT_PATH), 1):
            z = row.get("zolai", "").strip().lower()
            if z and len(z) >= 2:
                self._dict_headwords.add(z)
            print_progress("dict", dict_count, 93_931, every=5000)

        # Sample corpus
        print(f"  Streaming corpus (first {CORPUS_SAMPLE_LIMIT:,} lines)...")
        corpus_freq: Counter[str] = Counter()
        corpus_lines = 0
        for row in load_jsonl_streaming(CORPUS_PATH, limit=CORPUS_SAMPLE_LIMIT):
            text = row.get("text", "")
            if text:
                tokens = _tokenize_zolai(text)
                corpus_freq.update(tokens)
            corpus_lines += 1
            print_progress("corpus", corpus_lines, CORPUS_SAMPLE_LIMIT, every=5000)
        print(f"  Sampled {corpus_lines:,} lines → {len(corpus_freq):,} unique words")

        # Classify
        modern_only: list[dict[str, Any]] = []
        modern_and_dict: list[dict[str, Any]] = []
        for word, freq in corpus_freq.most_common():
            if word in self._bible_words:
                continue
            in_dict = word in self._dict_headwords
            entry = {
                "word": word,
                "corpus_freq": freq,
                "in_bible": False,
                "in_dict": in_dict,
            }
            if in_dict:
                modern_and_dict.append(entry)
            else:
                entry["severity"] = "HIGH" if freq >= 20 else "MEDIUM" if freq >= 5 else "LOW"
                modern_only.append(entry)

        result = {
            "audit": "real_world_vs_bible",
            "timestamp": ts(),
            "corpus_sample_lines": corpus_lines,
            "corpus_unique_words": len(corpus_freq),
            "bible_unique_words": len(self._bible_words),
            "modern_only_count": len(modern_only),
            "modern_in_dict_count": len(modern_and_dict),
            "modern_only_not_in_dict": sum(1 for m in modern_only if not m["in_dict"]),
            "modern_only_high": sum(1 for m in modern_only if m["severity"] == "HIGH"),
            "modern_only_details": modern_only[:300],
            "modern_in_dict_sample": modern_and_dict[:100],
        }

        print(f"\n  RESULT: {len(modern_only):,} modern-only words "
              f"({sum(1 for m in modern_only if not m['in_dict']):,} not in dict)")
        return result


# =====================================================================
# 5. UNKNOWN WORD DETECTOR
# =====================================================================

class UnknownWordDetector:
    """Union of Bible + corpus words, minus all dictionary headwords.

    These are untranslated.  Sorted by frequency (highest first).
    """

    def __init__(self) -> None:
        self._dict_headwords: set[str] = set()

    def run(self) -> dict[str, Any]:
        print(f"\n{'='*60}")
        print("5. UNKNOWN WORD DETECTOR")
        print(f"{'='*60}")

        # Load dictionary headwords
        print("  Loading dictionary headwords...")
        for count, row in enumerate(load_jsonl_streaming(DICT_PATH), 1):
            z = row.get("zolai", "").strip().lower()
            if z and len(z) >= 2:
                self._dict_headwords.add(z)
            print_progress("dict", count, 93_931, every=5000)
        print(f"  Loaded {len(self._dict_headwords):,} headwords")

        combined_freq: Counter[str] = Counter()

        # Bible words
        print("  Streaming Bible verses...")
        for vcount, row in enumerate(load_jsonl_streaming(BIBLE_PATH), 1):
            zo = row.get("zo_tdb77", "") or row.get("zo_tedim2010", "")
            if zo:
                tokens = _tokenize_zolai(zo)
                combined_freq.update(tokens)
            print_progress("bible", vcount, 31_102)
        bible_unique = len(combined_freq)

        # Corpus sample
        print(f"  Streaming corpus (first {CORPUS_SAMPLE_LIMIT:,} lines)...")
        ccount = 0
        for row in load_jsonl_streaming(CORPUS_PATH, limit=CORPUS_SAMPLE_LIMIT):
            text = row.get("text", "")
            if text:
                tokens = _tokenize_zolai(text)
                combined_freq.update(tokens)
            ccount += 1
            print_progress("corpus", ccount, CORPUS_SAMPLE_LIMIT, every=5000)
        print(f"  Combined vocabulary: {len(combined_freq):,} unique words")

        # Find unknown
        unknown: list[dict[str, Any]] = []
        for word, freq in combined_freq.most_common():
            if word not in self._dict_headwords:
                unknown.append({
                    "word": word,
                    "total_freq": freq,
                    "severity": "CRITICAL" if freq >= 100 else
                                "HIGH" if freq >= 20 else
                                "MEDIUM" if freq >= 5 else "LOW",
                })

        result = {
            "audit": "unknown_words",
            "timestamp": ts(),
            "dict_headwords": len(self._dict_headwords),
            "bible_unique": bible_unique,
            "corpus_sample_lines": ccount,
            "combined_unique": len(combined_freq),
            "unknown_count": len(unknown),
            "unknown_critical": sum(1 for u in unknown if u["severity"] == "CRITICAL"),
            "unknown_high": sum(1 for u in unknown if u["severity"] == "HIGH"),
            "unknown_medium": sum(1 for u in unknown if u["severity"] == "MEDIUM"),
            "unknown_details": unknown[:500],
        }

        print(f"\n  RESULT: {len(unknown):,} unknown words "
              f"({sum(1 for u in unknown if u['severity'] in ('CRITICAL','HIGH')):,} critical/high)")
        return result


# =====================================================================
# 6. GEMINI CROSS-CHECKER
# =====================================================================

class GeminiCrossChecker:
    """Batch-check questionable dictionary entries via Gemini web API.

    Sends 20 entries at a time with verse context.  Gracefully skips if
    the gemini_cookies module is unavailable.
    """

    BATCH_SIZE = 20

    def __init__(self) -> None:
        self._client_available = False
        self._client = None

    def _try_load_client(self) -> bool:
        """Attempt to create Gemini client; return False on failure."""
        if self._client is not None:
            return True
        try:
            import sys
            bible_dir = str(WORKSPACE / "zolai-datasets" / "scripts" / "bible")
            if bible_dir not in sys.path:
                sys.path.insert(0, bible_dir)
            from gemini_cookies import get_gemini_client
            self._client = get_gemini_client()
            self._client_available = True
            print("  Gemini client loaded successfully")
            return True
        except Exception as exc:
            print(f"  Gemini client unavailable: {exc}")
            self._client_available = False
            return False

    async def _query_gemini(self, prompt: str) -> str:
        """Query Gemini and return text response."""
        if not self._client:
            return ""
        try:
            output = await self._client.generate_content(
                prompt=prompt, model="gemini-3-flash"
            )
            text = output.text or ""
            # Strip XML artifacts
            if "<ElicitationsGroup" in text:
                text = text[: text.index("<ElicitationsGroup")].strip()
            return text.strip()
        except Exception as exc:
            return f"ERROR: {exc}"

    def run(self) -> dict[str, Any]:
        import asyncio

        print(f"\n{'='*60}")
        print("6. GEMINI CROSS-CHECKER")
        print(f"{'='*60}")

        if not self._try_load_client():
            return {
                "audit": "gemini_check",
                "timestamp": ts(),
                "status": "SKIPPED",
                "reason": "gemini_cookies module unavailable",
                "checked": 0,
                "discrepancies": [],
            }

        # Collect Bible verse context per headword (for the prompt)
        print("  Building word→verse context index (streaming)...")
        word_verses: dict[str, list[str]] = defaultdict(list)
        for count, row in enumerate(load_jsonl_streaming(BIBLE_PATH), 1):
            zo = (row.get("zo_tdb77") or row.get("zo_tedim2010") or "").strip()
            en = (row.get("en_kJV") or "").strip()
            ref = row.get("ref") or ""
            if zo and en:
                tokens = set(_tokenize_zolai(zo))
                for tok in tokens:
                    if len(word_verses[tok]) < 3:
                        word_verses[tok].append(f"  [{ref}] {zo} → {en[:80]}")
            print_progress("bible_idx", count, 31_102)

        # Load dictionary entries for checking
        print("  Loading dictionary for sampling...")
        entries = load_jsonl_list(DICT_PATH)

        # Sample: random selection of entries for Gemini verification
        import random
        valid_entries = [
            e for e in entries
            if e.get("zolai", "").strip() and len(e.get("zolai", "").strip()) >= 2
        ]

        # Prioritize entries with short/single-word EN (more likely to have errors)
        short_en = [
            e for e in valid_entries
            if len((e.get("english_clean", "") or "").split()) <= 2
        ]

        # Take 100 from short-EN + 100 random from all
        random.seed(42)
        sample_short = random.sample(short_en, min(100, len(short_en)))
        short_ids = {id(e) for e in sample_short}
        remaining = [e for e in valid_entries if id(e) not in short_ids]
        sample_random = random.sample(remaining, min(100, len(remaining)))
        to_check = sample_short + sample_random

        print(f"  Checking {len(to_check)} entries via Gemini ({self.BATCH_SIZE}/batch)...")

        discrepancies: list[dict[str, Any]] = []
        checked = 0

        async def _run_batches() -> None:
            nonlocal checked
            for i in range(0, len(to_check), self.BATCH_SIZE):
                batch = to_check[i : i + self.BATCH_SIZE]
                lines: list[str] = []
                for e in batch:
                    z = e.get("zolai", "").strip()
                    en = e.get("english_clean", "") or str(e.get("english", ""))
                    if isinstance(en, list):
                        en = ", ".join(en)
                    ctx = word_verses.get(z.lower(), [])
                    ctx_str = "\n".join(ctx[:2]) if ctx else "  (no Bible context)"
                    lines.append(
                        f"Word: {z}\n"
                        f"Our translation: {en[:100]}\n"
                        f"Bible context:\n{ctx_str}"
                    )

                prompt = (
                    "You are a Tedim Zolai language expert. For each word below, "
                    "tell me: CORRECT or WRONG, and what the correct English meaning "
                    "should be. Reply format per word:\n"
                    "WORD|CORRECT/WRONG|correct_meaning|notes\n\n"
                    + "\n---\n".join(lines)
                )

                response = await self._query_gemini(prompt)
                if response.startswith("ERROR"):
                    print(f"  Batch {i}: {response}")
                    continue

                for line in response.split("\n"):
                    line = line.strip()
                    if "|" in line and line[0].isalpha():
                        parts = line.split("|", 3)
                        if len(parts) >= 3:
                            word = parts[0].strip().lower()
                            verdict = parts[1].strip().upper()
                            correct = parts[2].strip() if len(parts) > 2 else ""
                            notes = parts[3].strip() if len(parts) > 3 else ""
                            if verdict == "WRONG":
                                # Find our definition
                                our_en = ""
                                for e in batch:
                                    if e.get("zolai", "").strip().lower() == word:
                                        our_en = e.get("english_clean", "") or str(
                                            e.get("english", "")
                                        )
                                        break
                                discrepancies.append({
                                    "word": word,
                                    "our_definition": str(our_en)[:120],
                                    "gemini_correction": correct[:120],
                                    "notes": notes[:200],
                                    "severity": "HIGH",
                                })

                checked += len(batch)
                print_progress("gemini", checked, len(to_check), every=self.BATCH_SIZE)
                await asyncio.sleep(2)  # rate limit

        asyncio.run(_run_batches())

        result = {
            "audit": "gemini_check",
            "timestamp": ts(),
            "status": "COMPLETED",
            "checked": checked,
            "discrepancies_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

        print(f"\n  RESULT: {checked} checked, {len(discrepancies)} discrepancies")
        return result


# =====================================================================
# TOKENIZER
# =====================================================================

_WORD_RE = re.compile(r"[a-zA-Z']+")


def _tokenize_zolai(text: str) -> list[str]:
    """Lowercase tokenize into word-like tokens."""
    return [w.lower() for w in _WORD_RE.findall(text) if len(w) >= 2]


# =====================================================================
# REPORT GENERATOR
# =====================================================================

def generate_report(results: list[dict[str, Any]], log_dir: Path) -> tuple[Path, Path]:
    """Write JSON report + MD summary. Returns (json_path, md_path)."""
    today = datetime.now(tz=None).date().isoformat()
    json_path = log_dir / f"data_audit_{today}.json"
    md_path = log_dir / "DATA_AUDIT_REPORT.md"

    # ── JSON ──
    save_json(results, json_path)

    # ── Markdown ──
    lines: list[str] = [
        "# Zolai Data Audit Report",
        f"**Generated:** {ts()}",
        "",
        "---",
        "",
    ]

    for r in results:
        audit = r.get("audit", "unknown")
        lines.append(f"## {audit.replace('_', ' ').title()}")
        lines.append("")

        # Summary table
        if audit == "dict_accuracy":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Dictionary entries | {r.get('total_dict_entries', 0):,} |")
            lines.append(f"| Checked | {r.get('checked', 0):,} |")
            lines.append(f"| Mismatches | **{r.get('mismatches', 0):,}** |")
            lines.append(f"| No alignment | {r.get('no_alignment', 0):,} |")
            lines.append("")
            details = r.get("mismatch_details", [])
            if details:
                lines.append("### Top Mismatches (first 20)")
                lines.append("")
                lines.append("| Zolai | Dict EN | Bible Top | Severity |")
                lines.append("|-------|---------|-----------|----------|")
                for d in details[:20]:
                    btop = ", ".join(x["en"] for x in d.get("bible_top", [])[:3])
                    lines.append(
                        f"| {d['zolai']} | {d['dict_en'][:40]} | "
                        f"{btop[:40]} | {d['severity']} |"
                    )
                lines.append("")

        elif audit == "phrase_coverage":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Total phrases | {r.get('total_phrases', 0):,} |")
            lines.append(f"| Zero attested | **{r.get('zero_attested', 0):,}** |")
            lines.append(f"| Low attested | {r.get('low_attested', 0):,} |")
            lines.append("")

        elif audit == "vocab_gaps":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Bible unique words | {r.get('bible_unique_words', 0):,} |")
            lines.append(f"| Dictionary headwords | {r.get('dict_headwords', 0):,} |")
            lines.append(f"| Gaps | **{r.get('gaps_count', 0):,}** |")
            lines.append(f"| High-freq gaps | {r.get('gaps_high', 0):,} |")
            lines.append(f"| Medium gaps | {r.get('gaps_medium', 0):,} |")
            lines.append("")
            details = r.get("gaps_details", [])
            if details:
                lines.append("### Top 30 Vocabulary Gaps")
                lines.append("")
                lines.append("| Word | Bible Freq | Severity |")
                lines.append("|------|-----------|----------|")
                for d in details[:30]:
                    lines.append(
                        f"| {d['word']} | {d['bible_freq']:,} | {d['severity']} |"
                    )
                lines.append("")

        elif audit == "real_world_vs_bible":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Corpus sample lines | {r.get('corpus_sample_lines', 0):,} |")
            lines.append(f"| Corpus unique words | {r.get('corpus_unique_words', 0):,} |")
            lines.append(f"| Bible unique words | {r.get('bible_unique_words', 0):,} |")
            lines.append(
                f"| Modern-only (not in Bible) | "
                f"**{r.get('modern_only_count', 0):,}** |"
            )
            lines.append(
                f"| Modern-only NOT in dict | "
                f"**{r.get('modern_only_not_in_dict', 0):,}** |"
            )
            lines.append("")

        elif audit == "unknown_words":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Dict headwords | {r.get('dict_headwords', 0):,} |")
            lines.append(f"| Combined unique words | {r.get('combined_unique', 0):,} |")
            lines.append(
                f"| Unknown words | **{r.get('unknown_count', 0):,}** |"
            )
            lines.append(
                f"| Critical (freq ≥100) | {r.get('unknown_critical', 0):,} |"
            )
            lines.append(
                f"| High (freq ≥20) | {r.get('unknown_high', 0):,} |"
            )
            lines.append("")
            details = r.get("unknown_details", [])
            if details:
                lines.append("### Top 30 Unknown Words (by frequency)")
                lines.append("")
                lines.append("| Word | Freq | Severity |")
                lines.append("|------|------|----------|")
                for d in details[:30]:
                    lines.append(
                        f"| {d['word']} | {d['total_freq']:,} | {d['severity']} |"
                    )
                lines.append("")

        elif audit == "gemini_check":
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Status | {r.get('status', 'N/A')} |")
            lines.append(f"| Entries checked | {r.get('checked', 0):,} |")
            lines.append(
                f"| Discrepancies | **{r.get('discrepancies_count', 0):,}** |"
            )
            lines.append("")

    # Overall summary
    lines.append("---")
    lines.append("")
    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Audit | Key Finding |")
    lines.append("|-------|-------------|")
    for r in results:
        audit = r.get("audit", "unknown")
        if audit == "dict_accuracy":
            lines.append(
                f"| Dict Accuracy | {r.get('mismatches', 0):,} mismatches vs Bible |"
            )
        elif audit == "phrase_coverage":
            lines.append(
                f"| Phrase Coverage | "
                f"{r.get('zero_attested', 0):,} zero-attested phrases |"
            )
        elif audit == "vocab_gaps":
            lines.append(
                f"| Vocab Gaps | "
                f"{r.get('gaps_count', 0):,} Bible words missing from dict |"
            )
        elif audit == "real_world_vs_bible":
            lines.append(
                f"| Real-World vs Bible | "
                f"{r.get('modern_only_count', 0):,} modern-only words |"
            )
        elif audit == "unknown_words":
            lines.append(
                f"| Unknown Words | "
                f"{r.get('unknown_count', 0):,} total unknown |"
            )
        elif audit == "gemini_check":
            lines.append(
                f"| Gemini Cross-Check | "
                f"{r.get('discrepancies_count', 0):,} AI-flagged issues |"
            )
    lines.append("")

    save_md(lines, md_path)
    return json_path, md_path


# =====================================================================
# CLI
# =====================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Zolai comprehensive data audit — cross-validates all data sources"
    )
    p.add_argument("--all", action="store_true", help="Run all 6 audits")
    p.add_argument("--dict-accuracy", action="store_true", help="Dictionary accuracy audit")
    p.add_argument("--phrase-coverage", action="store_true", help="Phrase coverage audit")
    p.add_argument("--vocab-gaps", action="store_true", help="Vocabulary gap audit")
    p.add_argument("--real-world", action="store_true", help="Real-world vs Bible audit")
    p.add_argument("--unknown-words", action="store_true", help="Unknown word detection")
    p.add_argument("--gemini-check", action="store_true", help="Gemini batch verification")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_all = args.all or not any([
        args.dict_accuracy, args.phrase_coverage, args.vocab_gaps,
        args.real_world, args.unknown_words, args.gemini_check,
    ])

    log_dir = ensure_log_dir()
    results: list[dict[str, Any]] = []

    t0 = time.time()

    if run_all or args.dict_accuracy:
        results.append(DictionaryAccuracyAuditor().run())

    if run_all or args.phrase_coverage:
        results.append(PhraseCoverageAuditor().run())

    if run_all or args.vocab_gaps:
        results.append(VocabularyGapAuditor().run())

    if run_all or args.real_world:
        results.append(RealWorldVsBibleAuditor().run())

    if run_all or args.unknown_words:
        results.append(UnknownWordDetector().run())

    if run_all or args.gemini_check:
        results.append(GeminiCrossChecker().run())

    elapsed = time.time() - t0

    # Generate reports
    json_path, md_path = generate_report(results, log_dir)

    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE — {elapsed:.1f}s")
    print(f"  JSON report: {json_path}")
    print(f"  MD report:   {md_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
