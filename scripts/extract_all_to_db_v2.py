#!/usr/bin/env python3
"""
Comprehensive data extraction from ALL authoritative sources to DB.
Uses:
- data/dictionary/ - authoritative Zolai-English dictionary (93K entries)
- data/bible/ - Bible parallel corpus (31K verses)
- data/reference/ - reference books (grammar, literature)
- zolai-wiki/ - structured wiki content
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Dict, List

DB_PATH = Path("data/zolai.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables(conn):
    c = conn.cursor()
    
    # Master vocabulary - single source of truth
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai TEXT NOT NULL,
            english TEXT,
            myanmar TEXT,
            pos TEXT,
            tone_category TEXT,  -- T1, T3, T4
            meaning_t1 TEXT,     -- meaning at T1 (high)
            meaning_t3 TEXT,     -- meaning at T3 (low)
            meaning_t4 TEXT,     -- meaning at T4 (creaky)
            is_compound INTEGER DEFAULT 0,
            compound_parts TEXT, -- JSON array
            root_word TEXT,      -- base root
            derivation TEXT,     -- how derived
            register TEXT,       -- formal, colloquial, biblical, poetic
            frequency_bible INTEGER DEFAULT 0,
            frequency_corpus INTEGER DEFAULT 0,
            frequency_songs INTEGER DEFAULT 0,
            bible_books TEXT,    -- JSON array of books where appears
            example_zo TEXT,     -- Zolai example
            example_en TEXT,     -- English example
            source_priority INTEGER DEFAULT 999,  -- lower = more authoritative
            source_category TEXT,  -- bible, dictionary, reference, wiki, corpus, songs
            source_file TEXT,
            confidence REAL DEFAULT 1.0,
            zvs_compliant INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(zolai, source_category, source_file)
        )
    """)
    
    # Grammar patterns
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_grammar_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT,
            pattern_name TEXT,
            pattern_text TEXT,
            structure TEXT,      -- SOV, SVC, etc.
            zolai_example TEXT,
            english_translation TEXT,
            morpheme_breakdown TEXT,  -- JSON
            tone_pattern TEXT,   -- T1+T3+T4 etc.
            pattern_type TEXT,   -- tense, aspect, negation, question, etc.
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
    
    # Bible verses with full analysis
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_bible_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT,
            book_name TEXT,
            chapter INTEGER,
            verse INTEGER,
            zolai_text TEXT,
            english_text TEXT,
            myanmar_text TEXT,
            verse_hash TEXT,
            morpheme_analysis TEXT,  -- JSON array
            grammar_tags TEXT,       -- JSON array
            tone_analysis TEXT,      -- T1/T3/T4 per word
            compounds_found TEXT,    -- JSON array
            rare_words TEXT,         -- JSON array
            source_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Proverbs and idioms
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_proverbs_idioms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai_text TEXT NOT NULL,
            english_translation TEXT,
            literal_translation TEXT,
            morpheme_breakdown TEXT,
            category TEXT,         -- proverb, idiom, saying, metaphor
            theme TEXT,
            cultural_context TEXT,
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tone sandhi rules
    c.execute("""
        CREATE TABLE IF NOT EXISTS zolai_tone_sandhi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_number TEXT,
            rule_name TEXT,
            underlying_pattern TEXT,  -- e.g., "T1+T3"
            surface_pattern TEXT,     -- e.g., "T2+T3"
            condition TEXT,
            examples TEXT,            -- JSON array
            domain TEXT,              -- toponyms, general, etc.
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_vocab_zolai ON zolai_vocabulary(zolai)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_english ON zolai_vocabulary(english)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_source ON zolai_vocabulary(source_category)",
        "CREATE INDEX IF NOT EXISTS idx_vocab_compound ON zolai_vocabulary(is_compound)",
        "CREATE INDEX IF NOT EXISTS idx_grammar_type ON zolai_grammar_patterns(pattern_type)",
        "CREATE INDEX IF NOT EXISTS idx_bible_ref ON zolai_bible_analysis(book_code, chapter, verse)",
        "CREATE INDEX IF NOT EXISTS idx_tone_word ON zolai_tone_sandhi(underlying_pattern)",
    ]:
        c.execute(idx)
    
    conn.commit()

def load_dictionary_to_vocab(conn):
    """Load authoritative dictionary into zolai_vocabulary."""
    c = conn.cursor()
    
    # Load from master dictionary
    dict_files = [
        ("data/dictionary/processed/dict_zo_en_master_v1.jsonl", "dictionary", 10),
        ("data/dictionary/processed/dict_bible_combined_v1.jsonl", "bible", 20),
        ("data/dictionary/processed/dict_dalsuum_merged.jsonl", "reference", 30),
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
                    zolai = entry.get('zolai', '').strip()
                    english = entry.get('english_clean', entry.get('english', '')).strip()
                    myanmar = entry.get('myanmar', '').strip()
                    pos = entry.get('pos', '').strip()
                    
                    if not zolai or not english:
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

def load_bible_verses(conn):
    """Load Bible verses with analysis."""
    c = conn.cursor()
    
    # Check existing bible_verses table
    existing = c.execute("SELECT COUNT(*) FROM bible_verses").fetchone()[0]
    if existing == 0:
        print("  No bible_verses table data")
        return 0
    
    print(f"  Analyzing {existing} Bible verses...")
    
    # Load verses
    rows = c.execute("""
        SELECT book_name, chapter, verse, zolai_text, english_text, myanmar_text
        FROM bible_verses
        WHERE zolai_text IS NOT NULL AND zolai_text != ''
    """).fetchall()
    
    total = 0
    for row in rows:
        book_name, chapter, verse, zolai, english, myanmar = row
        
        # Analyze verse
        words = zolai.split()
        compounds = []
        
        # Find known compounds
        known_compounds = ['vantung', 'leitung', 'laisiangtho', 'pasian', 'nuntakna', 
                          'suahtakna', 'hehpihna', 'lungdam', 'guahzu', 'khempeuh',
                          'khuapi', 'singgui', 'thagui', 'guihna']
        
        for word in words:
            clean = re.sub(r'[^\w]', '', word.lower())
            if clean in known_compounds:
                compounds.append(clean)
        
        verse_hash = f"{book_name}_{chapter}_{verse}"
        
        c.execute("""
            INSERT OR IGNORE INTO zolai_bible_analysis 
            (book_code, book_name, chapter, verse, zolai_text, english_text, 
             myanmar_text, verse_hash, compounds_found, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (book_name[:3].upper(), book_name, chapter, verse, zolai, english, 
              myanmar, verse_hash, json.dumps(compounds), 'TDB77'))
        
        if c.rowcount > 0:
            total += 1
    
    conn.commit()
    print(f"  Bible analysis loaded: {total}")
    return total

def load_tone_sandhi_rules(conn):
    """Load tone sandhi rules from reference document."""
    c = conn.cursor()
    
    tone_file = Path("data/reference/grammar/lesson_02_Tone_Sandhi_Tedim_Zomi_Toponyms.md")
    if not tone_file.exists():
        print("  Tone sandhi file not found")
        return 0
    
    text = tone_file.read_text(encoding='utf-8', errors='ignore')
    
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
        """, (num, name, underlying, surface, cond, 'toponyms/general', 'reference', tone_file.name))
    
    conn.commit()
    print(f"  Tone sandhi rules loaded: {len(rules)}")
    return len(rules)

def load_proverbs(conn):
    """Load proverbs from Bible and reference files."""
    c = conn.cursor()
    
    # From proverbs table
    if c.execute("SELECT COUNT(*) FROM proverbs").fetchone()[0] > 0:
        rows = c.execute("SELECT zolai_text, english_text, category FROM proverbs LIMIT 5000").fetchall()
        total = 0
        for zolai, english, cat in rows:
            if zolai and english:
                c.execute("""
                    INSERT OR IGNORE INTO zolai_proverbs_idioms 
                    (zolai_text, english_translation, category, source_category, source_file)
                    VALUES (?, ?, ?, ?, ?)
                """, (zolai, english, cat or 'proverb', 'bible', 'proverbs'))
                if c.rowcount > 0:
                    total += 1
        conn.commit()
        print(f"  Bible proverbs loaded: {total}")
        return total
    return 0

def extract_from_wiki_grammar(conn):
    """Extract grammar patterns from wiki grammar files."""
    c = conn.cursor()
    
    grammar_files = list(Path("zolai-wiki/grammar").glob("*.md"))
    total = 0
    
    for f in grammar_files:
        if f.name in ['README.md', 'tone_system.md']:
            continue
        text = f.read_text(encoding='utf-8', errors='ignore')
        
        # Extract patterns from tables
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '|' in line and not line.strip().startswith('---'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    # Look for Zolai|English|Pattern type
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

def main():
    print("=== Comprehensive Data Extraction to DB ===\n")
    
    conn = get_db()
    ensure_tables(conn)
    
    # 1. Load dictionary (most authoritative)
    print("1. Loading dictionary...")
    load_dictionary_to_vocab(conn)
    
    # 2. Load Bible analysis
    print("2. Loading Bible analysis...")
    load_bible_verses(conn)
    
    # 3. Load tone sandhi rules
    print("3. Loading tone sandhi rules...")
    load_tone_sandhi_rules(conn)
    
    # 4. Load proverbs
    print("4. Loading proverbs...")
    load_proverbs(conn)
    
    # 5. Extract wiki grammar
    print("5. Extracting wiki grammar...")
    extract_from_wiki_grammar(conn)
    
    # Final stats
    print("\n=== Final Database Stats ===")
    tables = ['vocabulary', 'grammar_patterns', 'bible_analysis', 
              'proverbs', 'tone_sandhi']
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count}")
    
    conn.close()
    print("\n✅ Complete!")

if __name__ == "__main__":
    main()
