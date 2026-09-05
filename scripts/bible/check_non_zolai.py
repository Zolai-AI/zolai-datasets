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
    "a": "Hakha - possessive (Zolai: a)",
    "a nu": "Hakha - his mother (Zolai: a neih)",
    "a pi": "Hakha - his father (Zolai: a pa)",
    "a ser": "Hakha - created (Zolai: a piangsak)",
    "a sip": "Hakha - he died (Zolai: a si)",
    "a thlungrawng": "Hakha - his reward (Zolai: a thatna)",
    "a ti": "Hakha - said (Zolai: ci hi)",
    "a tlung": "Hakha - he came (Zolai: a tung)",
    "a zi": "Hakha - his wife (Zolai: a neih)",
    "a zu": "Hakha - his child (Zolai: a neih)",
    "ah ai": "Hakha - there is (Zolai: ah om)",
    "ah lei": "Hakha - there is (Zolai: ah om)",
    "an": "Hakha - possessive (Zolai: a)",
    "an a": "Hakha - possessive (Zolai: a)",
    "an i": "Hakha - possessive (Zolai: a)",
    "arfi": "Hakha/Falam - stars (Zolai: khang)",
    "asem": "Hakha - work (Zolai: nasem)",
    "atlung": "Hakha - come (Zolai: atung)",
    "bang a": "Hakha - what is (Zolai: bang hi)",
    "bang i": "Hakha - what is (Zolai: bang hi)",
    "bawl a": "Hakha - made (Zolai: bawl hi)",
    "bawl i": "Hakha - made (Zolai: bawl hi)",
    "ceunak": "Hakha/Falam - light (Zolai: khuavak)",
    "cheunak": "Hakha - division (Zolai: khenhnak)",
    "chinmi": "Hakha - thing (Zolai: thil)",
    "chuahter": "Hakha - born (Zolai: suak)",
    "chuak": "Hakha - born/exit (Zolai: suak)",
    "chuakthar": "Hakha - newborn (Zolai: suak tuung)",
    "chuaktharmi": "Hakha - newborn (Zolai: suak tuung)",
    "chuan": "Hakha - from (Zolai: pan)",
    "ci a": "Hakha - said (Zolai: ci hi)",
    "ci i": "Hakha - said (Zolai: ci hi)",
    "cu": "Hakha/Falam - topic marker (Zolai: pen)",
    "cu a": "Hakha - topic marker (Zolai: pen a)",
    "cu i": "Hakha - topic marker (Zolai: pen i)",
    "cun": "Hakha - then (Zolai: tua ciangin)",
    "cuticun": "Hakha - then (Zolai: tua ciangin)",
    "daw": "Hakha - at/on (Zolai: taw)",
    "deuh": "Hakha - small (Zolai: neu)",
    "deuh a": "Hakha - small (Zolai: neu a)",
    "deuh i": "Hakha - small (Zolai: neu i)",
    "duhi": "Hakha - that (Zolai: tua)",
    "duhmi": "Hakha - this (Zolai: hih)",
    "ei": "Hakha/Falam - eat (Zolai: nek)",
    "hlan": "Hakha - before (Zolai: hmai)",
    "hlanah": "Hakha - before (Zolai: hmai)",
    "hmai a": "Hakha - front (Zolai: hmai a)",
    "hmai i": "Hakha - front (Zolai: hmai i)",
    "hmaisa": "Hakha - front (Zolai: hmai)",
    "hme": "Hakha - animal (Zolai: saram)",
    "hme a": "Hakha - animal (Zolai: saram a)",
    "hme i": "Hakha - animal (Zolai: saram i)",
    "hna": "Hakha - plural (Zolai: (plural))",
    "hna a": "Hakha - plural (Zolai: (plural) a)",
    "hna i": "Hakha - plural (Zolai: (plural) i)",
    "hramthawk": "Hakha - beginning (Zolai: kipat)",
    "kha a": "Hakha - Spirit (Zolai: kha a)",
    "kha i": "Hakha - Spirit (Zolai: kha i)",
    "kha knife": "Hakha - knife (NOT spirit) (Zolai: kha)",
    "khai": "Hakha - good (Zolai: hoih)",
    "khai a": "Hakha - good (Zolai: hoih a)",
    "khai i": "Hakha - good (Zolai: hoih i)",
    "ku a": "Hakha - who (Zolai: kua a)",
    "ku i": "Hakha - who (Zolai: kua i)",
    "kung": "Hakha/Falam - tree (Zolai: sing)",
    "law": "Hakha - please (Zolai: la)",
    "law a": "Hakha - please (Zolai: la a)",
    "law i": "Hakha - please (Zolai: la i)",
    "le": "Hakha/Falam - and (Zolai: leh)",
    "le a": "Hakha - and (Zolai: leh a)",
    "le i": "Hakha - and (Zolai: leh i)",
    "lung a si": "Hakha - good (Zolai: hoih)",
    "lungasi": "Hakha/Falam - good (Zolai: hoih)",
    "min a": "Hakha - name (Zolai: min a)",
    "min i": "Hakha - name (Zolai: min i)",
    "minsak": "Hakha/Falam - named (Zolai: kici)",
    "minu": "Hakha/Falam - woman (Zolai: numei)",
    "minung": "Hakha/Falam - person (Zolai: mi)",
    "mu a": "Hakha - saw (Zolai: mu a)",
    "mu i": "Hakha - saw (Zolai: mu i)",
    "muihnak": "Hakha/Falam - darkness (Zolai: khuamial)",
    "na a": "Hakha - you (Zolai: na a)",
    "na i": "Hakha - you (Zolai: na i)",
    "ngan": "Hakha - animal (Zolai: saram)",
    "ni a": "Hakha - ergative (Zolai: in a)",
    "ni i": "Hakha - ergative (Zolai: in i)",
    "nih": "Hakha/Falam - ergative (Zolai: in)",
    "pathian": "Hakha/Falam - God (Zolai: Pasian)",
    "paw a": "Hakha - side (Zolai: paw a)",
    "paw i": "Hakha - side (Zolai: paw i)",
    "pi a": "Hakha - father (Zolai: pa a)",
    "pi i": "Hakha - father (Zolai: pa i)",
    "pu a": "Hakha - gathered (Zolai: kikhawm a)",
    "pu i": "Hakha - gathered (Zolai: kikhawm i)",
    "pum": "Hakha/Falam - gathered (Zolai: kikhawm)",
    "ramsa": "Hakha/Falam - sea (Zolai: tuipi)",
    "rauh": "Hakha - run (Zolai: hei)",
    "sawn": "Hakha - help (Zolai: hawl)",
    "sawn a": "Hakha - help (Zolai: hawl a)",
    "sawn i": "Hakha - help (Zolai: hawl i)",
    "seh": "Hakha - imperative (Zolai: seh)",
    "seh a": "Hakha - imperative (Zolai: seh a)",
    "seh i": "Hakha - imperative (Zolai: seh i)",
    "ser": "Hakha/Falam - created (Zolai: piangsak/bawl)",
    "ser a": "Hakha - created (Zolai: piangsak a)",
    "ser i": "Hakha - created (Zolai: piangsak i)",
    "thluachuahnak": "Hakha/Falam - bless (Zolai: thupha)",
    "ti": "Hakha/Falam - quotative (Zolai: ci)",
    "ti a": "Hakha - said (Zolai: ci a)",
    "ti i": "Hakha - said (Zolai: ci i)",
    "tiah": "Hakha - said (Zolai: ci-in)",
    "tiah a": "Hakha - said (Zolai: ci-in a)",
    "tiah i": "Hakha - said (Zolai: ci-in i)",
    "tthennak": "Hakha - division (Zolai: khenhnak)",
    "tun": "Hakha - come (Zolai: tung)",
    "um": "Hakha/Falam - exist (Zolai: om)",
    "um a": "Hakha - exist (Zolai: om a)",
    "um i": "Hakha - exist (Zolai: om i)",
    "va a": "Hakha - bird (Zolai: va a)",
    "va i": "Hakha - bird (Zolai: va i)",
    "van": "Hakha/Falam - heaven (Zolai: vantung)",
    "vawlei": "Hakha/Falam - earth (Zolai: lebung)",
    "zinglei": "Hakha/Falam - morning (Zolai: zingsang)",
    "zoh": "Hakha/Falam - saw (Zolai: mu)",
    "zoh a": "Hakha - saw (Zolai: mu a)",
    "zoh i": "Hakha - saw (Zolai: mu i)",
    "ṭhawnnak": "Hakha/Falam - Spirit (Zolai: Kha)",
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
