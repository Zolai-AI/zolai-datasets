#!/usr/bin/env python3
"""
Full Knowledge Base Builder — All 66 Books
Extracts: grammar patterns, verbs, particles, book summaries, version comparison
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent.parent
DATA = WORKSPACE / "data"
KB_DIR = DATA / "bible"
CORPUS = KB_DIR / "parallel_corpus_v1.jsonl"
DICT_ZO_EN = DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
SUPPLEMENT_DICT = DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"

# ══════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════
def load_corpus() -> list:
    verses = []
    if CORPUS.exists():
        with open(CORPUS) as f:
            for line in f:
                verses.append(json.loads(line))
    return verses

def load_dict() -> dict:
    d = {}
    for path in [SUPPLEMENT_DICT, DICT_ZO_EN]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    hw = (rec.get("zolai") or rec.get("headword") or "").strip().lower()
                    eng = rec.get("english") or rec.get("translations") or []
                    if isinstance(eng, str):
                        eng = [eng]
                    if hw and hw not in d:
                        d[hw] = eng
    return d

# ══════════════════════════════════════════════════════════════════════
# BOOK DEFINITIONS
# ══════════════════════════════════════════════════════════════════════
BOOK_INFO = {
    "GEN": ("Genesis", 50, "narrative"), "EXO": ("Exodus", 40, "narrative"),
    "LEV": ("Leviticus", 27, "law"), "NUM": ("Numbers", 36, "narrative"),
    "DEU": ("Deuteronomy", 34, "law"), "JOS": ("Joshua", 24, "narrative"),
    "JUG": ("Judges", 21, "narrative"), "RUT": ("Ruth", 4, "narrative"),
    "1SA": ("1 Samuel", 31, "narrative"), "2SA": ("2 Samuel", 24, "narrative"),
    "1KI": ("1 Kings", 22, "narrative"), "2KI": ("2 Kings", 25, "narrative"),
    "1CH": ("1 Chronicles", 29, "narrative"), "2CH": ("2 Chronicles", 36, "narrative"),
    "EZR": ("Ezra", 10, "narrative"), "NEH": ("Nehemiah", 13, "narrative"),
    "EST": ("Esther", 10, "narrative"), "JOB": ("Job", 42, "poetry"),
    "PSA": ("Psalms", 150, "poetry"), "PRO": ("Proverbs", 31, "wisdom"),
    "ECC": ("Ecclesiastes", 12, "wisdom"), "SNG": ("Song of Solomon", 8, "poetry"),
    "ISA": ("Isaiah", 66, "prophecy"), "JER": ("Jeremiah", 52, "prophecy"),
    "LAM": ("Lamentations", 5, "poetry"), "EZK": ("Ezekiel", 48, "prophecy"),
    "DAN": ("Daniel", 12, "prophecy"), "HOS": ("Hosea", 14, "prophecy"),
    "JOE": ("Joel", 3, "prophecy"), "AMO": ("Amos", 9, "prophecy"),
    "OBA": ("Obadiah", 1, "prophecy"), "JON": ("Jonah", 4, "narrative"),
    "MIC": ("Micah", 7, "prophecy"), "NAM": ("Nahum", 3, "prophecy"),
    "HAB": ("Habakkuk", 3, "prophecy"), "ZEP": ("Zephaniah", 3, "prophecy"),
    "HAG": ("Haggai", 2, "prophecy"), "ZEC": ("Zechariah", 14, "prophecy"),
    "MAL": ("Malachi", 4, "prophecy"), "MAT": ("Matthew", 28, "gospel"),
    "MRK": ("Mark", 16, "gospel"), "LUK": ("Luke", 24, "gospel"),
    "JHN": ("John", 21, "gospel"), "ACT": ("Acts", 28, "narrative"),
    "ROM": ("Romans", 16, "epistle"), "1CO": ("1 Corinthians", 16, "epistle"),
    "2CO": ("2 Corinthians", 13, "epistle"), "GAL": ("Galatians", 6, "epistle"),
    "EPH": ("Ephesians", 6, "epistle"), "PHP": ("Philippians", 4, "epistle"),
    "COL": ("Colossians", 4, "epistle"), "1TH": ("1 Thessalonians", 5, "epistle"),
    "2TH": ("2 Thessalonians", 3, "epistle"), "1TI": ("1 Timothy", 6, "epistle"),
    "2TI": ("2 Timothy", 4, "epistle"), "TIT": ("Titus", 3, "epistle"),
    "PHM": ("Philemon", 1, "epistle"), "HEB": ("Hebrews", 13, "epistle"),
    "JAS": ("James", 5, "epistle"), "1PE": ("1 Peter", 5, "epistle"),
    "2PE": ("2 Peter", 3, "epistle"), "1JN": ("1 John", 5, "epistle"),
    "2JN": ("2 John", 1, "epistle"), "3JN": ("3 John", 1, "epistle"),
    "JUD": ("Jude", 1, "epistle"), "REV": ("Revelation", 22, "prophecy"),
}

# ══════════════════════════════════════════════════════════════════════
# GRAMMAR PATTERN EXTRACTION
# ══════════════════════════════════════════════════════════════════════
def extract_grammar_patterns(verses: list, d: dict) -> list:
    """Extract grammar patterns from all books."""
    patterns = []
    pattern_id = 1
    
    # Pattern templates
    pattern_templates = [
        # SOV patterns
        {"regex": r"^(\w+)\s+in\s+.+\s+(\w+)\s+hi$", "pattern": "S + in + O + V + hi",
         "meaning": "SOV declarative with topic marker", "function": "declarative"},
        {"regex": r"^(\w+)\s+in\s+.+\s+(\w+)\s+ci\s+hi$", "pattern": "S + in + O + V + ci hi",
         "meaning": "SOV with quotative", "function": "speech"},
        {"regex": r"^(\w+)\s+in\s+(\w+)\s+(\w+)\s+hi$", "pattern": "S + in + O + V + hi",
         "meaning": "Basic SOV", "function": "declarative"},
        
        # Tense/aspect
        {"regex": r"ding\s+\w+", "pattern": "ding + V", "meaning": "Future tense",
         "function": "future"},
        {"regex": r"ciangin\s+\w+", "pattern": "ciangin + V", "meaning": "Past tense",
         "function": "past"},
        {"regex": r"(\w+)\s+ta\s+\w+", "pattern": "V + ta + V", "meaning": "Completive",
         "function": "completive"},
        
        # Questions
        {"regex": r"hiam\s+cih", "pattern": "hiam cih", "meaning": "Question particle",
         "function": "question"},
        {"regex": r"hiam\s+cih\s+leh", "pattern": "hiam cih leh", "meaning": "Question tag",
         "function": "question_tag"},
        
        # Negation
        {"regex": r"(\w+)\s+lo\s+hi$", "pattern": "V + lo + hi", "meaning": "Negation",
         "function": "negation"},
        {"regex": r"(\w+)\s+a\s+lo", "pattern": "V + a + lo", "meaning": "Negation",
         "function": "negation"},
        
        # Commands
        {"regex": r"^(\w+)\s+\w+!$", "pattern": "V!", "meaning": "Imperative",
         "function": "command"},
        {"regex": r"^ci\s+ta", "pattern": "ci ta", "meaning": "Let it be",
         "function": "jussive"},
        
        # Conditionals
        {"regex": r"bang\s+hang\s+hiam", "pattern": "bang hang hiam", "meaning": "If",
         "function": "conditional"},
        {"regex": r"bang\s+hang\s+hiam\s+cih\s+leh", "pattern": "bang hang hiam cih leh",
         "meaning": "If...then", "function": "conditional"},
    ]
    
    # Collect frequency data
    freq_counter = Counter()
    examples = defaultdict(list)
    
    for v in verses:
        zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
        ref = v.get("ref", "")
        book = v.get("book", "")
        
        for tmpl in pattern_templates:
            if re.search(tmpl["regex"], zo):
                key = tmpl["pattern"]
                freq_counter[key] += 1
                if len(examples[key]) < 3:
                    examples[key].append({"ref": ref, "zo": zo[:100], "book": book})
    
    # Build pattern entries
    for tmpl in pattern_templates:
        key = tmpl["pattern"]
        if freq_counter[key] > 0:
            entry = {
                "id": f"ZO-GRAM-{pattern_id:04d}",
                "pattern": tmpl["pattern"],
                "meaning": tmpl["meaning"],
                "structure": tmpl["pattern"],
                "function": tmpl["function"],
                "examples": examples[key],
                "frequency": freq_counter[key],
                "confidence": "high" if freq_counter[key] >= 10 else "medium",
                "book": "all",
                "notes": ""
            }
            patterns.append(entry)
            pattern_id += 1
    
    return patterns

# ══════════════════════════════════════════════════════════════════════
# VERB DATABASE
# ══════════════════════════════════════════════════════════════════════
def build_verb_database(verses: list, d: dict) -> list:
    """Build comprehensive verb database."""
    verbs = []
    
    # Common verbs with their properties
    common_verbs = {
        "ci": {"english": ["say", "speak", "tell"], "transitivity": "transitive",
               "objects": ["word", "thing", "name"], "pattern": "S + O + ci"},
        "hei": {"english": ["go", "walk"], "transitivity": "intransitive",
                "objects": ["place", "way"], "pattern": "S + place + hei"},
        "tung": {"english": ["come", "arrive"], "transitivity": "intransitive",
                 "objects": ["place"], "pattern": "S + place + tung"},
        "hoih": {"english": ["see", "look"], "transitivity": "transitive",
                 "objects": ["thing", "person"], "pattern": "S + O + hoih"},
        "nei": {"english": ["have", "hold"], "transitivity": "transitive",
                "objects": ["thing", "power"], "pattern": "S + O + nei"},
        "piang": {"english": ["make", "create"], "transitivity": "transitive",
                  "objects": ["thing", "person"], "pattern": "S + O + piang"},
        "bawl": {"english": ["make", "create"], "transitivity": "transitive",
                 "objects": ["thing", "person"], "pattern": "S + O + bawl"},
        "lei": {"english": ["take", "carry"], "transitivity": "transitive",
                "objects": ["thing"], "pattern": "S + O + lei"},
        "sung": {"english": ["eat", "consume"], "transitivity": "transitive",
                 "objects": ["food"], "pattern": "S + O + sung"},
        "in": {"english": ["drink"], "transitivity": "transitive",
               "objects": ["liquid"], "pattern": "S + O + in"},
        "om": {"english": ["exist", "be present"], "transitivity": "intransitive",
               "objects": ["place"], "pattern": "S + place + om"},
        "kawm": {"english": ["die", "perish"], "transitivity": "intransitive",
                 "objects": [], "pattern": "S + kawm"},
        "phat": {"english": ["live", "be alive"], "transitivity": "intransitive",
                 "objects": [], "pattern": "S + phat"},
        "mu": {"english": ["know", "understand"], "transitivity": "transitive",
               "objects": ["thing", "person"], "pattern": "S + O + mu"},
        "sim": {"english": ["love", "like"], "transitivity": "transitive",
                "objects": ["person", "thing"], "pattern": "S + O + sim"},
        "thupha": {"english": ["bless"], "transitivity": "transitive",
                   "objects": ["person"], "pattern": "S + O + thupha"},
        "na": {"english": ["fear", "be afraid"], "transitivity": "transitive",
               "objects": ["person", "thing"], "pattern": "S + O + na"},
        "pau": {"english": ["trust", "believe"], "transitivity": "transitive",
                "objects": ["person", "God"], "pattern": "S + O + pau"},
        "gen": {"english": ["follow", "obey"], "transitivity": "transitive",
                "objects": ["person", "law"], "pattern": "S + O + gen"},
        "tampi": {"english": ["multiply", "increase"], "transitivity": "intransitive",
                  "objects": [], "pattern": "S + tampi"},
    }
    
    # Count frequencies
    verb_freq = Counter()
    verb_examples = defaultdict(list)
    
    for v in verses:
        zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
        ref = v.get("ref", "")
        words = re.findall(r"[a-zA-Z']+", zo)
        
        for w in words:
            wl = w.lower()
            if wl in common_verbs:
                verb_freq[wl] += 1
                if len(verb_examples[wl]) < 3:
                    verb_examples[wl].append(ref)
    
    # Build entries
    for verb, info in common_verbs.items():
        entry = {
            "verb": verb,
            "english": info["english"],
            "pos": "verb",
            "argument_structure": info["pattern"],
            "transitivity": info["transitivity"],
            "objects": info["objects"],
            "tense_aspects": ["present", "past", "future"],
            "negation": f"{verb} + lo",
            "commands": verb,
            "derived_forms": [],
            "frequency": verb_freq.get(verb, 0),
            "examples": verb_examples.get(verb, [])
        }
        verbs.append(entry)
    
    return verbs

# ══════════════════════════════════════════════════════════════════════
# PARTICLE DATABASE
# ══════════════════════════════════════════════════════════════════════
def build_particle_database(verses: list, d: dict) -> list:
    """Build comprehensive particle database."""
    particles = []
    
    # Common particles
    particle_info = {
        "hi": {"position": "sentence-final", "function": "declarative",
               "meaning": "marks statement", "english": "(declarative)"},
        "in": {"position": "post-verbal", "function": "imperative",
               "meaning": "marks command", "english": "(imperative)"},
        "hong": {"position": "pre-verbal", "function": "directional",
                 "meaning": "toward speaker", "english": "come (here)"},
        "leh": {"position": "post-verbal", "function": "reciprocal",
                "meaning": "return, reciprocate", "english": "again, back"},
        "ciangin": {"position": "pre-verbal", "function": "temporal",
                    "meaning": "then, at that time", "english": "then"},
        "ding": {"position": "pre-verbal", "function": "future",
                 "meaning": "will, going to", "english": "will"},
        "pen": {"position": "pre-nominal", "function": "topic",
                "meaning": "as for, regarding", "english": "(topic marker)"},
        "ah": {"position": "post-nominal", "function": "locative",
               "meaning": "in, at, to", "english": "in/at/to"},
        "tungah": {"position": "post-nominal", "function": "locative",
                   "meaning": "above, on top of", "english": "above/on"},
        "sungah": {"position": "post-nominal", "function": "locative",
                   "meaning": "inside, within", "english": "inside/in"},
        "kiangah": {"position": "post-nominal", "function": "locative",
                    "meaning": "outside, without", "english": "outside"},
        "panin": {"position": "post-nominal", "function": "locative",
                  "meaning": "before, in front of", "english": "before"},
        "tua": {"position": "pre-nominal", "function": "demonstrative",
                "meaning": "that, those", "english": "that/those"},
        "hih": {"position": "pre-nominal", "function": "demonstrative",
                "meaning": "this, these", "english": "this/these"},
        "ka": {"position": "pre-verbal", "function": "agreement",
               "meaning": "1st person agreement", "english": "(I/me)"},
        "kei": {"position": "pre-verbal", "function": "pronoun",
                "meaning": "I, me", "english": "I/me"},
        "amah": {"position": "pre-verbal", "function": "pronoun",
                 "meaning": "he, she, it", "english": "he/she/it"},
        "uh": {"position": "pre-verbal", "function": "pronoun",
               "meaning": "they, them", "english": "they/them"},
        "amaute": {"position": "pre-verbal", "function": "pronoun",
                   "meaning": "they (emphatic)", "english": "they (emphatic)"},
        "mite": {"position": "pre-verbal", "function": "noun",
                 "meaning": "people, persons", "english": "people"},
        "mi": {"position": "pre-verbal", "function": "noun",
               "meaning": "person, man", "english": "person/man"},
        "topa": {"position": "pre-verbal", "function": "title",
                 "meaning": "Lord, Master", "english": "Lord"},
        "pasian": {"position": "pre-verbal", "function": "title",
                   "meaning": "God", "english": "God"},
        "ahih": {"position": "sentence-final", "function": "copula",
                 "meaning": "is, am, are", "english": "is/am/are"},
        "ahi": {"position": "sentence-final", "function": "copula",
                "meaning": "is, am, are", "english": "is/am/are"},
        "ci": {"position": "pre-verbal", "function": "quotative",
               "meaning": "say, speak", "english": "say/speak"},
        "hiam": {"position": "sentence-initial", "function": "question",
                 "meaning": "question particle", "english": "?"},
    }
    
    # Count frequencies
    particle_freq = Counter()
    particle_examples = defaultdict(list)
    
    for v in verses:
        zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
        ref = v.get("ref", "")
        words = re.findall(r"[a-zA-Z']+", zo)
        
        for w in words:
            wl = w.lower()
            if wl in particle_info:
                particle_freq[wl] += 1
                if len(particle_examples[wl]) < 3:
                    particle_examples[wl].append(ref)
    
    # Build entries
    for particle, info in particle_info.items():
        entry = {
            "particle": particle,
            "position": info["position"],
            "function": info["function"],
            "meaning": info["meaning"],
            "english_equivalent": info["english"],
            "environment": f"Used in {info['function']} context",
            "examples": particle_examples.get(particle, []),
            "frequency": particle_freq.get(particle, 0)
        }
        particles.append(entry)
    
    return particles

# ══════════════════════════════════════════════════════════════════════
# BOOK SUMMARIES
# ══════════════════════════════════════════════════════════════════════
def build_book_summaries(verses: list, d: dict) -> list:
    """Build summary for each book."""
    summaries = []
    
    # Group by book
    book_verses = defaultdict(list)
    for v in verses:
        book = v.get("book", "")
        if book:
            book_verses[book].append(v)
    
    for book_code, (name, chapters, genre) in BOOK_INFO.items():
        bv = book_verses.get(book_code, [])
        
        # Count vocabulary
        vocab = Counter()
        for v in bv:
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            words = re.findall(r"[a-zA-Z']+", zo)
            for w in words:
                vocab[w.lower()] += 1
        
        # Get key vocabulary (top 10)
        key_vocab = [w for w, _ in vocab.most_common(10)]
        
        # Key patterns
        key_patterns = []
        for v in bv[:5]:  # Sample first 5 verses
            zo = v.get("zo_tedim2010") or v.get("zo_tdb77") or ""
            if "ding" in zo:
                key_patterns.append("future tense (ding)")
            if "ciangin" in zo:
                key_patterns.append("past tense (ciangin)")
            if "hiam" in zo:
                key_patterns.append("question (hiam)")
            if "lo" in zo:
                key_patterns.append("negation (lo)")
        
        entry = {
            "book": book_code,
            "book_name": name,
            "chapters": chapters,
            "verses": len(bv),
            "genre": genre,
            "register": "formal" if genre in ["law", "prophecy", "epistle"] else "informal",
            "key_vocabulary": key_vocab,
            "key_patterns": list(set(key_patterns)),
            "unique_expressions": [],
            "notes": f"Genre: {genre}"
        }
        summaries.append(entry)
    
    return summaries

# ══════════════════════════════════════════════════════════════════════
# VERSION COMPARISON
# ══════════════════════════════════════════════════════════════════════
def build_version_comparison(verses: list) -> list:
    """Compare TDB77 vs Tedim2010 versions."""
    comparisons = []
    
    # Group by book
    book_verses = defaultdict(list)
    for v in verses:
        book = v.get("book", "")
        if book:
            book_verses[book].append(v)
    
    for book_code in BOOK_INFO:
        bv = book_verses.get(book_code, [])
        total = len(bv)
        
        # Count differences
        word_changes = 0
        grammar_changes = 0
        orthography_changes = 0
        examples = []
        
        for v in bv:
            tdb77 = v.get("zo_tdb77", "")
            tedim2010 = v.get("zo_tedim2010", "")
            
            if tdb77 and tedim2010 and tdb77 != tedim2010:
                # Simple difference counting
                tdb77_words = set(re.findall(r"[a-zA-Z']+", tdb77.lower()))
                tedim_words = set(re.findall(r"[a-zA-Z']+", tedim2010.lower()))
                
                if tdb77_words != tedim_words:
                    word_changes += 1
                    if len(examples) < 3:
                        examples.append({
                            "ref": v.get("ref", ""),
                            "tdb77": tdb77[:100],
                            "tedim2010": tedim2010[:100]
                        })
                
                # Check for grammar differences (simple heuristic)
                if len(tdb77_words) != len(tedim_words):
                    grammar_changes += 1
                
                # Check for orthography differences (same words, different spelling)
                if tdb77_words == tedim_words:
                    orthography_changes += 1
        
        entry = {
            "book": book_code,
            "total_verses": total,
            "verses_differ": word_changes + grammar_changes + orthography_changes,
            "word_changes": word_changes,
            "grammar_changes": grammar_changes,
            "orthography_changes": orthography_changes,
            "examples": examples
        }
        comparisons.append(entry)
    
    return comparisons

# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build Full Knowledge Base")
    parser.add_argument("--version-only", action="store_true",
                       help="Only build version comparison")
    args = parser.parse_args()
    
    print("Loading corpus...")
    verses = load_corpus()
    print(f"Loaded {len(verses)} verses")
    
    print("Loading dictionary...")
    d = load_dict()
    print(f"Loaded {len(d)} dictionary entries")
    
    KB_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.version_only:
        # Version comparison only
        print("\nBuilding version comparison...")
        vc = build_version_comparison(verses)
        out = KB_DIR / "version_comparison_v1.jsonl"
        with open(out, "w") as f:
            for entry in vc:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"✅ Written {len(vc)} entries to {out}")
        return
    
    # Full knowledge base
    print("\nBuilding grammar patterns...")
    gp = extract_grammar_patterns(verses, d)
    out = KB_DIR / "grammar_patterns_v1.jsonl"
    with open(out, "w") as f:
        for entry in gp:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ Written {len(gp)} grammar patterns")
    
    print("\nBuilding verb database...")
    vb = build_verb_database(verses, d)
    out = KB_DIR / "verb_database_v1.jsonl"
    with open(out, "w") as f:
        for entry in vb:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ Written {len(vb)} verbs")
    
    print("\nBuilding particle database...")
    pb = build_particle_database(verses, d)
    out = KB_DIR / "particle_database_v1.jsonl"
    with open(out, "w") as f:
        for entry in pb:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ Written {len(pb)} particles")
    
    print("\nBuilding book summaries...")
    bs = build_book_summaries(verses, d)
    out = KB_DIR / "book_summaries_v1.jsonl"
    with open(out, "w") as f:
        for entry in bs:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ Written {len(bs)} book summaries")
    
    print("\nBuilding version comparison...")
    vc = build_version_comparison(verses)
    out = KB_DIR / "version_comparison_v1.jsonl"
    with open(out, "w") as f:
        for entry in vc:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ Written {len(vc)} version comparisons")
    
    print("\n" + "="*50)
    print("✅ Knowledge Base Complete!")
    print("="*50)

if __name__ == "__main__":
    main()
