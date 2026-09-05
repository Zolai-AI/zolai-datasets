#!/usr/bin/env python3
"""
Bible Linguistic Pipeline — transforms 31,102 parallel English-Zo Bible verses into structured,
RAG-ready linguistic knowledge. 8 pipeline steps with evidence envelopes.
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Any

# ─── PATHS ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent.parent  # zolai-ai root
DATA = WORKSPACE / "data"
BIBLE_DIR = DATA / "bible"
PIPELINE_DIR = BIBLE_DIR / "pipeline"

# Input files
INPUT_FILES = {
    "parallel_corpus": BIBLE_DIR / "parallel_corpus_v1.jsonl",
    "word_alignments": BIBLE_DIR / "word_alignments_v1.jsonl",
    "vocab_index": BIBLE_DIR / "vocab_index_full.jsonl",
    "grammar_patterns": BIBLE_DIR / "grammar_patterns_text.jsonl",
    "word_collocations": BIBLE_DIR / "word_collocations.jsonl",
    "phrases": BIBLE_DIR / "phrases_v1.jsonl",
    "translation_pairs": BIBLE_DIR / "translation_pairs_v1.jsonl",
    "verb_database": BIBLE_DIR / "verb_database_v1.jsonl",
    "particle_database": BIBLE_DIR / "particle_database_v1.jsonl",
    "dict_zo_en": DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl",
    "dict_supplement": DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl",
}

# Output directories
OUTPUT_DIRS = {
    "raw": PIPELINE_DIR / "raw",
    "aligned": PIPELINE_DIR / "aligned",
    "linguistic": PIPELINE_DIR / "linguistic",
    "learning": PIPELINE_DIR / "learning",
    "metadata": PIPELINE_DIR / "metadata",
}

# Evidence types
EVIDENCE_TYPES = {
    "BIBLE_EVIDENCE",
    "CORPUS_PATTERN",
    "GENERATED",
    "EXTERNAL_EVIDENCE",
}

# Evidence levels
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
UNCERTAIN = "UNCERTAIN"

# Pipeline version
PIPELINE_VERSION = "1.0.0"

# ─── HELPERS ───────────────────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create all output directories."""
    for d in OUTPUT_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    """Return ISO timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat()


def make_provenance(source_files: list[str]) -> dict[str, Any]:
    """Create a provenance envelope."""
    return {
        "source_files": source_files,
        "pipeline_version": PIPELINE_VERSION,
        "built_at": timestamp(),
    }


def make_evidence(
    examples_count: int = 0,
    references: list[str] | None = None,
    confidence: str = UNCERTAIN,
    evidence_type: str = "BIBLE_EVIDENCE",
) -> dict[str, Any]:
    """Create an evidence envelope."""
    return {
        "examples_count": examples_count,
        "references": references or [],
        "confidence": confidence,
        "evidence_type": evidence_type,
    }


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    items: list[dict] = []
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return items


def write_jsonl(path: Path, items: list[dict]) -> int:
    """Write a list of dicts to a JSONL file. Returns count."""
    with open(path, "w") as f:
        f.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    return len(items)


def write_json(path: Path, data: Any) -> None:
    """Write a dict/list to a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def file_exists_and_nonempty(path: Path) -> bool:
    """Check if a file exists and has non-zero size."""
    return path.exists() and path.stat().st_size > 0


# ─── EVIDENCE SCORER (copy from bible_engine.py for portability) ──────────

class EvidenceScorer:
    """Score the strength of linguistic evidence."""

    @staticmethod
    def score_dict_hit(freq: int) -> str:
        if freq > 1000:
            return HIGH
        if freq > 100:
            return MEDIUM
        if freq > 10:
            return LOW
        return UNCERTAIN

    @staticmethod
    def score_pattern(freq: int, example_count: int) -> str:
        if freq > 500 and example_count >= 5:
            return HIGH
        if freq > 100 and example_count >= 3:
            return MEDIUM
        if freq > 10:
            return LOW
        return UNCERTAIN

    @staticmethod
    def score_corpus_match(match_count: int, total: int) -> str:
        if total == 0:
            return UNCERTAIN
        ratio = match_count / total
        if ratio > 0.8:
            return HIGH
        if ratio > 0.5:
            return MEDIUM
        if ratio > 0.2:
            return LOW
        return UNCERTAIN


# ─── STEP 1: RAW ──────────────────────────────────────────────────────────

def step_raw(force: bool = False) -> bool:
    """Step 1: Copy parallel corpus to pipeline/raw/."""
    out_dir = OUTPUT_DIRS["raw"]
    out_file = out_dir / "parallel_corpus.jsonl"
    if file_exists_and_nonempty(out_file) and not force:
        print(f"  [skip] {out_file} exists (use --force to rebuild)")
        return True

    src = INPUT_FILES["parallel_corpus"]
    if not src.exists():
        print(f"  [error] Source not found: {src}")
        return False

    print(f"  Copying {src.name} → {out_file}")
    import shutil
    shutil.copy2(src, out_file)
    print(f"  ✓ {out_file.stat().st_size:,} bytes")
    return True


# ─── STEP 2: SENTENCE ALIGNMENT ──────────────────────────────────────────

def step_sentence_alignment(force: bool = False) -> bool:
    """Step 2: Verse→sentence split with sentence_id, alignment_confidence."""
    out_dir = OUTPUT_DIRS["aligned"]
    out_file = out_dir / "verse_alignment.jsonl"
    if file_exists_and_nonempty(out_file) and not force:
        print(f"  [skip] {out_file} exists (use --force to rebuild)")
        return True

    corpus = load_jsonl(INPUT_FILES["parallel_corpus"])
    if not corpus:
        print(f"  [error] No corpus loaded from {INPUT_FILES['parallel_corpus']}")
        return False

    # Load word alignments for confidence scoring (streaming for large file)
    print("  Loading word alignments...")
    verse_alignments: dict[str, list[dict]] = {}
    with open(INPUT_FILES["word_alignments"]) as f:
        for line in f:
            a = json.loads(line)
            vid = a.get("ref", "")  # actual field is 'ref'
            if vid not in verse_alignments:
                verse_alignments[vid] = []
            verse_alignments[vid].append(a)
    print(f"  Loaded {sum(len(v) for v in verse_alignments.values()):,} alignments for {len(verse_alignments):,} verses")

    results: list[dict] = []
    for verse in corpus:
        vid = verse.get("ref", "")  # actual field is 'ref'
        book = verse.get("book", "")
        chapter = str(verse.get("chapter", ""))
        verse_num = str(verse.get("verse", ""))
        zo = verse.get("zo_tedim2010", "") or verse.get("zo_tdb77", "")
        en = verse.get("en_kJV", "")
        source = "tedim2010"

        # Count aligned words for confidence
        va = verse_alignments.get(vid, [])
        aligned_count = sum(1 for a in va if a.get("zo") and a.get("en"))
        total_zo_words = len(zo.split()) if zo else 1
        confidence_ratio = aligned_count / total_zo_words if total_zo_words else 0

        if confidence_ratio > 0.8:
            confidence = HIGH
        elif confidence_ratio > 0.5:
            confidence = MEDIUM
        elif confidence_ratio > 0.2:
            confidence = LOW
        else:
            confidence = UNCERTAIN

        # Build sentence entries (one per verse; sentence split can be enhanced later)
        # Convert ref like "GEN 1:1" to "bible:GEN:1:1"
        safe_id = "bible:" + vid.replace(" ", ":") if vid else ""
        sentence_id = f"{safe_id}:s0"
        word_alignments = []
        for a in va:
            zo_w = a.get("zo_word", "")
            en_w = a.get("en_word", "")
            if zo_w and en_w:
                word_alignments.append({
                    "zo": zo_w,
                    "en": en_w,
                    "confidence": HIGH,
                })

        results.append({
            "id": safe_id,
            "book": book,
            "chapter": chapter,
            "verse": verse_num,
            "sentence_id": sentence_id,
            "zo": zo,
            "en": en,
            "source": source,
            "alignment_confidence": confidence,
            "word_alignments": word_alignments,
            "provenance": make_provenance(["parallel_corpus_v1.jsonl", "word_alignments_v1.jsonl"]),
        })

    count = write_jsonl(out_file, results)
    print(f"  ✓ {count:,} verses → {out_file}")
    return True


# ─── STEP 3: VOCABULARY ──────────────────────────────────────────────────

def step_vocabulary(force: bool = False) -> bool:
    """Step 3: Unified vocab with evidence scores, provenance, examples."""
    out_dir = OUTPUT_DIRS["linguistic"]
    out_file = out_dir / "vocabulary.jsonl"
    if file_exists_and_nonempty(out_file) and not force:
        print(f"  [skip] {out_file} exists (use --force to rebuild)")
        return True

    # Load vocab index
    vocab_raw = load_jsonl(INPUT_FILES["vocab_index"])
    if not vocab_raw:
        print(f"  [error] No vocab index from {INPUT_FILES['vocab_index']}")
        return False

    # Load dictionary for translations
    dict_zo: dict[str, list[str]] = {}
    for path in [INPUT_FILES["dict_supplement"], INPUT_FILES["dict_zo_en"]]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    hw = (rec.get("zolai") or rec.get("headword") or "").strip().lower()
                    if not hw:
                        continue
                    eng = rec.get("english") or rec.get("translations") or []
                    if isinstance(eng, str):
                        eng = [eng]
                    if hw not in dict_zo:
                        dict_zo[hw] = eng

    # Load corpus for example extraction (streaming)
    print("  Building word→verse index from corpus...")
    word_to_verses: dict[str, list[dict]] = defaultdict(list)
    with open(INPUT_FILES["parallel_corpus"]) as f:
        for line in f:
            verse = json.loads(line)
            vid = verse.get("ref", "")
            zo = verse.get("zo_tedim2010", "") or verse.get("zo_tdb77", "")
            en = verse.get("en_kJV", "") or ""
            if not zo:
                continue
            for word in zo.split():
                w = word.strip().lower()
                if len(w) > 1:
                    word_to_verses[w].append({
                        "ref": vid,
                        "zo": (zo or "")[:100] + ("..." if len(zo or "") > 100 else ""),
                        "en": (en or "")[:100] + ("..." if len(en or "") > 100 else ""),
                    })
    print(f"  Indexed {len(word_to_verses):,} unique words")

    results: list[dict] = []
    for entry in vocab_raw:
        word = entry.get("word", "")
        freq = entry.get("frequency", 0)
        translations = entry.get("translations", [])
        book_count = entry.get("book_count", 0)

        # Get translations from dictionary if not in vocab
        if not translations:
            translations = dict_zo.get(word.lower(), [])

        # Get examples from corpus
        examples = word_to_verses.get(word.lower(), [])[:5]  # top 5

        # Evidence scoring
        confidence = EvidenceScorer.score_dict_hit(freq)
        evidence_count = len(examples)

        results.append({
            "id": f"zo:vocab:{word}",
            "word": word,
            "translations": translations[:5],
            "pos": entry.get("pos", ""),
            "frequency": freq,
            "book_count": book_count,
            "examples": examples,
            "morphology": {
                "root": word,
                "prefix": None,
                "suffix": None,
            },
            "collocations": [],
            "grammar_roles": [],
            "evidence": make_evidence(
                examples_count=evidence_count,
                references=[ex["ref"] for ex in examples[:5]],
                confidence=confidence,
                evidence_type="BIBLE_EVIDENCE",
            ),
            "provenance": make_provenance(["vocab_index_full.jsonl", "dict_zo_en_master_v1.jsonl"]),
        })

    count = write_jsonl(out_file, results)
    print(f"  ✓ {count:,} vocab entries → {out_file}")
    return True


# ─── STEP 4: PHRASES ─────────────────────────────────────────────────────

def step_phrases(force: bool = False) -> bool:
    """Step 4: Multi-word expressions + collocations + idioms."""
    out_dir = OUTPUT_DIRS["linguistic"]
    out_file = out_dir / "phrases.jsonl"
    if file_exists_and_nonempty(out_file) and not force:
        print(f"  [skip] {out_file} exists (use --force to rebuild)")
        return True

    # Load phrases
    phrases_raw = load_jsonl(INPUT_FILES["phrases"])
    if not phrases_raw:
        print(f"  [error] No phrases from {INPUT_FILES['phrases']}")
        return False

    # Load collocations
    collocations_raw = load_jsonl(INPUT_FILES["word_collocations"])
    coll_map: dict[str, int] = {}
    for c in collocations_raw:
        key = c.get("pair") or f"{c.get('word1', '')} {c.get('word2', '')}"
        coll_map[key] = c.get("frequency", 0)

    # Load supplement dict for phrase translations
    phrase_dict: dict[str, str] = {}
    if INPUT_FILES["dict_supplement"].exists():
        with open(INPUT_FILES["dict_supplement"]) as f:
            for line in f:
                rec = json.loads(line)
                hw = (rec.get("zolai") or rec.get("headword") or "").strip().lower()
                eng = rec.get("english") or rec.get("translations") or []
                if isinstance(eng, str):
                    eng = [eng]
                if hw and eng:
                    phrase_dict[hw] = eng[0]

    results: list[dict] = []
    for phrase in phrases_raw:
        phrase_text = phrase.get("phrase") or phrase.get("text", "")
        freq = phrase.get("frequency", 0)
        translations = phrase.get("translations", [])
        phrase_type = phrase.get("type", "multi_word")

        # Get translation from dict supplement
        if not translations:
            trans = phrase_dict.get(phrase_text.lower(), "")
            if trans:
                translations = [trans]

        # Check if it's a collocation
        is_collocation = phrase_text.lower() in coll_map
        coll_freq = coll_map.get(phrase_text.lower(), 0)

        # Evidence scoring
        confidence = EvidenceScorer.score_dict_hit(freq + coll_freq)

        results.append({
            "id": f"zo:phrase:{phrase_text.replace(' ', '_')}",
            "phrase": phrase_text,
            "translations": translations[:3],
            "type": phrase_type,
            "frequency": freq + coll_freq,
            "is_collocation": is_collocation,
            "evidence": make_evidence(
                examples_count=1,  # placeholder
                references=[],
                confidence=confidence,
                evidence_type="CORPUS_PATTERN" if is_collocation else "BIBLE_EVIDENCE",
            ),
            "provenance": make_provenance(["phrases_v1.jsonl", "word_collocations.jsonl"]),
        })

    count = write_jsonl(out_file, results)
    print(f"  ✓ {count:,} phrases → {out_file}")
    return True


# ─── STEP 5: GRAMMAR ─────────────────────────────────────────────────────

def step_grammar(force: bool = False) -> bool:
    """Step 5: Patterns, morphology, verbs, particles — all with evidence."""
    out_dir = OUTPUT_DIRS["linguistic"]

    # 5a. Grammar patterns
    patterns_file = out_dir / "grammar_patterns.jsonl"
    if not file_exists_and_nonempty(patterns_file) or force:
        patterns_raw = load_jsonl(INPUT_FILES["grammar_patterns"])
        results: list[dict] = []
        for p in patterns_raw:
            pattern_name = p.get("pattern") or p.get("name", "")
            freq = p.get("frequency", 0)
            examples = p.get("examples", [])
            confidence = EvidenceScorer.score_pattern(freq, len(examples))
            results.append({
                "id": f"zo:pattern:{pattern_name.replace(' ', '_')}",
                "pattern": pattern_name,
                "description": p.get("description", ""),
                "frequency": freq,
                "examples": examples[:5],
                "evidence": make_evidence(
                    examples_count=len(examples),
                    references=[ex if isinstance(ex, str) else ex.get("ref", "") for ex in examples[:5]],
                    confidence=confidence,
                    evidence_type="CORPUS_PATTERN",
                ),
                "provenance": make_provenance(["grammar_patterns_text.jsonl"]),
            })
        count = write_jsonl(patterns_file, results)
        print(f"  ✓ {count:,} grammar patterns → {patterns_file}")
    else:
        print(f"  [skip] {patterns_file} exists (use --force to rebuild)")

    # 5b. Verbs
    verbs_file = out_dir / "verbs.jsonl"
    if not file_exists_and_nonempty(verbs_file) or force:
        verbs_raw = load_jsonl(INPUT_FILES["verb_database"])
        results = []
        for v in verbs_raw:
            verb = v.get("verb") or v.get("word", "")
            freq = v.get("frequency", 0)
            translations = v.get("translations", [])
            confidence = EvidenceScorer.score_dict_hit(freq)
            results.append({
                "id": f"zo:verb:{verb}",
                "verb": verb,
                "translations": translations[:3],
                "frequency": freq,
                "conjugations": v.get("conjugations", {}),
                "evidence": make_evidence(
                    examples_count=v.get("example_count", 0),
                    references=v.get("references", []),
                    confidence=confidence,
                    evidence_type="BIBLE_EVIDENCE",
                ),
                "provenance": make_provenance(["verb_database_v1.jsonl"]),
            })
        count = write_jsonl(verbs_file, results)
        print(f"  ✓ {count:,} verbs → {verbs_file}")
    else:
        print(f"  [skip] {verbs_file} exists (use --force to rebuild)")

    # 5c. Particles
    particles_file = out_dir / "particles.jsonl"
    if not file_exists_and_nonempty(particles_file) or force:
        particles_raw = load_jsonl(INPUT_FILES["particle_database"])
        results = []
        for p in particles_raw:
            particle = p.get("particle") or p.get("word", "")
            freq = p.get("frequency", 0)
            translations = p.get("translations", [])
            confidence = EvidenceScorer.score_dict_hit(freq)
            results.append({
                "id": f"zo:particle:{particle}",
                "particle": particle,
                "translations": translations[:3],
                "frequency": freq,
                "function": p.get("function", ""),
                "evidence": make_evidence(
                    examples_count=p.get("example_count", 0),
                    references=p.get("references", []),
                    confidence=confidence,
                    evidence_type="BIBLE_EVIDENCE",
                ),
                "provenance": make_provenance(["particle_database_v1.jsonl"]),
            })
        count = write_jsonl(particles_file, results)
        print(f"  ✓ {count:,} particles → {particles_file}")
    else:
        print(f"  [skip] {particles_file} exists (use --force to rebuild)")

    return True


# ─── STEP 6: EVIDENCE GRAPH ──────────────────────────────────────────────

def step_evidence_graph(force: bool = False) -> bool:
    """Step 6: Cross-references: word→phrase→sentence→pattern→examples."""
    out_dir = OUTPUT_DIRS["linguistic"]
    out_file = out_dir / "evidence_graph.jsonl"
    if file_exists_and_nonempty(out_file) and not force:
        print(f"  [skip] {out_file} exists (use --force to rebuild)")
        return True

    # Load vocabulary, phrases, patterns, aligned verses
    vocab = load_jsonl(out_dir / "vocabulary.jsonl") if (out_dir / "vocabulary.jsonl").exists() else []
    phrases = load_jsonl(out_dir / "phrases.jsonl") if (out_dir / "phrases.jsonl").exists() else []
    patterns = load_jsonl(out_dir / "grammar_patterns.jsonl") if (out_dir / "grammar_patterns.jsonl").exists() else []
    aligned = load_jsonl(OUTPUT_DIRS["aligned"] / "verse_alignment.jsonl") if (OUTPUT_DIRS["aligned"] / "verse_alignment.jsonl").exists() else []

    # Build word→verses mapping
    word_to_verses: dict[str, list[str]] = defaultdict(list)
    for verse in aligned:
        for w in verse.get("word_alignments", []):
            zo_w = (w.get("zo") or "").lower()
            if zo_w:
                word_to_verses[zo_w].append(verse.get("id", ""))

    # Build phrase→verses mapping
    phrase_to_verses: dict[str, list[str]] = defaultdict(list)
    for verse in aligned:
        zo = (verse.get("zo") or "").lower()
        for phrase in phrases:
            pt = (phrase.get("phrase") or "").lower()
            if pt and pt in zo:
                phrase_to_verses[phrase.get("id", "")].append(verse.get("id", ""))

    results: list[dict] = []

    # Word nodes
    for v in vocab:
        word = v.get("word", "")
        connections = []
        # Connect to verses
        for vid in word_to_verses.get(word.lower(), [])[:10]:
            connections.append({
                "type": "sentence",
                "id": vid,
                "relation": "appears_in",
            })
        # Connect to translations
        for trans in v.get("translations", [])[:3]:
            connections.append({
                "type": "translation",
                "en": trans,
                "relation": "translates_to",
            })
        # Connect to patterns (placeholder)
        results.append({
            "id": f"zo:graph:{word}",
            "node_type": "word",
            "word": word,
            "connected_to": connections,
            "evidence": make_evidence(
                examples_count=len(connections),
                references=[],
                confidence=(v.get("evidence") or {}).get("confidence", UNCERTAIN),
                evidence_type="BIBLE_EVIDENCE",
            ),
            "provenance": make_provenance(["vocabulary.jsonl", "verse_alignment.jsonl"]),
        })

    # Phrase nodes
    for ph in phrases:
        pid = ph.get("id", "")
        connections = []
        for vid in phrase_to_verses.get(pid, [])[:10]:
            connections.append({
                "type": "sentence",
                "id": vid,
                "relation": "appears_in",
            })
        results.append({
            "id": f"zo:graph:phrase:{pid.split(':')[-1]}",
            "node_type": "phrase",
            "phrase": ph.get("phrase", ""),
            "connected_to": connections,
            "evidence": make_evidence(
                examples_count=len(connections),
                references=[],
                confidence=(ph.get("evidence") or {}).get("confidence", UNCERTAIN),
                evidence_type="CORPUS_PATTERN",
            ),
            "provenance": make_provenance(["phrases.jsonl", "verse_alignment.jsonl"]),
        })

    count = write_jsonl(out_file, results)
    print(f"  ✓ {count:,} evidence graph nodes → {out_file}")
    return True


# ─── STEP 7: LEARNING ────────────────────────────────────────────────────

def step_learning(force: bool = False) -> bool:
    """Step 7: Lessons, exercises, translation pairs, evaluation sets."""
    out_dir = OUTPUT_DIRS["learning"]

    # 7a. Lessons (progressive levels)
    lessons_file = out_dir / "lessons.jsonl"
    if not file_exists_and_nonempty(lessons_file) or force:
        vocab = load_jsonl(OUTPUT_DIRS["linguistic"] / "vocabulary.jsonl") if (OUTPUT_DIRS["linguistic"] / "vocabulary.jsonl").exists() else []
        # Sort by frequency
        vocab_sorted = sorted(vocab, key=lambda x: x.get("frequency", 0), reverse=True)

        level_thresholds = {1: 100, 2: 200, 3: 500, 4: 1000, 5: 2000, 6: 3500, 7: 5000, 8: 999999}
        level_titles = {
            1: "Common Nouns — Top 100 Words",
            2: "Basic Phrases — 200 Words",
            3: "Sentence Patterns — 500 Words",
            4: "Grammar Structures — 1000 Words",
            5: "Complex Sentences — 2000 Words",
            6: "Idiomatic Usage — 3500 Words",
            7: "Literary Analysis — 5000 Words",
            8: "Full Bible Vocabulary — All Words",
        }

        lessons: list[dict] = []
        for level, threshold in level_thresholds.items():
            level_words = [v for v in vocab_sorted if v.get("frequency", 0) > 0][:threshold]
            word_list = [w.get("word", "") for w in level_words[:100]]  # top 100 per level

            # Find grammar focus based on POS distribution
            pos_counter = Counter(w.get("pos", "") for w in level_words)
            grammar_focus = ""
            if pos_counter:
                top_pos = pos_counter.most_common(1)[0][0]
                grammar_focus = f"{top_pos} usage patterns"

            lessons.append({
                "id": f"lesson:L{level}:{level_titles[level].split('—')[0].strip().lower().replace(' ', '_')}",
                "level": level,
                "title": level_titles[level],
                "words": word_list,
                "word_count": len(level_words),
                "grammar_focus": grammar_focus,
                "exercises": [],
                "translation_pairs": [],
                "evidence": make_evidence(
                    examples_count=len(level_words),
                    references=[],
                    confidence=HIGH if level <= 3 else MEDIUM,
                    evidence_type="GENERATED",
                ),
                "provenance": make_provenance(["vocabulary.jsonl"]),
            })

        count = write_jsonl(lessons_file, lessons)
        print(f"  ✓ {count} lessons → {lessons_file}")
    else:
        print(f"  [skip] {lessons_file} exists (use --force to rebuild)")

    # 7b. Translation pairs (from input)
    pairs_file = out_dir / "translation_pairs.jsonl"
    if not file_exists_and_nonempty(pairs_file) or force:
        pairs_raw = load_jsonl(INPUT_FILES["translation_pairs"])
        results = []
        for p in pairs_raw[:50000]:  # limit to 50k for memory
            results.append({
                "id": f"zo:pair:{len(results)}",
                "zo": p.get("zo", ""),
                "en": p.get("en", ""),
                "source": p.get("source", "generated"),
                "evidence": make_evidence(
                    examples_count=1,
                    references=[],
                    confidence=MEDIUM,
                    evidence_type="GENERATED",
                ),
                "provenance": make_provenance(["translation_pairs_v1.jsonl"]),
            })
        count = write_jsonl(pairs_file, results)
        print(f"  ✓ {count:,} translation pairs → {pairs_file}")
    else:
        print(f"  [skip] {pairs_file} exists (use --force to rebuild)")

    return True


# ─── STEP 8: METADATA ────────────────────────────────────────────────────

def step_metadata(force: bool = False) -> bool:
    """Step 8: sources.json (provenance), quality.json (coverage stats)."""
    out_dir = OUTPUT_DIRS["metadata"]

    # sources.json
    sources_file = out_dir / "sources.json"
    if not file_exists_and_nonempty(sources_file) or force:
        sources = {}
        for name, path in INPUT_FILES.items():
            sources[name] = {
                "path": str(path.relative_to(WORKSPACE)) if path.exists() else str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if path.exists() else None,
            }
        write_json(sources_file, {
            "pipeline_version": PIPELINE_VERSION,
            "sources": sources,
            "generated_at": timestamp(),
        })
        print(f"  ✓ sources.json → {sources_file}")
    else:
        print(f"  [skip] {sources_file} exists (use --force to rebuild)")

    # quality.json
    quality_file = out_dir / "quality.json"
    if not file_exists_and_nonempty(quality_file) or force:
        # Count records in each output file
        vocab_file = OUTPUT_DIRS["linguistic"] / "vocabulary.jsonl"
        phrases_file = OUTPUT_DIRS["linguistic"] / "phrases.jsonl"
        patterns_file = OUTPUT_DIRS["linguistic"] / "grammar_patterns.jsonl"
        aligned_file = OUTPUT_DIRS["aligned"] / "verse_alignment.jsonl"
        evidence_file = OUTPUT_DIRS["linguistic"] / "evidence_graph.jsonl"

        total_verses = len(load_jsonl(aligned_file)) if aligned_file.exists() else 0
        total_vocab = len(load_jsonl(vocab_file)) if vocab_file.exists() else 0
        total_phrases = len(load_jsonl(phrases_file)) if phrases_file.exists() else 0
        total_patterns = len(load_jsonl(patterns_file)) if patterns_file.exists() else 0
        total_graph = len(load_jsonl(evidence_file)) if evidence_file.exists() else 0

        # Evidence distribution
        evidence_dist = Counter()
        if vocab_file.exists():
            for v in load_jsonl(vocab_file):
                ev = v.get("evidence", {}).get("evidence_type", "UNKNOWN")
                evidence_dist[ev] += 1

        # Book coverage
        book_counter: Counter = Counter()
        if aligned_file.exists():
            for a in load_jsonl(aligned_file):
                book_counter[a.get("book", "")] += 1

        quality = {
            "pipeline_version": PIPELINE_VERSION,
            "generated_at": timestamp(),
            "total_verses": total_verses,
            "total_unique_words": total_vocab,
            "total_phrases": total_phrases,
            "total_patterns": total_patterns,
            "evidence_graph_nodes": total_graph,
            "evidence_distribution": dict(evidence_dist),
            "book_coverage": dict(book_counter.most_common()),
        }
        write_json(quality_file, quality)
        print(f"  ✓ quality.json → {quality_file}")
    else:
        print(f"  [skip] {quality_file} exists (use --force to rebuild)")

    return True


# ─── STEP RUNNER ──────────────────────────────────────────────────────────

STEP_MAP = {
    "raw": step_raw,
    "sentence_alignment": step_sentence_alignment,
    "vocabulary": step_vocabulary,
    "phrases": step_phrases,
    "grammar": step_grammar,
    "evidence_graph": step_evidence_graph,
    "learning": step_learning,
    "metadata": step_metadata,
}

STEP_ORDER = [
    "raw",
    "sentence_alignment",
    "vocabulary",
    "phrases",
    "grammar",
    "evidence_graph",
    "learning",
    "metadata",
]


def run_step(step_name: str, force: bool = False) -> bool:
    """Run a single step."""
    if step_name not in STEP_MAP:
        print(f"  [error] Unknown step: {step_name}")
        return False
    print(f"\n{'='*60}")
    print(f"STEP: {step_name}")
    print(f"{'='*60}")
    return STEP_MAP[step_name](force=force)


def run_all(force: bool = False) -> bool:
    """Run all steps in order."""
    ensure_dirs()
    results = {}
    for step in STEP_ORDER:
        results[step] = run_step(step, force=force)
        if not results[step]:
            print(f"\n✗ Step {step} failed. Stopping.")
            return False

    print(f"\n{'='*60}")
    print("ALL STEPS COMPLETE")
    print(f"{'='*60}")
    for step, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {step}")
    return all(results.values())


def show_stats() -> None:
    """Show pipeline statistics."""
    ensure_dirs()
    print(f"\n{'='*60}")
    print("PIPELINE STATS")
    print(f"{'='*60}")

    for step in STEP_ORDER:
        print(f"\n--- {step} ---")
        if step == "raw":
            f = OUTPUT_DIRS["raw"] / "parallel_corpus.jsonl"
            if f.exists():
                count = sum(1 for _ in open(f))
                print(f"  records: {count:,}")
                print(f"  size: {f.stat().st_size:,} bytes")
            else:
                print("  (not built)")
        elif step == "sentence_alignment":
            f = OUTPUT_DIRS["aligned"] / "verse_alignment.jsonl"
            if f.exists():
                count = sum(1 for _ in open(f))
                print(f"  records: {count:,}")
            else:
                print("  (not built)")
        elif step == "vocabulary":
            f = OUTPUT_DIRS["linguistic"] / "vocabulary.jsonl"
            if f.exists():
                count = sum(1 for _ in open(f))
                print(f"  records: {count:,}")
            else:
                print("  (not built)")
        elif step == "phrases":
            f = OUTPUT_DIRS["linguistic"] / "phrases.jsonl"
            if f.exists():
                count = sum(1 for _ in open(f))
                print(f"  records: {count:,}")
            else:
                print("  (not built)")
        elif step == "grammar":
            for sub in ["grammar_patterns.jsonl", "verbs.jsonl", "particles.jsonl"]:
                f = OUTPUT_DIRS["linguistic"] / sub
                if f.exists():
                    count = sum(1 for _ in open(f))
                    print(f"  {sub}: {count:,}")
                else:
                    print(f"  {sub}: (not built)")
        elif step == "evidence_graph":
            f = OUTPUT_DIRS["linguistic"] / "evidence_graph.jsonl"
            if f.exists():
                count = sum(1 for _ in open(f))
                print(f"  records: {count:,}")
            else:
                print("  (not built)")
        elif step == "learning":
            for sub in ["lessons.jsonl", "translation_pairs.jsonl"]:
                f = OUTPUT_DIRS["learning"] / sub
                if f.exists():
                    count = sum(1 for _ in open(f))
                    print(f"  {sub}: {count:,}")
                else:
                    print(f"  {sub}: (not built)")
        elif step == "metadata":
            for sub in ["sources.json", "quality.json"]:
                f = OUTPUT_DIRS["metadata"] / sub
                if f.exists():
                    print(f"  {sub}: exists ({f.stat().st_size:,} bytes)")
                else:
                    print(f"  {sub}: (not built)")


# ─── CLI ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bible Linguistic Pipeline — 8-step structured knowledge builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_linguistic_pipeline.py --all          # Run all 8 steps
  python build_linguistic_pipeline.py --step vocabulary  # Run single step
  python build_linguistic_pipeline.py --force        # Rebuild even if exists
  python build_linguistic_pipeline.py --stats        # Show pipeline stats
        """,
    )
    parser.add_argument("--all", action="store_true", help="Run all 8 steps")
    parser.add_argument("--step", choices=STEP_ORDER, help="Run a single step")
    parser.add_argument("--force", action="store_true", help="Rebuild even if output exists")
    parser.add_argument("--stats", action="store_true", help="Show pipeline statistics")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if not args.all and not args.step:
        parser.print_help()
        return

    ensure_dirs()

    if args.all:
        success = run_all(force=args.force)
    else:
        success = run_step(args.step, force=args.force)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
