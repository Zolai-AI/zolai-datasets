#!/usr/bin/env python3
"""Check dictionaries for non-Zolai (Hakha/Falam) words."""
import json
import os
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

# Known non-Zolai words (Hakha/Falam intrusions)
NON_ZOLAI = {
    "chuak": "Hakha/Falam - Zolai: suak",
    "chuahter": "Hakha - Zolai: suak",
    "chuaktharmi": "Hakha - Zolai: suak tuung",
    "chuakthar": "Hakha - Zolai: suak tuung",
    "chuan": "Hakha - Zolai: pan",
    "chinmi": "Hakha - Zolai: thil",
    "duhi": "Hakha - Zolai: tua",
    "duhmi": "Hakha - Zolai: hih",
    "rauh": "Hakha - Zolai: hei",
    "hlanah": "Hakha - Zolai: hmai",
    "hmaisa": "Hakha - Zolai: hmai",
    "sawn": "Hakha - Zolai: hawl",
    "deuh": "Hakha - Zolai: neu",
    "tthennak": "Hakha - Zolai: khenhnak",
    "cheunak": "Hakha - Zolai: khenhnak",
    "law": "Hakha - Zolai: la",
    "ngan": "Hakha - Zolai: saram",
    "ti": "Hakha - Zolai: ci",
    "pathian": "Hakha/Falam - Zolai: Pasian",
    "ceunak": "Hakha/Falam - Zolai: khuavak",
    "muihnak": "Hakha/Falam - Zolai: khuamial",
    "vawlei": "Hakha/Falam - Zolai: lebung",
    "minung": "Hakha/Falam - Zolai: mi",
    "minu": "Hakha/Falam - Zolai: numei",
    "kung": "Hakha/Falam - Zolai: sing",
    "ei": "Hakha/Falam - Zolai: nek",
    "zinglei": "Hakha/Falam - Zolai: zingsang",
    "thluachuahnak": "Hakha/Falam - Zolai: thupha",
    "ramsa": "Hakha/Falam - Zolai: tuipi",
    "arfi": "Hakha/Falam - Zolai: khang",
    "ser": "Hakha/Falam - Zolai: piangsak/bawl",
    "um": "Hakha/Falam - Zolai: om",
    "cu": "Hakha/Falam - Zolai: pen",
    "nih": "Hakha/Falam - Zolai: in",
    "leh": "Hakha/Falam - Zolai: leh (shared)",
    "va": "Hakha/Falam - Zolai: va (shared)",
}

# Check dictionaries
dict_files = [
    DATA / "dictionary/processed/dict_zo_en_master_v1.jsonl",
    DATA / "dictionary/processed/dict_canonical_v1.jsonl",
    DATA / "dictionary/wordlists/zo_en_wordlist_v1.jsonl",
]

found_words = {}
for dict_path in dict_files:
    if not dict_path.exists():
        continue
    with open(dict_path) as f:
        for line in f:
            d = json.loads(line)
            hw = (d.get("headword") or d.get("zolai") or d.get("word") or "").lower().strip()
            if hw in NON_ZOLAI:
                if hw not in found_words:
                    found_words[hw] = {
                        "reason": NON_ZOLAI[hw],
                        "in_bible": hw in bible_words,
                        "sources": set(),
                    }
                found_words[hw]["sources"].add(dict_path.name)

# Separate into categories
in_bible = {w: i for w, i in found_words.items() if i["in_bible"]}
not_in_bible = {w: i for w, i in found_words.items() if not i["in_bible"]}

print("  === Non-Zolai Word Check ===")
print()

if not_in_bible:
    print(f"  ❌ {len(not_in_bible)} words NOT in Zolai Bible (should remove):")
    print()
    for hw in sorted(not_in_bible.keys()):
        info = not_in_bible[hw]
        sources_str = ", ".join(info["sources"])
        print(f"    {hw:25s} {info['reason']}")
        print(f"    {'':25s} Found in: {sources_str}")
    print()

if in_bible:
    print(f"  ✅ {len(in_bible)} words IN Zolai Bible (valid cognates, kept):")
    print()
    for hw in sorted(in_bible.keys()):
        info = in_bible[hw]
        sources_str = ", ".join(info["sources"])
        print(f"    {hw:25s} {info['reason']}")
    print()

total = len(found_words)
clean = total == 0
if clean:
    print("  ✅ All dictionaries are clean — Zolai/Tedim only!")
else:
    print(f"  Total: {total} non-Zolai words found in dictionaries")
