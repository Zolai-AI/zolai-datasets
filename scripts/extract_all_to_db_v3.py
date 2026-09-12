#!/usr/bin/env python3
"""
Comprehensive data extraction from ALL authoritative sources to DB.
"""

import sqlite3
import json
import re
from pathlib import Path

DB_PATH = Path("data/zolai.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables(conn):
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai TEXT NOT NULL,
            english TEXT,
            myanmar TEXT,
            pos TEXT,
            tone_category TEXT,
            meaning_t1 TEXT,
            meaning_t3 TEXT,
            meaning_t4 TEXT,
            is_compound INTEGER DEFAULT 0,
            compound_parts TEXT,
            root_word TEXT,
            derivation TEXT,
            register TEXT,
            frequency_bible INTEGER DEFAULT 0,
            frequency_corpus INTEGER DEFAULT 0,
            frequency_songs INTEGER DEFAULT 0,
            bible_books TEXT,
            example_zo TEXT,
            example_en TEXT,
            source_priority INTEGER DEFAULT 999,
            source_category TEXT,
            source_file TEXT,
            confidence REAL DEFAULT 1.0,
            zvs_compliant INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(zolai, source_category, source_file)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_grammar_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT,
            pattern_name TEXT,
            pattern_text TEXT,
            structure TEXT,
            zolai_example TEXT,
            english_translation TEXT,
            morpheme_breakdown TEXT,
            tone_pattern TEXT,
            pattern_type TEXT,
            tense TEXT,
            aspect TEXT,
            negation_type TEXT,
            question_type TEXT,
            agreement TEXT,
            ergative INTEGER DEFAULT 0,
            source_category TEXT,
            source_file TEXT,
            source_line INTEGER,
            frequency INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_bible_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT,
            book_name TEXT,
            chapter INTEGER,
            verse INTEGER,
            zolai TEXT,
            english TEXT,
            myanmar_text TEXT,
            verse_hash TEXT,
            morpheme_analysis TEXT,
            grammar_tags TEXT,
            tone_analysis TEXT,
            compounds_found TEXT,
            rare_words TEXT,
            source_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_proverbs_idioms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai TEXT NOT NULL,
            english_translation TEXT,
            literal_translation TEXT,
            morpheme_breakdown TEXT,
            category TEXT,
            theme TEXT,
            cultural_context TEXT,
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_tone_sandhi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_number TEXT,
            rule_name TEXT,
            underlying_pattern TEXT,
            surface_pattern TEXT,
            condition TEXT,
            examples TEXT,
            domain TEXT,
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_word_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            book_code TEXT,
            frequency INTEGER DEFAULT 0,
            meanings TEXT,
            co_occurring TEXT,
            contexts TEXT,
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_vocab_zolai ON zolai_vocabulary(zolai)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_english ON zolai_vocabulary(english)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_source ON zolai_vocabulary(source_category)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_compound ON zolai_vocabulary(is_compound)",
        "CREATE INDEX IF NOT EXISTS idx_grammar_type ON zolai_grammar_patterns(pattern_type)",
        "CREATE INDEX IF NOT EXISTS idx_bible_ref ON zolai_bible_analysis(book_code, chapter, verse)",
        "CREATE INDEX IF NOT EXISTS idx_tone_word ON zolai_tone_sandhi(underlying_pattern)",
        "CREATE INDEX IF NOT EXISTS idx_usage_word ON zolai_word_usage(word)",
        "CREATE INDEX IF NOT EXISTS idx_usage_book ON zolai_word_usage(book_code)",
    ]:
        c.execute(idx)
    
    conn.commit()

def clean_field(val):
    """Clean a field value."""
    if val is None:
        return ""
    if isinstance(val, list):
        return " ".join(str(v) for v in val)
    return str(val).strip()

def load_dictionary_to_vocab(conn):
    c = conn.cursor()
    
    dict_files = [
        ("data/dictionary/processed/dict_zo_en_master_v1.jsonl", "dictionary", 10),
        ("data/dictionary/processed/dict_bible_combined_v1.jsonl", "bible", 20),
        ("data/dictionary/processed/dict_dalsuum_merged.jsonl", "reference", 30),
        ("data/dictionary/processed/dict_canonical_clean.jsonl", "canonical", 15),
    ]
    
    total = 0
    for filepath, category, priority in dict_files:
        if not Path(filepath).exists():
            print(f"  Missing: {filepath}")
            continue
        print(f"  Loading {filepath}...")
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    zolai = clean_field(entry.get('zolai', ''))
                    english = clean_field(entry.get('english_clean', entry.get('english', '')))
                    myanmar = clean_field(entry.get('myanmar', ''))
                    pos = clean_field(entry.get('pos', ''))
                    
                    if not zolai or not english:
                        continue
                    
                    # Skip non-Zolai entries
                    if not re.match(r'^[a-zA-Z\s\-]+$', zolai):
                        continue
                    
                    c.execute("""
                        INSERT OR IGNORE INTO zolai_vocabulary 
                        (zolai, english, myanmar, pos, source_category, source_file, source_priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (zolai, english, myanmar, pos, category, Path(filepath).name, priority))
                    if c.rowcount > 0:
                        total += 1
                except json.JSONDecodeError:
                    continue
    
    conn.commit()
    print(f"  Dictionary vocab loaded: {total}")
    return total

def load_bible_analysis(conn):
    c = conn.cursor()
    
    print("  Loading Bible verses...")
    rows = c.execute("""
        SELECT book_name, chapter, verse, zo_tdb77, en_kJV, myanmar_judson, zo_tedim2010
        FROM bible_verses
        WHERE zo_tdb77 IS NOT NULL AND zo_tdb77 != ''
    """).fetchall()
    
    print(f"  Analyzing {len(rows)} Bible verses...")
    
    known_compounds = {
        'vantung': ['van', 'tung'],
        'leitung': ['lei', 'tung'],
        'laisiangtho': ['lai', 'siang', 'tho'],
        'pasian': ['pa', 'sian'],
        'nuntakna': ['nun', 'tak', 'na'],
        'suahtakna': ['suah', 'tak', 'na'],
        'hehpihna': ['heh', 'pih', 'na'],
        'lungdam': ['lung', 'dam'],
        'guahzu': ['guah', 'zu'],
        'khempeuh': ['khem', 'peuh'],
        'khuapi': ['khua', 'pi'],
        'singgui': ['sing', 'gui'],
        'thagui': ['tha', 'gui'],
        'guihna': ['gui', 'hna'],
    }
    
    total = 0
    for row in rows:
        book_name, chapter, verse, zo_tdb77, en_kJV, myanmar, zo_tedim2010 = row
        
        zolai = zo_tdb77 or zo_tedim2010
        if not zolai:
            continue
            
        words = zolai.split()
        compounds = []
        
        for word in words:
            clean = re.sub(r'[^\w]', '', word.lower())
            if clean in known_compounds:
                compounds.append({'word': clean, 'parts': known_compounds[clean]})
        
        verse_hash = f"{book_name}_{chapter}_{verse}"
        
        c.execute("""
            INSERT OR IGNORE INTO zolai_bible_analysis 
            (book_code, book_name, chapter, verse, zolai, english, 
             myanmar_text, verse_hash, compounds_found, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (book_name[:3].upper(), book_name, chapter, verse, zolai, en_kJV, 
              myanmar, verse_hash, json.dumps(compounds), 'TDB77'))
        
        if c.rowcount > 0:
            total += 1
    
    conn.commit()
    print(f"  Bible analysis loaded: {total}")
    return total

def load_word_usage_from_bible(conn):
    c = conn.cursor()
    
    print("  Extracting word usage per book...")
    
    rows = c.execute("""
        SELECT book_name, chapter, verse, zo_tdb77
        FROM bible_verses
        WHERE zo_tdb77 IS NOT NULL AND zo_tdb77 != ''
    """).fetchall()
    
    book_word_counts = {}
    
    for book_name, chapter, verse, zo_tdb77 in rows:
        book_code = book_name[:3].upper()
        words = zo_tdb77.split()
        
        for word in words:
            clean = re.sub(r'[^\w]', '', word.lower())
            if len(clean) < 2:
                continue
            
            key = (book_code, clean)
            book_word_counts[key] = book_word_counts.get(key, 0) + 1
    
    total = 0
    for (book_code, word), freq in book_word_counts.items():
        c.execute("""
            INSERT OR IGNORE INTO zolai_word_usage 
            (word, book_code, frequency, meanings, source_category, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (word, book_code, freq, json.dumps({}), 'bible', 'bible_verses'))
        if c.rowcount > 0:
            total += 1
    
    conn.commit()
    print(f"  Word usage loaded: {total}")
    return total

def load_tone_sandhi_rules(conn):
    c = conn.cursor()
    
    rules = [
        ("01", "T1 → T2 / — T3", "T1+T3", "T2+T3", "T1 before T3 becomes T2"),
        ("02", "T1 → T4 / — T3", "T1+T3", "T4+T3", "Exception: T1 before T3 becomes T4"),
        ("03", "T4 → T2 / T1 —", "T1+T4", "T1+T2", "T4 after T1 becomes T2"),
        ("04", "T1 → T2 / — T4", "T1+T4", "T2+T2", "T1 before T4 becomes T2"),
        ("05", "T3 → T2 / — T1", "T3+T1", "T2+T1", "T3 before T1 becomes T2"),
        ("06", "T3 → T2 / — T3", "T3+T3", "T2+T3", "T3 before T3 becomes T2"),
        ("07", "T4 → T2 / T3 —", "T3+T4", "T3+T2", "T4 after T3 becomes T2"),
        ("08", "T3 → T2 / — T4", "T3+T4", "T2+T2", "T3 before T4 becomes T2"),
        ("09", "T4 → T4 / — T1", "T4+T1", "T4+T1", "T4 before T1 unchanged"),
        ("10", "T4 → T4 / — T3", "T4+T3", "T4+T3", "T4 before T3 unchanged"),
        ("11", "T4 → T4 / — T4", "T4+T4", "T4+T4", "T4 before T4 unchanged"),
        ("12", "T1 → T2 / T1 — T4", "T1+T1+T4", "T1+T2+T4", "Trisyllabic"),
        ("13", "T1 → T2 / → T1", "T1+T1+T4", "T2+T1+T2", "Trisyllabic"),
        ("14", "T4 → T2 / T1 —", "T1+T4+T4", "T1+T2+T4", "Trisyllabic"),
        ("15", "T1 → T2 / T3 —", "T3+T1+T3", "T3+T2+T3", "Trisyllabic"),
        ("16", "T3 → T2 / T3 —", "T3+T3+T3", "T3+T2+T3", "Trisyllabic"),
        ("17", "T3 → T2 / T3 —", "T3+T3+T4", "T3+T2+T2", "Trisyllabic"),
        ("18", "T4 → T2 / T3 —", "T3+T4+T3", "T3+T2+T3", "Trisyllabic"),
        ("19", "T4 → T4 / T4 —", "T4+T4+T4", "T4+T4+T4", "Trisyllabic"),
    ]
    
    for num, name, underlying, surface, cond in rules:
        c.execute("""
            INSERT OR IGNORE INTO zolai_tone_sandhi 
            (rule_number, rule_name, underlying_pattern, surface_pattern, condition, domain, source_category, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (num, name, underlying, surface, cond, 'toponyms/general', 'reference', 'lesson_02_Tone_Sandhi.md'))
    
    conn.commit()
    print(f"  Tone sandhi rules loaded: {len(rules)}")
    return len(rules)

def load_proverbs(conn):
    c = conn.cursor()
    
    if c.execute("SELECT COUNT(*) FROM proverbs").fetchone()[0] == 0:
        return 0
    
    rows = c.execute("SELECT zolai, english, category FROM proverbs LIMIT 5000").fetchall()
    total = 0
    for zolai, english, cat in rows:
        if zolai and english:
            c.execute("""
                INSERT OR IGNORE INTO zolai_proverbs_idioms 
                (zolai, english_translation, category, source_category, source_file)
                VALUES (?, ?, ?, ?, ?)
            """, (zolai, english, cat or 'proverb', 'bible', 'proverbs'))
            if c.rowcount > 0:
                total += 1
    conn.commit()
    print(f"  Bible proverbs loaded: {total}")
    return total

def extract_wiki_grammar(conn):
    c = conn.cursor()
    
    grammar_files = list(Path("zolai-wiki/grammar").glob("*.md"))
    total = 0
    
    for f in grammar_files:
        if f.name in ['README.md', 'tone_system.md']:
            continue
        text = f.read_text(encoding='utf-8', errors='ignore')
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '|' in line and not line.strip().startswith('---'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    zolai_ex = parts[1] if len(parts) > 1 else ''
                    eng_ex = parts[2] if len(parts) > 2 else ''
                    p_type = parts[3] if len(parts) > 3 else ''
                    
                    if zolai_ex and eng_ex and len(zolai_ex) > 3:
                        c.execute("""
                            INSERT INTO zolai_grammar_patterns 
                            (zolai_example, english_translation, pattern_type, 
                             source_category, source_file, source_line)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (zolai_ex, eng_ex, p_type, 'wiki', f.name, i))
                        total += 1
    
    conn.commit()
    print(f"  Wiki grammar patterns: {total}")
    return total

def add_tone_vocab(conn):
    c = conn.cursor()
    
    tone_vocab = [
        ('khem', 'lie/deceive', 'thin/weak after illness', None, 'VERB', 'T1/T3'),
        ('nam', 'smell', 'odoriferous', None, 'VERB', 'T1/T3'),
        ('zu', 'alcohol/distillate', None, 'rain (with guah-)', 'NOUN', 'T1/T4'),
        ('ta', 'completive/realized aspect', 'beginning', None, 'PART', 'T1/T3'),
        ('ci', 'say/speak', None, None, 'VERB', 'T1'),
        ('ne', 'eat/drink', None, None, 'VERB', 'T1'),
        ('pai', 'go/move', None, None, 'VERB', 'T1'),
        ('om', 'exist/stay', None, None, 'VERB', 'T1'),
    ]
    
    for zolai, t1, t3, t4, pos, tones in tone_vocab:
        c.execute("""
            INSERT OR IGNORE INTO zolai_vocabulary 
            (zolai, english, meaning_t1, meaning_t3, meaning_t4, pos, tone_category, source_category, source_file, source_priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (zolai, t1, t1, t3, t4, pos, tones, 'reference', 'Zolai_Sinna_lesson_16', 5))
    
    conn.commit()
    print(f"  Tone vocabulary added")

def main():
    print("=== Comprehensive Data Extraction to DB (v3) ===\n")
    
    conn = get_db()
    ensure_tables(conn)
    
    print("1. Loading dictionary...")
    load_dictionary_to_vocab(conn)
    
    print("2. Loading Bible analysis...")
    load_bible_analysis(conn)
    
    print("3. Extracting word usage per book...")
    load_word_usage_from_bible(conn)
    
    print("4. Loading tone sandhi rules...")
    load_tone_sandhi_rules(conn)
    
    print("5. Loading proverbs...")
    load_proverbs(conn)
    
    print("6. Extracting wiki grammar...")
    extract_wiki_grammar(conn)
    
    print("7. Adding tone vocabulary...")
    add_tone_vocab(conn)
    
    print("\n=== Final Database Stats ===")
    tables = ['zolai_vocabulary', 'zolai_grammar_patterns', 'zolai_bible_analysis', 
              'zolai_proverbs_idioms', 'zolai_tone_sandhi', 'zolai_word_usage']
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count}")
    
    conn.close()
    print("\n✅ Complete!")

if __name__ == "__main__":
    main()
