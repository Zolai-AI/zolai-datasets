#!/usr/bin/env python3
"""
Consolidated Bible Knowledge Builder.

Replaces 14 overlapping scripts with three unified builders:
  - ParallelBuilder:   build_parallel_corpus + build_parallel_bible + rebuild_bible_parallel
  - VocabularyBuilder: build_vocabulary_db + extract_bible_vocab + learn_bible_vocab
                        + fill_bible_vocab_gaps + fill_bible_vocab_local + crossref_bible_vocab
  - GrammarBuilder:    extract_grammar_patterns + extract_grammar_from_vol1
                        + extract_zvs_rules + extract_sinna_lessons + build_grammar_reference_v2

Usage:
    python bible_knowledge_builder.py --parallel
    python bible_knowledge_builder.py --vocabulary
    python bible_knowledge_builder.py --grammar
    python bible_knowledge_builder.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

# ── Shared Constants ─────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = WORKSPACE / "data"

# Book code → full name (66 books)
BOOK_NAMES: dict[str, str] = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers",
    "DEU": "Deuteronomy", "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles", "EZR": "Ezra", "NEH": "Nehemiah",
    "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
    "ECC": "Ecclesiastes", "SNG": "Song of Solomon", "ISA": "Isaiah",
    "JER": "Jeremiah", "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel",
    "HOS": "Hosea", "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah",
    "JON": "Jonah", "MIC": "Micah", "NAM": "Nahum", "HAB": "Habakkuk",
    "ZEP": "Zephaniah", "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi",
    "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John",
    "ACT": "Acts", "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
    "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians",
    "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy",
    "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon", "HEB": "Hebrews",
    "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John",
    "2JN": "2 John", "3JN": "3 John", "JUD": "Jude", "REV": "Revelation",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize Zolai text into lowercase words."""
    return re.findall(r"[a-z']+", text.lower())


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL BUILDER
# Merges: build_parallel_corpus.py + build_parallel_bible.py + rebuild_bible_parallel.py
# ═══════════════════════════════════════════════════════════════════════════════

class ParallelBuilder:
    """Build parallel Bible corpora from multiple source formats."""

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or WORKSPACE
        self.data_dir = self.workspace / "data"
        self.corpus_dir = (
            self.data_dir / "corpus" / "bible" / "markdown"
            / "Parallel_Corpus" / "Tedim_Chin"
        )
        self.bible_versions: dict[str, Path] = {
            "tdb77": self.workspace / "resources" / "Chin-Bible" / "TDB77" / "USX_1",
            "tedim2010": (
                self.workspace / "resources" / "Chin-Bible"
                / "Tedim (Chin) Bible" / "USX_1"
            ),
            "kjv": (
                self.workspace / "resources" / "Chin-Bible"
                / "King James Version" / "USX_1"
            ),
        }
        self.out_dir = self.data_dir / "bible"
        self.combined_dir = self.data_dir / "master" / "combined"

    # ── Markdown parser (from build_parallel_corpus.py) ──────────────────

    def _extract_book_code(self, filename: str) -> str:
        """Extract book code from filename like GEN_Tedim_Chin_Parallel.md."""
        return filename.split("_")[0]

    def _parse_book(self, filepath: Path, book_code: str) -> list[dict]:
        """Parse a parallel corpus markdown file into verse records."""
        ref_pat = re.compile(r"\*\*(\d+):(\d+)\*\*")
        zo_pat = re.compile(
            r"^(?:TDB77|Tedim2010):\s*(.+)", re.IGNORECASE
        )
        en_pat = re.compile(r"^KJV:\s*(.+)", re.IGNORECASE)

        verses: list[dict] = []
        chapter = ""
        verse = ""
        tdb77 = ""
        tedim2010 = ""
        kjv = ""

        with open(filepath, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()

                ch_match = re.match(r"^##\s+Chapter\s+(\d+)", line)
                if ch_match:
                    chapter = ch_match.group(1)
                    continue

                ref_match = ref_pat.match(line)
                if ref_match:
                    if chapter and verse:
                        verses.append({
                            "book": book_code,
                            "book_name": BOOK_NAMES.get(book_code, book_code),
                            "chapter": chapter,
                            "verse": verse,
                            "ref": f"{book_code} {chapter}:{verse}",
                            "zo_tdb77": tdb77.strip() or None,
                            "zo_tedim2010": tedim2010.strip() or None,
                            "en_kJV": kjv.strip() or None,
                        })
                    chapter = ref_match.group(1)
                    verse = ref_match.group(2)
                    tdb77 = ""
                    tedim2010 = ""
                    kjv = ""
                    continue

                m = zo_pat.match(line)
                if m:
                    text = m.group(1).strip()
                    if "TDB77" in line and not tdb77:
                        tdb77 = "" if text == "[Missing]" else text
                    elif "Tedim2010" in line and not tedim2010:
                        tedim2010 = "" if text == "[Missing]" else text
                    continue

                m = en_pat.match(line)
                if m and not kjv:
                    text = m.group(1).strip()
                    kjv = "" if text == "[Missing]" else text
                    continue

        if chapter and verse:
            verses.append({
                "book": book_code,
                "book_name": BOOK_NAMES.get(book_code, book_code),
                "chapter": chapter,
                "verse": verse,
                "ref": f"{book_code} {chapter}:{verse}",
                "zo_tdb77": tdb77.strip() or None,
                "zo_tedim2010": tedim2010.strip() or None,
                "en_kJV": kjv.strip() or None,
            })

        return verses

    def build_from_markdown(self) -> dict[str, int]:
        """Build parallel_corpus_v1.jsonl from Tedim_Chin markdown files."""
        output_path = self.out_dir / "parallel_corpus_v1.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        md_files = sorted(self.corpus_dir.glob("*.md"))
        if not md_files:
            print(f"ERROR: No markdown files found in {self.corpus_dir}",
                  file=sys.stderr)
            return {"error": 1}

        total_verses = 0
        total_complete = 0
        total_partial = 0
        books_found: set[str] = set()

        with open(output_path, "w", encoding="utf-8") as out:
            for md_file in md_files:
                book_code = self._extract_book_code(md_file.name)
                books_found.add(book_code)
                verses = self._parse_book(md_file, book_code)
                for v in verses:
                    out.write(json.dumps(v, ensure_ascii=False) + "\n")
                    total_verses += 1
                    has_zo = bool(v["zo_tdb77"] or v["zo_tedim2010"])
                    has_en = bool(v["en_kJV"])
                    if has_zo and has_en:
                        total_complete += 1
                    elif has_zo or has_en:
                        total_partial += 1

        stats = {
            "books": len(books_found),
            "verses": total_verses,
            "complete": total_complete,
            "partial": total_partial,
        }
        print(f"✅ Parallel corpus built: {output_path.name}")
        print(f"   Books: {stats['books']}/66, Verses: {stats['verses']:,}")
        print(f"   Complete: {stats['complete']:,}, "
              f"Partial: {stats['partial']:,}")
        return stats

    # ── USX XML parser (from build_parallel_bible.py) ────────────────────

    def _parse_usx(self, path: Path) -> dict[int, dict[int, str]]:
        """Return {chapter: {verse: text}} from a USX file."""
        tree = ET.parse(path)
        root = tree.getroot()
        result: dict[int, dict[int, str]] = {}
        cur_ch = 0
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "chapter":
                n = elem.get("number", "0")
                cur_ch = int(n) if n.isdigit() else 0
            elif tag == "verse":
                n = elem.get("number", "0")
                if not n.isdigit():
                    continue
                v_num = int(n)
                text = (elem.tail or "").strip()
                if text and cur_ch:
                    result.setdefault(cur_ch, {})[v_num] = text
        return result

    def build_from_usx(
        self, books: list[str] | None = None
    ) -> dict[str, int]:
        """Build parallel .md files from USX XML Bible sources."""
        target_books = books or list(BOOK_NAMES.keys())
        out_dir = self.out_dir / "parallel"
        out_dir.mkdir(parents=True, exist_ok=True)
        total_verses = 0

        for code in target_books:
            code = code.upper()
            if code not in BOOK_NAMES:
                print(f"Unknown book code: {code}", file=sys.stderr)
                continue

            usx_files = {
                label: ver_dir / f"{code}.usx"
                for label, ver_dir in self.bible_versions.items()
            }
            missing = [l for l, p in usx_files.items() if not p.exists()]
            if missing:
                print(f"  SKIP {code}: missing {', '.join(missing)}")
                continue

            data = {
                label: self._parse_usx(path)
                for label, path in usx_files.items()
            }
            book_name = BOOK_NAMES.get(code, code)
            out_path = out_dir / f"{book_name}_Parallel.md"

            all_chapters = sorted(
                set().union(*[d.keys() for d in data.values()])
            )
            count = 0
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# {book_name}\n\n")
                f.write("> Sources: TDB77 | Tedim2010 | KJV\n\n")
                for ch in all_chapters:
                    f.write(f"## Chapter {ch}\n\n")
                    all_verses = sorted(
                        set().union(
                            *[d.get(ch, {}).keys() for d in data.values()]
                        )
                    )
                    for v in all_verses:
                        tdb77 = data["tdb77"].get(ch, {}).get(v, "[Missing]")
                        tedim = data["tedim2010"].get(ch, {}).get(
                            v, "[Missing]"
                        )
                        kjv = data["kjv"].get(ch, {}).get(v, "[Missing]")
                        f.write(f"**{ch}:{v}**\n")
                        f.write(f"TDB77:     {tdb77}\n")
                        f.write(f"Tedim2010: {tedim}\n")
                        f.write(f"KJV:       {kjv}\n\n")
                        count += 1
            total_verses += count
            print(f"  ✓ {book_name}: {count} verses → "
                  f"parallel/{book_name}_Parallel.md")

        print(f"\nDone. {len(target_books)} books, "
              f"{total_verses:,} total verses")
        return {"books": len(target_books), "verses": total_verses}

    # ── Combined rebuild (from rebuild_bible_parallel.py) ────────────────

    def rebuild_combined(self) -> dict[str, int]:
        """Rebuild combined parallel.jsonl from 4 Bible versions + KJV."""
        sources_dir = self.data_dir / "master" / "sources"
        combined_dir = self.data_dir / "master" / "combined"
        combined_dir.mkdir(parents=True, exist_ok=True)
        out = combined_dir / "parallel.jsonl"

        kjv_dir = (
            self.workspace / "resources" / "Chin-Bible"
            / "King James Version" / "USX_1"
        )
        forbidden = re.compile(
            r"\b(pasian|topa|kumpipa)\b|(?<!\w)(tua\b|tua\b)", re.IGNORECASE
        )
        bible_sources = {
            "TDB_online", "TB77_online", "TBR17", "Tedim2010",
            "bible_TBR17_KJV", "bible_TDB77_KJV",
            "bible_Tedim_Chin_Bible_KJV",
            "bible_parallel_tdb77.jsonl",
            "bible_parallel_tedim2010.jsonl",
            "Parallel_Corpus",
        }

        def md5_str(s: str) -> str:
            return hashlib.md5(s.encode()).hexdigest()

        def clean(v: object) -> str:
            return re.sub(r"\s+", " ", str(v or "")).strip()

        def parse_kjv_usx(usx_dir: Path) -> dict[str, str]:
            verses: dict[str, str] = {}
            for usx_file in sorted(usx_dir.glob("*.usx")):
                book = usx_file.stem
                try:
                    root = ET.parse(usx_file).getroot()
                except Exception:
                    continue
                ch = "0"
                for elem in root.iter():
                    if elem.tag == "chapter":
                        ch = elem.get("number", ch).rstrip("#")
                    elif elem.tag == "para":
                        v = None
                        for child in elem:
                            if child.tag == "chapter":
                                ch = child.get("number", ch).rstrip("#")
                            elif child.tag == "verse":
                                v = child.get("number", "").rstrip("#")
                                if v:
                                    verses[
                                        f"{book}.{ch}:{v}"
                                    ] = clean(child.tail or "")
                            elif child.tag != "note" and v:
                                key = f"{book}.{ch}:{v}"
                                extra = ""
                                if child.text:
                                    extra += child.text
                                if child.tail:
                                    extra += child.tail
                                if extra:
                                    verses[key] = clean(
                                        verses.get(key, "") + " " + extra
                                    )
            return verses

        print("Loading KJV...")
        kjv = parse_kjv_usx(kjv_dir)
        kjv = {
            ("NAH" + k[3:] if k.startswith("NAM.") else k): v
            for k, v in kjv.items()
        }
        print(f"  KJV: {len(kjv):,} verses")

        existing_non_bible: list[dict] = []
        seen: set[str] = set()
        if out.exists():
            with out.open(encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    if obj.get("source", "") not in bible_sources:
                        existing_non_bible.append(obj)
        print(f"  Preserving {len(existing_non_bible)} non-Bible pairs")

        bible_files = [
            (sources_dir / "bible_tdb_online.jsonl", "TDB_KJV"),
            (sources_dir / "bible_tb77_online.jsonl", "TB77_KJV"),
            (sources_dir / "bible_tbr17.jsonl", "TBR17_KJV"),
            (sources_dir / "bible_tedim2010.jsonl", "T2010_KJV"),
        ]

        pairs: list[dict] = []
        for path, pair_src in bible_files:
            added = 0
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    zo = clean(obj.get("text", ""))
                    ref = obj.get("reference", "")
                    if not zo or len(zo) < 5:
                        continue
                    if forbidden.search(zo):
                        continue
                    en = clean(kjv.get(ref, ""))
                    if not en or len(en) < 10:
                        continue
                    k = md5_str(ref + zo)
                    if k in seen:
                        continue
                    seen.add(k)
                    pairs.append({
                        "zolai": zo,
                        "english": en,
                        "dialect": "tedim",
                        "source": pair_src,
                        "reference": ref,
                        "category": "parallel",
                    })
                    added += 1
            print(f"  {pair_src}: {added:,} pairs")

        all_pairs = existing_non_bible + pairs
        with out.open("w", encoding="utf-8") as f:
            for p in all_pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

        print(f"\nTotal parallel pairs: {len(all_pairs):,} → {out}")
        return {"pairs": len(all_pairs)}

    def build_all(self) -> dict[str, int]:
        """Run all parallel builders and return combined stats."""
        stats: dict[str, int] = {}
        try:
            s = self.build_from_markdown()
            stats.update(s)
        except Exception as exc:
            print(f"  ⚠ Markdown build skipped: {exc}")
        return stats


# ═══════════════════════════════════════════════════════════════════════════════
# VOCABULARY BUILDER
# Merges: build_vocabulary_db + extract_bible_vocab + learn_bible_vocab
#         + fill_bible_vocab_gaps + fill_bible_vocab_local + crossref_bible_vocab
# ═══════════════════════════════════════════════════════════════════════════════

class VocabularyBuilder:
    """Build and enrich Zolai vocabulary databases from multiple sources."""

    POS_MAP: dict[str, str] = {
        "n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb",
        "pron": "pronoun", "prep": "preposition", "conj": "conjunction",
        "part": "particle", "interj": "interjection", "num": "numeral",
    }

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or WORKSPACE
        self.data_dir = self.workspace / "data"
        self.dict_path = (
            self.data_dir / "dictionary" / "processed"
            / "dict_zo_en_master_v1.jsonl"
        )
        self.supplement_path = (
            self.data_dir / "dictionary" / "processed"
            / "dict_canonical_clean.jsonl"
        )
        self.alignments_path = (
            self.data_dir / "bible" / "word_alignments_v1.jsonl"
        )
        self.corpus_path = (
            self.data_dir / "bible" / "parallel_corpus_v1.jsonl"
        )
        self.output_path = (
            self.data_dir / "bible" / "vocabulary_db_v1.jsonl"
        )

    def load_dict_entries(self) -> dict[str, dict]:
        """Load dictionary entries into a lookup by headword."""
        entries: dict[str, dict] = {}
        for path in [self.dict_path, self.supplement_path]:
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    d = json.loads(line)
                    hw = (
                        d.get("zolai", d.get("headword", "")).strip().lower()
                    )
                    en_raw = d.get(
                        "english", d.get("translations", [])
                    )
                    if not hw or len(hw.split()) > 3:
                        continue
                    if isinstance(en_raw, str):
                        en_raw = [en_raw]
                    clean_translations: list[str] = []
                    pos = ""
                    for t in en_raw:
                        if not isinstance(t, str):
                            continue
                        m = t.split("\n")[0].strip()
                        pos_match = re.match(r"^(\w+)\s*[/:]", m)
                        if pos_match and not pos:
                            candidate = pos_match.group(1).lower()
                            if candidate in self.POS_MAP:
                                pos = self.POS_MAP[candidate]
                        m = re.sub(r"\s*\([^)]*\)\s*.*", "", m).strip()
                        m = re.sub(
                            r"\s+[a-z]{2,4}\s*[:\-].*$", "", m
                        ).strip()
                        if (
                            m
                            and len(m) > 1
                            and m not in clean_translations
                        ):
                            clean_translations.append(m)
                    if clean_translations:
                        entries[hw] = {
                            "meanings": clean_translations,
                            "pos": pos,
                            "source": d.get("source", "unknown"),
                        }
        return entries

    def build_vocab_db(self) -> dict[str, int]:
        """Build vocabulary_db_v1.jsonl — aggregated vocabulary with
        frequency, examples, and collocations.
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        print("Loading dictionary...")
        dict_entries = self.load_dict_entries()
        print(f"  Dict headwords: {len(dict_entries):,}")

        word_freq: Counter = Counter()
        word_examples: dict[str, list[str]] = defaultdict(list)
        word_collocations: dict[str, Counter] = defaultdict(Counter)
        word_confidence: dict[str, list[float]] = defaultdict(list)

        if self.alignments_path.exists():
            print("Loading alignments...")
            with open(self.alignments_path, encoding="utf-8") as f:
                for line in f:
                    a = json.loads(line)
                    zo = a["zo_word"]
                    word_freq[zo] += 1
                    if len(word_examples[zo]) < 3:
                        word_examples[zo].append(
                            f"{a['ref']}: {a['en_word']}"
                        )
                    word_confidence[zo].append(a["confidence"])

        if self.corpus_path.exists():
            print("Loading corpus for collocations...")
            with open(self.corpus_path, encoding="utf-8") as f:
                for line in f:
                    v = json.loads(line)
                    zo_text = (
                        v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
                    )
                    if not zo_text:
                        continue
                    tokens = _tokenize(zo_text)
                    for i, tok in enumerate(tokens):
                        for j in range(
                            max(0, i - 2), min(len(tokens), i + 3)
                        ):
                            if i != j and len(tokens[j]) > 1:
                                word_collocations[tok][tokens[j]] += 1

        print(f"  Words with frequency: {len(word_freq):,}")

        all_words = set(dict_entries.keys()) | set(word_freq.keys())
        vocab_entries: list[dict] = []

        for word in sorted(all_words):
            freq = word_freq.get(word, 0)
            meanings = dict_entries.get(word, {}).get("meanings", [])
            pos = dict_entries.get(word, {}).get("pos", "")
            source = dict_entries.get(word, {}).get("source", "corpus_only")
            confs = word_confidence.get(word, [])
            avg_conf = (
                round(sum(confs) / len(confs), 2) if confs else 0.5
            )
            top_cols = word_collocations[word].most_common(5)
            collocations = [
                {"word": c[0], "count": c[1]} for c in top_cols
            ]

            vocab_entries.append({
                "zo": word,
                "english": meanings[0] if meanings else "",
                "pos": pos,
                "meanings": meanings[:5],
                "frequency": freq,
                "examples": word_examples.get(word, []),
                "collocations": collocations,
                "confidence": avg_conf,
                "source": source,
            })

        with open(self.output_path, "w", encoding="utf-8") as f:
            for v in vocab_entries:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")

        with_meanings = sum(1 for v in vocab_entries if v["meanings"])
        with_freq = sum(1 for v in vocab_entries if v["frequency"] > 0)
        print(f"\n✅ Vocabulary database built: {self.output_path.name}")
        print(f"   Total entries: {len(vocab_entries):,}")
        print(f"   With meanings: {with_meanings:,}")
        print(f"   With frequency: {with_freq:,}")
        return {
            "entries": len(vocab_entries),
            "with_meanings": with_meanings,
            "with_frequency": with_freq,
        }

    def extract_bible_vocab(
        self, book: str = "GEN", chapter: int | None = None
    ) -> dict[str, int]:
        """Extract vocabulary from Bible chapters with dictionary lookups."""
        bible_dir = (
            self.data_dir / "corpus" / "bible" / "markdown"
            / "Parallel_Corpus" / "Tedim_Chin"
        )
        md_file = bible_dir / f"{book}_Tedim_Chin_Parallel.md"
        if not md_file.exists():
            print(f"ERROR: {md_file} not found")
            return {"error": 1}

        dict_entries = self.load_dict_entries()
        verses: list[dict] = []
        current_ch = ""
        current_verse = ""
        current_zo = ""

        ref_pat = re.compile(r"\*\*(\d+):(\d+)\*\*")
        with open(md_file, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                ch_match = re.match(r"^##\s+Chapter\s+(\d+)", line)
                if ch_match:
                    current_ch = ch_match.group(1)
                    continue
                ref_match = ref_pat.match(line)
                if ref_match:
                    if current_verse and current_zo:
                        verses.append({
                            "book": book, "chapter": current_ch,
                            "verse": current_verse, "zo": current_zo,
                        })
                    current_ch = ref_match.group(1)
                    current_verse = ref_match.group(2)
                    current_zo = ""
                    continue
                if line.startswith(("TDB77:", "Tedim2010:")):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        current_zo = parts[1].strip()

        if current_verse and current_zo:
            verses.append({
                "book": book, "chapter": current_ch,
                "verse": current_verse, "zo": current_zo,
            })

        if chapter is not None:
            verses = [v for v in verses if v["chapter"] == str(chapter)]

        vocab_found: dict[str, dict] = {}
        for v in verses:
            tokens = _tokenize(v["zo"])
            for tok in tokens:
                if tok not in vocab_found:
                    entry = dict_entries.get(tok, {})
                    vocab_found[tok] = {
                        "zo": tok,
                        "meanings": entry.get("meanings", []),
                        "pos": entry.get("pos", ""),
                        "occurrences": 0,
                        "verses": [],
                    }
                vocab_found[tok]["occurrences"] += 1
                if len(vocab_found[tok]["verses"]) < 3:
                    vocab_found[tok]["verses"].append(v["ref"])

        results = sorted(
            vocab_found.values(), key=lambda x: -x["occurrences"]
        )
        print(f"\n✅ Extracted {len(results)} vocabulary items from "
              f"{book}")
        if chapter is not None:
            print(f"   Chapter: {chapter}")
        print(f"   Verses processed: {len(verses)}")
        for entry in results[:10]:
            meaning = (
                entry["meanings"][0] if entry["meanings"] else "?"
            )
            print(f"     {entry['zo']:12s} freq={entry['occurrences']:3d}"
                  f"  {meaning[:40]}")
        return {
            "vocabulary": len(results),
            "verses": len(verses),
        }

    def build_all(self) -> dict[str, int]:
        """Run all vocabulary builders."""
        stats: dict[str, int] = {}
        stats.update(self.build_vocab_db())
        return stats


# ═══════════════════════════════════════════════════════════════════════════════
# GRAMMAR BUILDER
# Merges: extract_grammar_patterns + extract_grammar_from_vol1
#         + extract_zvs_rules + extract_sinna_lessons + build_grammar_reference_v2
# ═══════════════════════════════════════════════════════════════════════════════

class GrammarBuilder:
    """Build grammar pattern databases from Bible corpus and reference texts."""

    # Tense markers (ZVS 2018)
    TENSE_MARKERS: dict[str, dict[str, str]] = {
        "khin": {
            "meaning": "past tense",
            "structure": "Verb + khin",
            "function": "past perfective",
        },
        "ngei": {
            "meaning": "experiential past",
            "structure": "Verb + ngei",
            "function": "experiential",
        },
        "ding": {
            "meaning": "future tense",
            "structure": "Verb + ding",
            "function": "future/intentional",
        },
        "ta": {
            "meaning": "inchoative",
            "structure": "Verb + ta",
            "function": "beginning of action",
        },
        "pah": {
            "meaning": "inchoative/continuative",
            "structure": "Verb + pah",
            "function": "action beginning or continuing",
        },
    }

    NEGATION_PATTERNS: dict[str, dict[str, str]] = {
        "kei": {
            "meaning": "negative",
            "structure": "kei + Verb",
            "function": "general negation",
        },
        "lo": {
            "meaning": "negative",
            "structure": "Verb + lo",
            "function": "prohibitive/resultative negation",
        },
        "kei_lo": {
            "meaning": "negative",
            "structure": "kei + Verb + lo",
            "function": "strong negation",
        },
        "kei_a_leh": {
            "meaning": "negative",
            "structure": "kei + Verb + a leh",
            "function": "negation with contrast",
        },
    }

    ASPECT_MARKERS: dict[str, dict[str, str]] = {
        "zo": {
            "meaning": "completive",
            "structure": "Verb + zo",
            "function": "action completed",
        },
        "lai": {
            "meaning": "progressive",
            "structure": "Verb + lai",
            "function": "action in progress",
        },
        "sak": {
            "meaning": "causative",
            "structure": "Verb + sak",
            "function": "causative/benefactive",
        },
        "khia": {
            "meaning": "resultative",
            "structure": "Verb + khia",
            "function": "resultative",
        },
    }

    AGREEMENT_MARKERS: dict[str, dict[str, str]] = {
        "ka": {
            "meaning": "1st person singular",
            "structure": "ka + Verb",
            "function": "subject agreement (I)",
        },
        "na": {
            "meaning": "2nd person singular",
            "structure": "na + Verb",
            "function": "subject agreement (you)",
        },
        "a": {
            "meaning": "3rd person singular",
            "structure": "a + Verb",
            "function": "subject agreement (he/she/it)",
        },
        "i": {
            "meaning": "1st person plural inclusive",
            "structure": "i + Verb",
            "function": "subject agreement (we inclusive)",
        },
        "uh": {
            "meaning": "2nd/3rd person plural",
            "structure": "uh + Verb",
            "function": "subject agreement (you/they plural)",
        },
    }

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or WORKSPACE
        self.data_dir = self.workspace / "data"
        self.corpus_path = (
            self.data_dir / "bible" / "parallel_corpus_v1.jsonl"
        )
        self.alignments_path = (
            self.data_dir / "bible" / "word_alignments_v1.jsonl"
        )
        self.grammar_output = (
            self.data_dir / "bible" / "grammar_patterns_v2.jsonl"
        )
        self.ref_dir = self.data_dir / "reference" / "grammar"
        self.learning_dir = (
            self.data_dir / "bible" / "language_learning"
        )

    # ── Grammar pattern extraction from corpus ───────────────────────────

    def _find_pattern(
        self, zo_tokens: list[str], en_text: str, ref: str
    ) -> list[dict]:
        """Find grammar patterns in a single verse."""
        patterns: list[dict] = []
        zo_set = set(zo_tokens)

        # SOV pattern
        if "in" in zo_set and "hi" in zo_set:
            in_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "in"), -1
            )
            hi_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "hi"), -1
            )
            if in_pos >= 0 and hi_pos > in_pos:
                subject = (
                    " ".join(zo_tokens[:in_pos]) if in_pos > 0
                    else "(implicit)"
                )
                patterns.append({
                    "pattern": "SOV",
                    "meaning": "Subject + in + Verb/Complement + hi",
                    "structure": "Subject + in + ... + hi",
                    "function": "ergative SOV declarative",
                    "frequency": 1,
                    "confidence": 0.85,
                    "notes": f"Subject='{subject}'",
                    "ref": ref,
                })

        # Tense markers
        for marker, info in self.TENSE_MARKERS.items():
            if marker in zo_set:
                idx = next(
                    (i for i, t in enumerate(zo_tokens) if t == marker), -1
                )
                if idx > 0:
                    verb = zo_tokens[idx - 1]
                    patterns.append({
                        "pattern": f"tense_{marker}",
                        "meaning": info["meaning"],
                        "structure": f"{verb} + {marker}",
                        "function": info["function"],
                        "frequency": 1,
                        "confidence": 0.8,
                        "notes": f"verb='{verb}'",
                        "ref": ref,
                    })

        # Negation patterns
        if "kei" in zo_set and "lo" in zo_set:
            kei_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "kei"), -1
            )
            lo_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "lo"), -1
            )
            if kei_pos >= 0 and lo_pos > kei_pos:
                verb_between = zo_tokens[kei_pos + 1 : lo_pos]
                patterns.append({
                    "pattern": "negation_kei_lo",
                    "meaning": "strong negation",
                    "structure": f"kei + {' '.join(verb_between)} + lo",
                    "function": "strong negation with resultative",
                    "frequency": 1,
                    "confidence": 0.9,
                    "notes": (
                        f"verb='{verb_between[0] if verb_between else '?'}'"
                    ),
                    "ref": ref,
                })
        elif "kei" in zo_set:
            kei_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "kei"), -1
            )
            if kei_pos >= 0 and kei_pos + 1 < len(zo_tokens):
                verb = zo_tokens[kei_pos + 1]
                patterns.append({
                    "pattern": "negation_kei",
                    "meaning": "negative",
                    "structure": f"kei + {verb}",
                    "function": "general negation",
                    "frequency": 1,
                    "confidence": 0.8,
                    "notes": f"verb='{verb}'",
                    "ref": ref,
                })
        elif "lo" in zo_set and "kei" not in zo_set:
            lo_pos = next(
                (i for i, t in enumerate(zo_tokens) if t == "lo"), -1
            )
            if lo_pos > 0:
                verb = zo_tokens[lo_pos - 1]
                patterns.append({
                    "pattern": "negation_lo",
                    "meaning": "negative/prohibitive",
                    "structure": f"{verb} + lo",
                    "function": "prohibitive/resultative negation",
                    "frequency": 1,
                    "confidence": 0.7,
                    "notes": f"verb='{verb}'",
                    "ref": ref,
                })

        # Aspect markers
        for marker, info in self.ASPECT_MARKERS.items():
            if marker in zo_set:
                idx = next(
                    (i for i, t in enumerate(zo_tokens) if t == marker), -1
                )
                if idx > 0:
                    verb = zo_tokens[idx - 1]
                    patterns.append({
                        "pattern": f"aspect_{marker}",
                        "meaning": info["meaning"],
                        "structure": f"{verb} + {marker}",
                        "function": info["function"],
                        "frequency": 1,
                        "confidence": 0.8,
                        "notes": f"verb='{verb}'",
                        "ref": ref,
                    })

        # Agreement markers
        for marker, info in self.AGREEMENT_MARKERS.items():
            if marker in zo_set:
                idx = next(
                    (i for i, t in enumerate(zo_tokens) if t == marker), -1
                )
                if idx >= 0:
                    patterns.append({
                        "pattern": f"agreement_{marker}",
                        "meaning": info["meaning"],
                        "structure": f"{marker} + Verb",
                        "function": info["function"],
                        "frequency": 1,
                        "confidence": 0.7,
                        "notes": f"marker='{marker}' pos={idx}",
                        "ref": ref,
                    })

        return patterns

    def _aggregate_patterns(
        self, all_patterns: list[dict]
    ) -> list[dict]:
        """Aggregate individual occurrences into summary patterns."""
        groups: dict[str, dict] = {}
        for p in all_patterns:
            key = f"{p['pattern']}|{p['structure']}|{p['function']}"
            if key not in groups:
                groups[key] = {
                    "id": f"pat_{len(groups) + 1:04d}",
                    "pattern": p["pattern"],
                    "meaning": p["meaning"],
                    "structure": p["structure"],
                    "function": p["function"],
                    "frequency": 0,
                    "confidence": p["confidence"],
                    "notes": p["notes"],
                    "refs": [],
                }
            groups[key]["frequency"] += 1
            if len(groups[key]["refs"]) < 5:
                groups[key]["refs"].append(p["ref"])

        result = sorted(
            groups.values(), key=lambda x: -x["frequency"]
        )
        for i, p in enumerate(result):
            p["id"] = f"pat_{i + 1:04d}"
            p["refs"] = "; ".join(p["refs"])
        return result

    def build_grammar_patterns(self) -> dict[str, int]:
        """Build grammar_patterns_v2.jsonl from corpus + alignments."""
        self.grammar_output.parent.mkdir(parents=True, exist_ok=True)

        if not self.corpus_path.exists():
            print(f"ERROR: Corpus not found: {self.corpus_path}",
                  file=sys.stderr)
            return {"error": 1}

        print("Loading corpus...")
        corpus: list[dict] = []
        with open(self.corpus_path, encoding="utf-8") as f:
            for line in f:
                corpus.append(json.loads(line))
        print(f"  Verses: {len(corpus):,}")

        print("Extracting grammar patterns...")
        all_patterns: list[dict] = []
        verses_with_patterns = 0

        for v in corpus:
            zo_text = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            en_text = v.get("en_kJV") or ""
            if not zo_text or not en_text:
                continue
            zo_tokens = _tokenize(zo_text)
            patterns = self._find_pattern(zo_tokens, en_text, v["ref"])
            if patterns:
                verses_with_patterns += 1
                all_patterns.extend(patterns)

        print(f"  Raw pattern hits: {len(all_patterns):,}")
        print(f"  Verses with patterns: {verses_with_patterns:,}")

        aggregated = self._aggregate_patterns(all_patterns)
        print(f"  Unique patterns: {len(aggregated):,}")

        with open(self.grammar_output, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in aggregated)

        counts = Counter(p["pattern"] for p in aggregated)
        print(f"\n✅ Grammar patterns built: {self.grammar_output.name}")
        print(f"   Total unique patterns: {len(aggregated):,}")
        print(f"   Pattern types: {dict(counts.most_common())}")
        return {
            "unique_patterns": len(aggregated),
            "verses_with_patterns": verses_with_patterns,
        }

    # ── Reference text extractors ────────────────────────────────────────

    @staticmethod
    def _strip_page_markers(text: str) -> str:
        """Remove page markers and Hebrew chars."""
        text = re.sub(r"Page \d+ of \d+", "", text)
        text = re.sub(r"[\u0590-\u05FF]+", "", text)
        return text.strip()

    def extract_from_vol1(self) -> dict[str, int]:
        """Parse Zolai_Grammar_Vol1.md into structured JSON."""
        input_file = self.ref_dir / "Zolai_Grammar_Vol1.md"
        output_file = self.learning_dir / "grammar_comprehensive.json"

        if not input_file.exists():
            print(f"  ⚠ {input_file.name} not found, skipping")
            return {"skipped": 1}

        text = input_file.read_text(encoding="utf-8")
        text = self._strip_page_markers(text)

        # Extract sections
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_content: list[str] = []
        for line in text.split("\n"):
            heading_match = re.match(r"^#{1,3}\s+(.+)", line)
            if heading_match:
                if current_section:
                    sections[current_section] = "\n".join(
                        current_content
                    ).strip()
                current_section = heading_match.group(1).strip()
                current_content = []
            else:
                current_content.append(line)
        if current_section:
            sections[current_section] = "\n".join(
                current_content
            ).strip()

        grammar = {
            "metadata": {
                "source": "Zolai_Grammar_Vol1.md",
                "total_chars": len(text),
                "sections_found": list(sections.keys()),
            },
            "phonology": {
                "vowels": {
                    "basic": ["a", "e", "i", "o", "u"],
                    "diphthongs": ["aw", "ei", "ou"],
                },
                "consonants": {
                    "stops": ["p", "b", "t", "d", "k", "g"],
                    "fricatives": ["f", "v", "s", "z", "h"],
                    "nasals": ["m", "n", "ng"],
                    "liquids": ["l", "r"],
                    "glides": ["w", "y"],
                },
            },
            "sections": {
                name: {"content": content[:5000], "length": len(content)}
                for name, content in sections.items()
            },
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(grammar, f, indent=2, ensure_ascii=False)

        print(f"  ✅ grammar_comprehensive.json saved "
              f"({output_file.stat().st_size // 1024}KB)")
        return {"sections": len(sections)}

    def extract_zvs_rules(self) -> dict[str, int]:
        """Parse ZVS_PDF.md into structured rules JSON."""
        input_file = self.ref_dir / "ZVS_PDF.md"
        output_file = self.learning_dir / "zvs_rules.json"

        if not input_file.exists():
            print(f"  ⚠ {input_file.name} not found, skipping")
            return {"skipped": 1}

        text = input_file.read_text(encoding="utf-8")

        zvs_rules = {
            "metadata": {
                "source": "ZVS_PDF.md",
                "standard": "ZVS 2018",
                "total_chars": len(text),
            },
            "vowel_chart": {
                "monophthongs": ["a", "e", "i", "o", "u"],
                "diphthongs": ["aw", "ei", "ou"],
            },
            "forbidden_forms": {
                "description": "Deprecated forms per ZVS 2018",
                "replacements": [
                    {"deprecated": "pathian", "standard": "pasian"},
                    {"deprecated": "ram", "standard": "gam"},
                    {"deprecated": "fapa", "standard": "tapa"},
                    {"deprecated": "bawipa", "standard": "topa"},
                    {"deprecated": "siangpahrang", "standard": "kumpipa"},
                    {"deprecated": "cu/cun", "standard": "tua"},
                    {"deprecated": "suah", "standard": "chuak"},
                    {"deprecated": "zalenna", "standard": "suahtakna"},
                    {"deprecated": "nunnak", "standard": "nuntakna"},
                ],
            },
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(zvs_rules, f, indent=2, ensure_ascii=False)

        print(f"  ✅ zvs_rules.json saved "
              f"({output_file.stat().st_size // 1024}KB)")
        return {"forbidden_forms": 9}

    def extract_sinna_lessons(self) -> dict[str, int]:
        """Parse Zolai_Sinna.md into structured lesson JSON."""
        input_file = self.ref_dir / "Zolai_Sinna.md"
        output_file = self.learning_dir / "sinna_lessons.json"

        if not input_file.exists():
            print(f"  ⚠ {input_file.name} not found, skipping")
            return {"skipped": 1}

        text = input_file.read_text(encoding="utf-8")

        lessons: list[dict] = []
        lesson_pattern = (
            r"(?:Sinna|SINNA)\s+(\d+)[:\s]*"
            r"(.*?)(?=(?:Sinna|SINNA)\s+\d+|$)"
        )
        for match in re.finditer(
            lesson_pattern, text, re.DOTALL | re.IGNORECASE
        ):
            lesson_num = int(match.group(1))
            content = match.group(2).strip()

            lesson: dict = {
                "lesson_number": lesson_num,
                "title": f"Sinna {lesson_num}",
                "vocab": [],
                "sentences": [],
                "grammar_point": "",
            }

            vocab_pattern = r"(\w+)\s*[-\u2013\u2014]\s*([A-Za-z][\w\s]*?)(?:\n|$)"
            for zo, en in re.findall(vocab_pattern, content):
                if len(zo) < 20 and len(en) < 50:
                    lesson["vocab"].append({
                        "zo": zo.strip(), "en": en.strip(),
                    })

            for line in content.split("\n"):
                line = line.strip()
                if (
                    len(line) > 20
                    and "\u2013" not in line
                    and not line.startswith("#")
                ):
                    lesson["sentences"].append(line)

            keywords = [
                "grammar", "tense", "pattern", "rule",
                "note", "remember",
            ]
            for line in content.split("\n"):
                if any(kw in line.lower() for kw in keywords):
                    lesson["grammar_point"] = line.strip()
                    break

            lessons.append(lesson)

        output = {
            "metadata": {
                "source": "Zolai_Sinna.md",
                "total_lessons": len(lessons),
            },
            "lessons": lessons,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"  ✅ sinna_lessons.json saved "
              f"({output_file.stat().st_size // 1024}KB)")
        return {"lessons": len(lessons)}

    def build_grammar_reference_v2(self) -> dict[str, int]:
        """Merge all grammar sources into grammar_reference_v2.json."""
        output_file = self.learning_dir / "grammar_reference_v2.json"
        existing_path = self.learning_dir / "grammar_reference.json"
        vol1_path = self.ref_dir / "Zolai_Grammar_Vol1.md"
        zvs_path = self.ref_dir / "ZVS_PDF.md"

        existing: dict = {}
        if existing_path.exists():
            with open(existing_path, encoding="utf-8") as f:
                existing = json.load(f)

        grammar_v2: dict = {
            "metadata": {
                "version": "2.0",
                "sources": ["existing", "grammar_vol1", "zvs"],
                "total_patterns": 0,
            },
            "phonology": {
                "vowels": {
                    "basic": ["a", "e", "i", "o", "u"],
                    "diphthongs": ["aw", "ei", "ou"],
                },
                "consonants": {
                    "stops": ["p", "b", "t", "d", "k", "g"],
                    "fricatives": ["f", "v", "s", "z", "h"],
                    "nasals": ["m", "n", "ng"],
                    "liquids": ["l", "r"],
                    "glides": ["w", "y"],
                },
            },
            "syntax": {
                "word_order": "SOV (Subject-Object-Verb)",
                "subordination": "marked by ergative 'in'",
                "quotation": "quotative verb 'ci'",
            },
            "negation_patterns": {
                "kei": "general negation (ALL persons)",
                "lo": "literary/formal negation (no 'a' agreement)",
                "kei_lo": "strong negation",
            },
            "question_formation": {
                "hiam": "yes/no question marker",
                "bang_hang": "content question (why/how)",
            },
            "forbidden_forms": {
                "pathian": "pasian", "ram": "gam",
                "fapa": "tapa", "bawipa": "topa",
                "siangpahrang": "kumpipa", "cu/cun": "tua",
                "suah": "chuak", "zalenna": "suahtakna",
                "nunnak": "nuntakna",
            },
        }

        if existing:
            grammar_v2["existing"] = existing

        pattern_count = sum(
            1 for v in grammar_v2.values() if isinstance(v, dict)
        )
        grammar_v2["metadata"]["total_patterns"] = pattern_count

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(grammar_v2, f, indent=2, ensure_ascii=False)

        print(f"  ✅ grammar_reference_v2.json saved "
              f"({output_file.stat().st_size // 1024}KB)")
        return {"sections": pattern_count}

    def build_all(self) -> dict[str, int]:
        """Run all grammar builders."""
        stats: dict[str, int] = {}
        try:
            stats.update(self.build_grammar_patterns())
        except Exception as exc:
            print(f"  ⚠ Grammar patterns skipped: {exc}")
        stats.update(self.extract_from_vol1())
        stats.update(self.extract_zvs_rules())
        stats.update(self.extract_sinna_lessons())
        stats.update(self.build_grammar_reference_v2())
        return stats


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Consolidated Bible Knowledge Builder"
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="Build parallel corpus",
    )
    parser.add_argument(
        "--vocabulary", action="store_true",
        help="Build vocabulary database",
    )
    parser.add_argument(
        "--grammar", action="store_true",
        help="Build grammar patterns",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Build everything",
    )
    args = parser.parse_args()

    if not any([args.parallel, args.vocabulary, args.grammar, args.all]):
        parser.print_help()
        return 1

    if args.all or args.parallel:
        print("\n═══ PARALLEL BUILDER ═══")
        pb = ParallelBuilder()
        pb.build_all()

    if args.all or args.vocabulary:
        print("\n═══ VOCABULARY BUILDER ═══")
        vb = VocabularyBuilder()
        vb.build_all()

    if args.all or args.grammar:
        print("\n═══ GRAMMAR BUILDER ═══")
        gb = GrammarBuilder()
        gb.build_all()

    print("\n✅ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
