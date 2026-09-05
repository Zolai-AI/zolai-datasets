#!/usr/bin/env python3
"""
ZOLAI BIBLE STUDY — AI-Assisted Context-Aware Glossing v2.0
All 66 books • Full knowledge base • Version comparison
OpenCode Free Models • Dictionary-First • AI Disambiguation
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent.parent  # zolai-ai root
DATA = WORKSPACE / "data"
DICT_ZO_EN = DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
DICT_EN_ZO = DATA / "dictionary" / "processed" / "dict_canonical_v1.jsonl"
SUPPLEMENT_DICT = DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"
CORPUS = DATA / "bible" / "parallel_corpus_v1.jsonl"
STUDY_DIR = DATA / "dictionary" / "bible_study"
LOG_FILE = STUDY_DIR / "bible_study_log.jsonl"
AI_CACHE = STUDY_DIR / "ai_gloss_cache.jsonl"
KB_DIR = DATA / "bible"

# ══════════════════════════════════════════════════════════════════════
# COLORS
# ══════════════════════════════════════════════════════════════════════
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
B = "\033[0;34m"
C = "\033[0;36m"
M = "\033[0;35m"
NC = "\033[0m"

# ══════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════
def log_event(event: str, **kwargs):
    """Append structured log event."""
    entry = {"ts": datetime.now().isoformat(), "event": event, **kwargs}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ══════════════════════════════════════════════════════════════════════
# LOAD DICTIONARIES
# ══════════════════════════════════════════════════════════════════════
def load_zo_en_dict() -> dict:
    """Load Zolai→English master dictionary."""
    d = {}
    for path in [SUPPLEMENT_DICT, DICT_ZO_EN]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    # Support both formats
                    hw = rec.get("zolai") or rec.get("headword") or ""
                    hw = hw.strip().lower()
                    if not hw:
                        continue
                    eng = rec.get("english") or rec.get("translations") or []
                    if isinstance(eng, str):
                        eng = [eng]
                    if hw not in d:  # supplement wins (checked first)
                        d[hw] = eng
    return d

def load_en_zo_dict() -> dict:
    """Load English→Zolai dictionary."""
    d = {}
    if DICT_EN_ZO.exists():
        with open(DICT_EN_ZO) as f:
            for line in f:
                rec = json.loads(line)
                hw = rec.get("headword", "").strip().lower()
                trans = rec.get("translations", [])
                if hw and hw not in d:
                    d[hw] = trans
    return d

def load_corpus() -> list:
    """Load parallel corpus."""
    verses = []
    if CORPUS.exists():
        with open(CORPUS) as f:
            for line in f:
                verses.append(json.loads(line))
    return verses

def load_ai_cache() -> dict:
    """Load AI gloss cache."""
    d = {}
    if AI_CACHE.exists():
        with open(AI_CACHE) as f:
            for line in f:
                rec = json.loads(line)
                d[rec.get("word", "")] = rec.get("meaning", "")
    return d

# ══════════════════════════════════════════════════════════════════════
# GLOSSING ENGINE
# ══════════════════════════════════════════════════════════════════════
class GlossingEngine:
    def __init__(self, zo_en: dict, en_zo: dict, ai_cache: dict):
        self.zo_en = zo_en
        self.en_zo = en_zo
        self.ai_cache = ai_cache
        self.stats = {"dict_hit": 0, "ai_hit": 0, "miss": 0}
    
    def gloss_word(self, word: str, context: str = "") -> dict:
        """Gloss a single Zolai word."""
        w = word.strip().lower()
        
        # 1. Check ZO→EN dictionary
        if w in self.zo_en:
            self.stats["dict_hit"] += 1
            return {
                "word": word,
                "gloss": self.zo_en[w][0] if self.zo_en[w] else "?",
                "alternatives": self.zo_en[w][1:3],
                "source": "dict_zo_en",
                "confidence": "high"
            }
        
        # 2. Check AI cache
        if w in self.ai_cache:
            self.stats["ai_hit"] += 1
            return {
                "word": word,
                "gloss": self.ai_cache[w],
                "alternatives": [],
                "source": "ai_cache",
                "confidence": "medium"
            }
        
        # 3. Miss
        self.stats["miss"] += 1
        return {
            "word": word,
            "gloss": "?",
            "alternatives": [],
            "source": "miss",
            "confidence": "low"
        }
    
    def gloss_verse(self, zo_text: str) -> list:
        """Gloss all words in a verse."""
        words = re.findall(r"[a-zA-Z']+", zo_text)
        return [self.gloss_word(w, zo_text) for w in words]

# ══════════════════════════════════════════════════════════════════════
# STUDY ENGINE
# ══════════════════════════════════════════════════════════════════════
def study_book(book_code: str, verses: list, engine: GlossingEngine, 
               ai_flag: str = "") -> dict:
    """Study a single book and output results."""
    book_verses = [v for v in verses if v.get("book") == book_code]
    if not book_verses:
        return {"book": book_code, "verses": 0, "dict_rate": 0, "ai_rate": 0}
    
    output_file = STUDY_DIR / f"{book_code.lower()}_study.jsonl"
    results = []
    
    for verse in book_verses:
        ref = verse.get("ref", "")
        zo = verse.get("zo_tedim2010") or verse.get("zo_tdb77") or ""
        en = verse.get("en_kJV") or ""
        
        if not zo:
            continue
        
        # Gloss the verse
        glosses = engine.gloss_verse(zo)
        
        # Build result
        result = {
            "type": "verse",
            "ref": ref,
            "zo": zo,
            "en": en,
            "glosses": glosses,
            "timestamp": datetime.now().isoformat()
        }
        results.append(result)
        
        # Log key words
        for g in glosses:
            if g["source"] != "miss":
                log_event("gloss", word=g["word"], meaning=g["gloss"], 
                         source=g["source"], ref=ref)
    
    # Write study file
    with open(output_file, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    # Calculate stats
    total_words = sum(len(r["glosses"]) for r in results)
    dict_hits = sum(1 for r in results for g in r["glosses"] if g["source"] == "dict_zo_en")
    ai_hits = sum(1 for r in results for g in r["glosses"] if g["source"] == "ai_cache")
    
    dict_rate = (dict_hits / total_words * 100) if total_words else 0
    ai_rate = (ai_hits / total_words * 100) if total_words else 0
    
    log_event("book_done", book=book_code, verses=len(results),
             dict_rate=f"{dict_rate:.1f}%", ai_rate=f"{ai_rate:.1f}%")
    
    return {
        "book": book_code,
        "verses": len(results),
        "dict_rate": dict_rate,
        "ai_rate": ai_rate
    }

# ══════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════
def show_stats():
    """Show study statistics."""
    print(f"\n{Y}═══ Bible Study Statistics ═══{NC}\n")
    
    # Count study files
    study_files = list(STUDY_DIR.glob("*_study.jsonl"))
    print(f"  Books studied: {len(study_files)}/66")
    
    # Count AI cache
    if AI_CACHE.exists():
        with open(AI_CACHE) as f:
            cache_count = sum(1 for _ in f)
        print(f"  AI cache entries: {cache_count}")
    
    # Count log events
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            log_count = sum(1 for _ in f)
        print(f"  Log events: {log_count}")
    
    # Knowledge base files
    print(f"\n  {Y}Knowledge Base Files:{NC}")
    for name in ["parallel_corpus", "grammar_patterns", "vocabulary_db", 
                 "translation_pairs", "phrases", "verb_database", 
                 "particle_database", "book_summaries", "version_comparison"]:
        fp = KB_DIR / f"{name}_v1.jsonl"
        if fp.exists():
            with open(fp) as f:
                count = sum(1 for _ in f)
            print(f"    {G}✅ {name}_v1.jsonl: {count} entries{NC}")
        else:
            print(f"    {R}❌ {name}_v1.jsonl: missing{NC}")
    
    print()

# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Bible Study")
    parser.add_argument("--book", type=str, help="Book codes (comma-separated)")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted study")
    parser.add_argument("--no-ai", action="store_true", help="Dictionary only, no AI")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
        return
    
    # Ensure directories exist
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print(f"{G}Loading dictionaries...{NC}")
    zo_en = load_zo_en_dict()
    en_zo = load_en_zo_dict()
    ai_cache = load_ai_cache() if not args.no_ai else {}
    
    print(f"{G}Loading parallel corpus...{NC}")
    verses = load_corpus()
    
    print(f"{G}Loaded: {len(zo_en)} ZO→EN, {len(en_zo)} EN→ZO, {len(verses)} verses{NC}\n")
    
    # Initialize engine
    engine = GlossingEngine(zo_en, en_zo, ai_cache)
    
    # Determine books
    if args.book:
        books = [b.strip().upper() for b in args.book.split(",")]
    else:
        books = sorted(set(v.get("book", "") for v in verses if v.get("book")))
    
    # Resume: skip completed
    if args.resume:
        completed = set()
        for f in STUDY_DIR.glob("*_study.jsonl"):
            bc = f.stem.replace("_study", "").upper()
            completed.add(bc)
        books = [b for b in books if b not in completed]
        print(f"{G}Resuming: skipping {len(completed)} completed books{NC}\n")
    
    # Study each book
    print(f"{M}═══ Starting Bible Study ═══{NC}\n")
    for i, book in enumerate(books, 1):
        print(f"{B}[{i}/{len(books)}] Studying {book}...{NC}")
        result = study_book(book, verses, engine, 
                           "--no-ai" if args.no_ai else "")
        print(f"  {G}✓ {result['verses']} verses, "
              f"dict={result['dict_rate']:.1f}%, ai={result['ai_rate']:.1f}%{NC}")
    
    # Summary
    print(f"\n{M}═══ Study Complete ═══{NC}")
    print(f"  Books: {len(books)}")
    print(f"  Dict hits: {engine.stats['dict_hit']}")
    print(f"  AI hits: {engine.stats['ai_hit']}")
    print(f"  Misses: {engine.stats['miss']}")

if __name__ == "__main__":
    main()
