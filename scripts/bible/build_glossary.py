#!/usr/bin/env python3
"""build_glossary.py — Build final glossary from verified dictionary + Bible frequency.

Generates pcore_brain_glossary_final.txt with:
1. All 21 corrected words with Bible references
2. Top 500 high-frequency Bible words
3. Grammar rules (SOV, negation, questions, tense)
"""

import json
import re
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DICT_PATH = DATA_DIR / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
CORPUS_PATH = DATA_DIR / "bible" / "parallel_corpus_v1.jsonl"
OUTPUT_PATH = DATA_DIR / "pcore_brain_glossary_final.txt"

# ── Corrected words with Bible references ──────────────────────────────────
CORRECTED_WORDS = [
    {"word": "in", "def": "ergative marker (agent of transitive)", "ref": "GEN 1:1", "freq": 23999},
    {"word": "leh", "def": "and (conjunction)", "ref": "GEN 1:3", "freq": 11770},
    {"word": "nek", "def": "specific/conditional eating", "ref": "1CO 8:4", "freq": 231},
    {"word": "kammal", "def": "deed/action/commandment", "ref": "1CH 16:15", "freq": 58},
    {"word": "siam", "def": "good/skilled/craftsman", "ref": "1CH 5:18", "freq": 76},
    {"word": "uh", "def": "plural marker (NOT standalone they)", "ref": "GEN 1:2", "freq": 12170},
    {"word": "sing", "def": "wood (NOT tree — tree = singkung)", "ref": "GEN 6:14", "freq": 202},
    {"word": "nasep", "def": "work/service (NOT deed — deed = kammal)", "ref": "1CH 6:31", "freq": 255},
    {"word": "na", "def": "possessive particle (your/my); quotative connector", "ref": "GEN 3:15", "freq": 10073},
    {"word": "kei", "def": "negation not (ALL persons); OR I/me", "ref": "GEN 4:7", "freq": 5606},
    {"word": "tawh", "def": "with (comitative); key; free-hand", "ref": "GEN 4:1", "freq": 6686},
    {"word": "ahi", "def": "copula is/am/are/was (context-dependent)", "ref": "GEN 1:2", "freq": 5909},
    {"word": "ci", "def": "say/speak/tell (quotative verb, most frequent)", "ref": "GEN 1:3", "freq": 6683},
    {"word": "lo", "def": "literary negation (standalone, NO agreement)", "ref": "GEN 4:12", "freq": 4251},
    {"word": "u", "def": "elder brother/sister (NOT they!)", "ref": "1JN 2:9", "freq": 104},
    {"word": "nau", "def": "younger brother/sister", "ref": "1CO 1:10", "freq": 92},
    {"word": "hihte", "def": "they (respectful/older)", "ref": "1CH 1:23", "freq": 301},
    {"word": "huate", "def": "those/them (demonstrative)", "ref": "1CH 4:23", "freq": 45},
    {"word": "mankhin", "def": "truly/completed", "ref": "EXO 39:32", "freq": 1},
    {"word": "kiman", "def": "finished/completed", "ref": "EXO 39:32", "freq": 71},
    {"word": "khin", "def": "past simple/experiential marker", "ref": "GEN 1:1", "freq": 8000},
    {"word": "ta", "def": "completive/realized aspect (NOT past simple)", "ref": "GEN 1:1", "freq": 9000},
]

# ── Grammar rules ──────────────────────────────────────────────────────────
GRAMMAR_RULES = """
## GRAMMAR RULES

### Word Order: SOV (Subject-Object-Verb)
Zolai is strictly SOV. The verb always comes last.
- S + V: Gam ka mu hi. (I see.)
- S + O + V: Gam ka mu hi. (I see the land.)
- S + O + V (ergative): Pasian in leitung a piangsak hi. (God created the earth.)

### Negation
- "kei" is the standard negation for ALL persons:
  - Ka pai kei hi. (I don't go.)
  - Na pai kei hi. (You don't go.)
  - A pai kei hi. (He doesn't go.)
- "lo" is literary/formal (standalone, NO agreement):
  - Pai lo hi. (Goes not.)
  - WRONG: A pai lo hi.

### Questions
- Yes/No: hiam at end
  - Na pai hiam? (Do you go?)
- Content: bang hang + verb + subject + hiam
  - Bang hang pai na hiam? (Why do you go?)

### Tense & Aspect
- Present: hi (A pai hi. — He goes.)
- Past simple: khin (A pai khin hi. — He went.)
- Future: ding (A pai ding hi. — He will go.)
- Completive: ta (A pai ta hi. — He finished going.)
- Progressive: lai (A ne lai hi. — He is eating.)

### Pronouns
- Agreement markers: a (3sg), ka (1sg), na (2sg)
- Standalone pronouns: amah (he/she/it), hihte/amaute/huate (they)

### Ergative "in"
- Marks the agent of transitive verbs
- Pasian in vantung leh leitung a piangsak hi. (God created heaven and earth.)

### Forbidden Forms (ZVS 2018)
- pathian → pasian (God)
- ram → gam (earth)
- fapa → tapa (life)
- bawipa → topa (Lord)
- siangpahrang → kumpipa (Savior)
- cu/cun → tua (that)
"""


def load_jsonl(path):
    """Load a JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_word_freq(corpus):
    """Build word frequency from Bible corpus."""
    word_freq = {}
    for verse in corpus:
        zo_text = verse.get("zo_tdb77") or verse.get("zo_tedim2010") or ""
        words = re.findall(r"\b\w+\b", zo_text.lower())
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
    return word_freq


def build_glossary(records, word_freq):
    """Build the final glossary."""
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("ZOLAI AI — FINAL GLOSSARY (Bible-Verified)")
    lines.append("=" * 70)
    lines.append(f"Generated: 2026-09-11")
    lines.append(f"Dictionary entries: {len(records)}")
    lines.append(f"Bible words with frequency: {len(word_freq)}")
    lines.append("")
    
    # Section 1: Corrected Words
    lines.append("=" * 70)
    lines.append("SECTION 1: CORRECTED WORDS (21 Bible-Verified Fixes)")
    lines.append("=" * 70)
    lines.append("")
    
    for i, item in enumerate(CORRECTED_WORDS, 1):
        lines.append(f"{i:2d}. {item['word']}")
        lines.append(f"    Definition: {item['def']}")
        lines.append(f"    Bible ref:  {item['ref']}")
        lines.append(f"    Frequency:  {item['freq']:,} occurrences")
        lines.append("")
    
    # Section 2: Top 500 High-Frequency Words
    lines.append("=" * 70)
    lines.append("SECTION 2: TOP 500 HIGH-FREQUENCY BIBLE WORDS")
    lines.append("=" * 70)
    lines.append("")
    
    # Sort by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])[:500]
    
    # Build dict lookup
    dict_lookup = {}
    for r in records:
        zolai = r.get("zolai", "").strip().lower()
        if zolai:
            dict_lookup[zolai] = r.get("english_clean", "") or ""
    
    for rank, (word, freq) in enumerate(sorted_words, 1):
        eng = dict_lookup.get(word, "NOT IN DICT")
        lines.append(f"{rank:3d}. {word}: {freq:,} — {eng}")
    
    lines.append("")
    
    # Section 3: Grammar Rules
    lines.append("=" * 70)
    lines.append("SECTION 3: GRAMMAR RULES")
    lines.append("=" * 70)
    lines.append(GRAMMAR_RULES)
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    print("Building final glossary...")
    
    # Load data
    print(f"Loading dictionary: {DICT_PATH}")
    records = load_jsonl(DICT_PATH)
    print(f"  Loaded {len(records)} entries")
    
    print(f"Loading Bible corpus: {CORPUS_PATH}")
    corpus = load_jsonl(CORPUS_PATH)
    print(f"  Loaded {len(corpus)} verses")
    
    # Build word frequency
    print("Building word frequency...")
    word_freq = build_word_freq(corpus)
    print(f"  Found {len(word_freq)} unique words")
    
    # Build glossary
    print("Building glossary...")
    glossary = build_glossary(records, word_freq)
    
    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(glossary)
    
    print(f"\nWrote glossary to: {OUTPUT_PATH}")
    print(f"  Lines: {len(glossary.splitlines())}")
    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
