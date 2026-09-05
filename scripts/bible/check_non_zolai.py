#!/usr/bin/env python3
"""Check dictionaries for non-Zolai (Hakha/Falam) words — comprehensive v2."""
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("WORKSPACE", str(Path(__file__).resolve().parents[3]))) / "data"

# Load Bible words (confirmed Zolai)
bible_words = set()
bible_path = DATA / "bible/zolai_bible_words.jsonl"
if bible_path.exists():
    with open(bible_path) as f:
        for line in f:
            d = json.loads(line)
            bible_words.add(d["word"])

# Load comprehensive Hakha/Falam word list
NON_ZOLAI = {}
wordlist_path = DATA / "dictionary/hakha_falam_wordlist_v2.json"
if wordlist_path.exists():
    with open(wordlist_path) as f:
        data = json.load(f)
        NON_ZOLAI = data.get("all_words", {})

# Add pattern-based detection
HAKHA_PATTERNS = {
    "chuak": "Hakha/Falam birth/exit verb (Zolai: suak)",
    "chuahter": "Hakha birth verb (Zolai: suak)",
    "chuan": "Hakha from (Zolai: pan)",
    "chinmi": "Hakha thing (Zolai: thil)",
    "duhi": "Hakha that (Zolai: tua)",
    "duhmi": "Hakha this (Zolai: hih)",
    "rauh": "Hakha run (Zolai: hei)",
    "hlanah": "Hakha before (Zolai: hmai)",
    "hmaisa": "Hakha front (Zolai: hmai)",
    "sawn": "Hakha help (Zolai: hawl)",
    "deuh": "Hakha small (Zolai: neu)",
    "tthennak": "Hakha division (Zolai: khenhnak)",
    "cheunak": "Hakha division (Zolai: khenhnak)",
    "law": "Hakha please (Zolai: la)",
    "ngan": "Hakha animal (Zolai: saram)",
    "ti": "Hakha said (Zolai: ci)",
    "cun": "Hakha then (Zolai: tua ciangin)",
    "cuticun": "Hakha then (Zolai: tua ciangin)",
    "hna": "Hakha plural marker",
    "tiah": "Hakha said (Zolai: ci-in)",
    "hramthawk": "Hakha beginning (Zolai: kipat)",
    "hme": "Hakha animal (Zolai: saram)",
    "pathian": "Hakha/Falam God (Zolai: Pasian)",
    "ceunak": "Hakha/Falam light (Zolai: khuavak)",
    "muihnak": "Hakha/Falam darkness (Zolai: khuamial)",
    "vawlei": "Hakha/Falam earth (Zolai: lebung)",
    "van": "Hakha/Falam heaven (Zolai: vantung)",
    "ramsa": "Hakha/Falam sea (Zolai: tuipi)",
    "minung": "Hakha/Falam person (Zolai: mi)",
    "minu": "Hakha/Falam woman (Zolai: numei)",
    "kung": "Hakha/Falam tree (Zolai: sing)",
    "arfi": "Hakha/Falam stars (Zolai: khang)",
    "zinglei": "Hakha/Falam morning (Zolai: zingsang)",
    "thluachuahnak": "Hakha/Falam bless (Zolai: thupha)",
    "ser": "Hakha/Falam created (Zolai: piangsak)",
    "ei": "Hakha/Falam eat (Zolai: nek)",
    "um": "Hakha/Falam exist (Zolai: om)",
    "cu": "Hakha/Falam topic marker (Zolai: pen)",
    "nih": "Hakha/Falam ergative (Zolai: in)",
    "zoh": "Hakha/Falam saw (Zolai: mu)",
    "lungasi": "Hakha/Falam good (Zolai: hoih)",
    "minsak": "Hakha/Falam named (Zolai: kici)",
    "pum": "Hakha/Falam gathered (Zolai: kikhawm)",
    "ṭhawnnak": "Hakha/Falam Spirit (Zolai: Kha)",
}

# Check dictionaries
dict_files = [
    DATA / "dictionary/processed/dict_zo_en_master_v1.jsonl",
    DATA / "dictionary/processed/dict_canonical_v1.jsonl",
    DATA / "dictionary/wordlists/zo_en_wordlist_v1.jsonl",
]

in_dict = {}
for dict_path in dict_files:
    if not dict_path.exists():
        continue
    with open(dict_path) as f:
        for line in f:
            d = json.loads(line)
            hw = (d.get("headword") or d.get("zolai") or d.get("word") or "").lower().strip()
            if hw in HAKHA_PATTERNS:
                if hw not in in_dict:
                    in_dict[hw] = set()
                in_dict[hw].add(dict_path.name)

# Categorize
removed = []
still_present = []
valid_cognates = []

for word, reason in sorted(HAKHA_PATTERNS.items()):
    in_bible = word in bible_words
    entry = {
        "word": word,
        "reason": reason,
        "in_bible": in_bible,
        "in_dict": word in in_dict,
        "sources": list(in_dict.get(word, set())),
    }
    if in_bible:
        valid_cognates.append(entry)
    elif word in in_dict:
        still_present.append(entry)
    else:
        removed.append(entry)

# Print report
print("  ═══════════════════════════════════════════════════════════")
print("  NON-ZOLAI WORD AUDIT — Comprehensive v2")
print("  ═══════════════════════════════════════════════════════════")
print()
print(f"  SUMMARY: {len(HAKHA_PATTERNS)} non-Zolai words tracked")
print(f"    ✅ {len(valid_cognates):2d} valid cognates (in Zolai Bible, KEPT)")
print(f"    🧹 {len(removed):2d} removed from dictionaries (CLEANED)")
print(f"    ❌ {len(still_present):2d} still in dictionaries (NEED REMOVAL)")
print()

if removed:
    print(f"  ─── REMOVED FROM DICTIONARIES ({len(removed)} words) ───")
    for e in removed:
        print(f"    {e['word']:25s} {e['reason']}")
    print()

if still_present:
    print(f"  ─── STILL IN DICTIONARIES ({len(still_present)} words) ───")
    for e in still_present:
        sources = ", ".join(e["sources"])
        print(f"    {e['word']:25s} {e['reason']}")
        print(f"    {'':25s} Found in: {sources}")
    print()

if valid_cognates:
    print(f"  ─── VALID COGNATES ({len(valid_cognates)} words) ───")
    for e in valid_cognates:
        print(f"    {e['word']:25s} {e['reason']}")
    print()

print("  ═══════════════════════════════════════════════════════════")
