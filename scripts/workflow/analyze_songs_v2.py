#!/usr/bin/env python3
"""Analyze Zomi Worship Collective songs 41-60 — improved version."""
import re
from pathlib import Path

# Song directory
SONG_DIR = Path("/home/peter/Documents/Projects/zolai-ai/data/raw/Zomi Worship Collective/")
OUTPUT_FILE = Path("/home/peter/Documents/Projects/zolai-ai/zolai-wiki/grammar/song_analysis_zomi_worship_batch3.md")

# Get songs 41-60
files = sorted(SONG_DIR.glob("*.txt"))
batch = files[40:60]

# English translations for titles
translations = {
    "Hanciam Lai.txt": "Walk Together",
    "Hehpihna Simloh.txt": "Accept Redemption",
    "Hehpihna Tawh Ki Dimlet.txt": "Drenched in Redemption",
    "Hiah Om Ing Hong Bia Ding.txt": "You Will Declare Where You Are",
    "Hih Ciang Dong Topa.txt": "At This Moment, Lord",
    "Hih Mun Ah.txt": "In This Place",
    "Hon Domsang.txt": "They Have Come Together",
    "Hon Pa Zeisu.txt": "Our Father Jesus",
    "Hong Honpa In Hong Kun.txt": "You Crowned with Honor",
    "Hong Hopih Aw.txt": "Come Closer",
    "Hong Hopih In.txt": "Drawing Near",
    "Hong It Gumpa.txt": "Love the Bridegroom",
    "Hong It Lo Hi Leh.txt": "If You Don't Love",
    "Hong It Lua Ing Zeisu.txt": "Love More, Jesus",
    "Hong It Pasian.txt": "Love God",
    "Hong Khel Aw.txt": "Guide Me",
    "Hong Len In.txt": "Walk With Me",
    "Hong Nai Sak In.txt": "Lead Me",
    "Hong Ngai Ing.txt": "Worship",
    "Hong Pah Tawi Ung.txt": "Praise Again",
}

# Comprehensive vocabulary dictionary
vocab_dict = {
    "pasian": "God",
    "topa": "Lord",
    "zeisu": "Jesus",
    "vantung": "heaven",
    "leitung": "earth",
    "itna": "love",
    "hehpihna": "redemption",
    "suahtakna": "holiness",
    "nuntakna": "life",
    "thupha": "blessing",
    "gualzawhna": "grace",
    "vangliatna": "glory",
    "phatna": "praise",
    "pahtawina": "worship",
    "lungmuanna": "comfort",
    "lametna": "suffering",
    "kumpi": "bridegroom",
    "singlamteh": "cross",
    "kha siangtho": "Holy Spirit",
    "nuntak": "alive",
    "lunggulh": "heart",
    "khempeuh": "everything",
    "tampi": "many",
    "zawh": "completely",
    "thanem": "mouth",
    "kipan": "begin",
    "mitsuan": "tears",
    "kihel": "share",
    "lam": "road",
    "tel": "join",
    "sem": "serve",
    "hoih": "good",
    "thahat": "strong",
    "zung": "also",
    "hanciam": "together",
    "lai": "walk",
    "sep": "work",
    "zaw": "complete",
    "kawm": "together",
    "lau": "afraid",
    "omkei": "not exist",
    "hong": "you (honorific)",
    "nong": "you (honorific)",
    "ka": "I",
    "na": "you",
    "a": "he/she",
    "i": "we",
    "keng": "will",
    "ding": "future",
    "hi": "is",
    "ta": "past",
    "zo": "completed",
    "lai": "progressive",
    "khin": "experiential",
    "kei": "negation",
    "lo": "negation (literary)",
    "in": "ergative",
    "leh": "and",
    "tawh": "with",
    "pan": "from",
    "teng": "on",
    "ah": "at",
    "sung": "inside",
    "kiang": "hand",
    "khut": "hand",
    "lung": "heart",
    "sim": "mind",
    "mit": "eye",
    "hun": "time",
    "ni": "day",
    "man": "price",
    "dam": "well",
    "sing": "tree",
    "khua": "village",
    "tui": "water",
    "mi": "person",
    "numei": "woman",
    "mipa": "man",
    "pianpih": "children",
    "inn": "house",
    "gam": "land",
    "khuavak": "light",
    "khuamial": "darkness",
    "vantung": "heaven",
    "leitung": "earth",
    "laisiangtho": "Bible",
    "pasian": "God",
    "tapa": "son/life",
    "topa": "Lord",
    "kumpipa": "Savior",
    "suahtakna": "holiness",
    "nuntakna": "life",
}

def parse_lyrics(content: str) -> str:
    """Extract lyrics from song file."""
    lines = content.strip().split("\n")
    lyrics_start = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("Title:"):
            lyrics_start = i
            break
    return "\n".join(lines[lyrics_start:])

def find_key_lines(lyrics: str) -> list:
    """Find 2-3 key lines for word-by-word analysis."""
    lines = [l.strip() for l in lyrics.split("\n") if l.strip()]
    # Skip section headers like "Verse 1", "Chorus", etc.
    content_lines = []
    for line in lines:
        if not re.match(r'^(Verse|Chorus|Bridge|Pre-Chorus|Tag|Outro|Intro)\s*\d*$', line, re.IGNORECASE):
            content_lines.append(line)
    return content_lines[:3] if len(content_lines) >= 3 else content_lines

def get_word_translation(word: str) -> str:
    """Get English translation for a Zolai word."""
    word_lower = word.lower().strip(".,!?;:'\"")
    if word_lower in vocab_dict:
        return vocab_dict[word_lower]
    # Check compound words
    for key, val in vocab_dict.items():
        if key in word_lower:
            return val
    return "—"

def analyze_song(song_file: Path, idx: int) -> str:
    """Generate compact analysis for a song."""
    content = song_file.read_text(encoding="utf-8")
    title = song_file.stem
    translation = translations.get(song_file.name, title)
    lyrics = parse_lyrics(content)
    
    # Find key lines
    key_lines = find_key_lines(lyrics)
    
    # Word-by-word table for first key line
    word_table = ""
    if key_lines:
        first_line = key_lines[0]
        words = first_line.split()
        table_rows = []
        for word in words[:6]:  # Limit to 6 words
            eng = get_word_translation(word)
            table_rows.append(f"| {word} | {eng} |")
        word_table = "\n".join(table_rows)
    
    # Extract new vocabulary (words not in common vocab)
    all_words = set()
    for line in lyrics.split("\n"):
        for word in line.split():
            cleaned = word.lower().strip(".,!?;:'\"")
            if len(cleaned) > 3 and cleaned not in vocab_dict:
                all_words.add(cleaned)
    new_vocab_str = ", ".join(sorted(all_words)[:8]) if all_words else "—"
    
    # Determine themes
    themes = []
    text_lower = lyrics.lower()
    if any(w in text_lower for w in ["pasian", "topa", "zeisu"]):
        themes.append("worship")
    if any(w in text_lower for w in ["itna", "love"]):
        themes.append("love")
    if any(w in text_lower for w in ["hehpihna", "sianthona"]):
        themes.append("redemption")
    if any(w in text_lower for w in ["thupha", "phatna"]):
        themes.append("blessing")
    if any(w in text_lower for w in ["vantung", "leitung"]):
        themes.append("creation")
    if any(w in text_lower for w in ["lametna", "haksat"]):
        themes.append("suffering")
    if any(w in text_lower for w in ["gualzawhna"]):
        themes.append("grace")
    themes_str = ", ".join(themes[:3]) if themes else "worship"
    
    # Build analysis block
    analysis = f"""## {idx}. {title}

**Translation:** {translation}

```
{lyrics.strip()}
```

**Key line — word by word:**
| Zolai | English |
|-------|---------|
{word_table}

**New vocabulary:** {new_vocab_str}

**Themes:** {themes_str}

---"""
    return analysis

# Generate main content
header = """# Zomi Worship Collective — Song Analysis (Batch 3: Songs 41–60)

**Source:** [Zomi Worship Collective](https://www.zomiworshipcollective.com/) — alphabetic batch 3 (files 41–60)
**Orthography:** ZVS 2018

---
"""

analyses = []
for i, song_file in enumerate(batch):
    idx = i + 41
    analyses.append(analyze_song(song_file, idx))

full_content = header + "\n\n".join(analyses)

# Write output
OUTPUT_FILE.write_text(full_content, encoding="utf-8")
print(f"✅ Generated: {OUTPUT_FILE}")
print(f"   Songs: {len(batch)} (41–60)")
print(f"   Lines: {full_content.count(chr(10)) + 1}")

# Check for ZVS 2018 violations
forbidden = ["pathian", "ram", "fapa", "bawipa", "siangpahrang", "cu ", "cun ", "suah ", "nunnak "]
violations = []
for i, song_file in enumerate(batch):
    content = song_file.read_text(encoding="utf-8").lower()
    for word in forbidden:
        if word in content:
            violations.append(f"{song_file.name}: contains '{word}'")

if violations:
    print("\n⚠️  ZVS 2018 violations found:")
    for v in violations:
        print(f"   - {v}")
else:
    print("\n✅ No ZVS 2018 violations detected")
