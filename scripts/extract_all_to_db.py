#!/usr/bin/env python3
"""
Comprehensive data extraction from ALL sources to DB.
Sources:
- data/reference/ (31 files) - authoritative grammar, literature, genealogy
- zolai-wiki/ (1669 files) - structured wiki content
- data/bible/ (31K verses) - parallel corpus
- data/dictionary/ (93K entries) - Zolai-English dictionary
- data/corpus/ (3M+ sentences) - modern corpus
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

DB_PATH = Path("data/zolai.db")

# Source categories for proper tracking
SOURCE_CATEGORIES = {
    "reference": "Authoritative reference materials",
    "wiki": "Zolai wiki structured content",
    "bible": "Bible parallel corpus (authoritative)",
    "dictionary": "Zolai-English dictionary (authoritative)",
    "corpus": "Modern corpus (paumkim/zomi-dataset)",
    "songs": "Traditional songs",
    "generated": "AI-generated / derived content",
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables(conn):
    """Ensure all needed tables exist."""
    c = conn.cursor()
    
    # Enhanced dictionary with source tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS dictionary_enhanced (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai TEXT NOT NULL,
            english TEXT,
            english_clean TEXT,
            myanmar TEXT,
            pos TEXT,
            tone_notes TEXT,
            source_category TEXT,
            source_file TEXT,
            confidence REAL DEFAULT 1.0,
            word_count INTEGER,
            is_compound INTEGER DEFAULT 0,
            compound_parts TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(zolai, source_file)
        )
    """)
    
    # Grammar patterns with full source tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS grammar_patterns_enhanced (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT,
            pattern_text TEXT,
            zolai_example TEXT,
            english_translation TEXT,
            pattern_type TEXT,
            tone_category TEXT,
            source_category TEXT,
            source_file TEXT,
            page_section TEXT,
            frequency INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Vocabulary with full etymology
    c.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary_enhanced (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai TEXT NOT NULL,
            english_meaning TEXT,
            pos TEXT,
            tone_category TEXT,
            etymology TEXT,
            compound_breakdown TEXT,
            register TEXT,
            frequency INTEGER DEFAULT 0,
            bible_frequency INTEGER DEFAULT 0,
            corpus_frequency INTEGER DEFAULT 0,
            source_category TEXT,
            source_file TEXT,
            example_sentences TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tone patterns
    c.execute("""
        CREATE TABLE IF NOT EXISTS tone_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            tone_category TEXT,
            meaning_t1 TEXT,
            meaning_t3 TEXT,
            meaning_t4 TEXT,
            sandhi_rules TEXT,
            source_category TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Proverbs/idioms
    c.execute("""
        CREATE TABLE IF NOT EXISTS proverbs_idioms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zolai_text TEXT NOT NULL,
            english_translation TEXT,
            literal_translation TEXT,
            category TEXT,
            source_category TEXT,
            source_file TEXT,
            cultural_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Bible verses with enhanced metadata
    c.execute("""
        CREATE TABLE IF NOT EXISTS bible_verses_enhanced (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book TEXT,
            chapter INTEGER,
            verse INTEGER,
            zolai_text TEXT,
            english_text TEXT,
            myanmar_text TEXT,
            tone_analysis TEXT,
            grammar_analysis TEXT,
            vocabulary_notes TEXT,
            source_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()

def extract_from_reference_file(filepath: Path) -> Dict:
    """Extract structured data from a reference file."""
    text = filepath.read_text(encoding='utf-8', errors='ignore')
    
    result = {
        'source_file': str(filepath),
        'source_category': 'reference',
        'words': [],
        'patterns': [],
        'proverbs': [],
        'tone_data': [],
        'vocabulary': [],
    }
    
    # Extract Zolai words (sequences of Zolai characters)
    zolai_words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    
    # Look for specific patterns
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Skip very short lines
        if len(line.strip()) < 3:
            continue
            
        # Look for Zolai-English pairs (various formats)
        # Format: "Zolai|English" or "Zolai - English" or "Zolai: English"
        for sep in ['|', '-', ':', '→']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    zolai = parts[0].strip()
                    english = parts[1].strip()
                    if len(zolai) > 1 and len(english) > 1 and zolai.isalpha():
                        result['vocabulary'].append({
                            'zolai': zolai,
                            'english': english,
                            'line_num': i,
                            'context': line.strip()[:200]
                        })
        
        # Look for Bible verse patterns
        verse_match = re.match(r'^(\d+)\s*[:.]\s*(.+)', line.strip())
        if verse_match:
            result['patterns'].append({
                'type': 'verse',
                'verse_num': verse_match.group(1),
                'text': verse_match.group(2),
                'line_num': i
            })
        
        # Look for tone patterns (T1, T2, T3, T4)
        tone_matches = re.findall(r'(T[1-4])\s*[+=]\s*(\w+)', line)
        for tone, word in tone_matches:
            result['tone_data'].append({
                'tone': tone,
                'word': word,
                'context': line.strip()[:200]
            })
    
    return result

def extract_from_wiki_file(filepath: Path) -> Dict:
    """Extract from wiki markdown files."""
    text = filepath.read_text(encoding='utf-8', errors='ignore')
    
    result = {
        'source_file': str(filepath),
        'source_category': 'wiki',
        'vocabulary': [],
        'grammar_rules': [],
        'examples': [],
    }
    
    # Extract from tables, lists, etc.
    lines = text.split('\n')
    for line in lines:
        # Skip empty
        if len(line.strip()) < 3:
            continue
        
        # Table rows with Zolai|English
        if '|' in line and not line.strip().startswith('---'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                # Check if any part looks like Zolai word
                for part in parts:
                    words = re.findall(r'\b[a-zA-Z]{3,}\b', part)
                    for w in words:
                        if w.lower() == w and len(w) > 2:  # lowercase Zolai
                            result['vocabulary'].append({
                                'zolai': w,
                                'context': line.strip()[:200],
                                'source_line': line
                            })
        
        # Bold terms (vocabulary)
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', line)
        for term in bold_matches:
            if len(term) > 2 and term.replace(' ', '').isalpha():
                result['vocabulary'].append({
                    'zolai': term,
                    'context': line.strip()[:200]
                })
    
    return result

def process_all_sources():
    """Process all data sources."""
    conn = get_db()
    ensure_tables(conn)
    c = conn.cursor()
    
    stats = {
        'reference_files': 0,
        'wiki_files': 0,
        'vocab_added': 0,
        'patterns_added': 0,
        'proverbs_added': 0,
        'tone_data_added': 0,
    }
    
    # 1. Process reference files
    print("Processing reference files...")
    ref_files = list(Path("data/reference").rglob("*.md")) + list(Path("data/reference").rglob("*.txt"))
    for f in ref_files:
        if f.is_file():
            data = extract_from_reference_file(f)
            stats['reference_files'] += 1
            
            # Insert vocabulary
            for v in data['vocabulary']:
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO vocabulary_enhanced 
                        (zolai, english_meaning, source_category, source_file, context)
                        VALUES (?, ?, ?, ?, ?)
                    """, (v['zolai'], v.get('english', ''), data['source_category'], 
                          data['source_file'], v.get('context', '')))
                    if c.rowcount > 0:
                        stats['vocab_added'] += 1
                except:
                    pass
            
            # Insert patterns
            for p in data['patterns']:
                try:
                    c.execute("""
                        INSERT INTO grammar_patterns_enhanced 
                        (pattern_text, pattern_type, source_category, source_file)
                        VALUES (?, ?, ?, ?)
                    """, (p.get('text', ''), p.get('type', ''), data['source_category'], data['source_file']))
                    stats['patterns_added'] += 1
                except:
                    pass
            
            # Insert tone data
            for t in data['tone_data']:
                try:
                    c.execute("""
                        INSERT INTO tone_patterns 
                        (word, tone_category, source_category, source_file)
                        VALUES (?, ?, ?, ?)
                    """, (t['word'], t['tone'], data['source_category'], data['source_file']))
                    stats['tone_data_added'] += 1
                except:
                    pass
            
            if stats['reference_files'] % 5 == 0:
                conn.commit()
                print(f"  Processed {stats['reference_files']} reference files...")
    
    # 2. Process wiki files
    print("\nProcessing wiki files...")
    wiki_files = list(Path("zolai-wiki").rglob("*.md"))
    for f in wiki_files:
        if f.is_file() and '.venv' not in str(f) and '.git' not in str(f):
            data = extract_from_wiki_file(f)
            stats['wiki_files'] += 1
            
            for v in data['vocabulary']:
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO vocabulary_enhanced 
                        (zolai, source_category, source_file, context)
                        VALUES (?, ?, ?, ?)
                    """, (v['zolai'], data['source_category'], data['source_file'], v.get('context', '')))
                    if c.rowcount > 0:
                        stats['vocab_added'] += 1
                except:
                    pass
            
            if stats['wiki_files'] % 100 == 0:
                conn.commit()
                print(f"  Processed {stats['wiki_files']} wiki files...")
    
    conn.commit()
    print(f"\n=== Processing Complete ===")
    print(f"Reference files: {stats['reference_files']}")
    print(f"Wiki files: {stats['wiki_files']}")
    print(f"Vocabulary added: {stats['vocab_added']}")
    print(f"Patterns added: {stats['patterns_added']}")
    print(f"Tone data added: {stats['tone_data_added']}")
    
    # Show final counts
    for table in ['vocabulary_enhanced', 'grammar_patterns_enhanced', 'tone_patterns']:
        count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
    
    conn.close()

if __name__ == "__main__":
    process_all_sources()
