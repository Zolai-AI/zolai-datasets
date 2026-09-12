#!/usr/bin/env python3
"""
Regenerate dictionary database from JSONL with proper headwords and ZVS tracking.

This script:
1. Reads dict_zo_en_verified_v1.jsonl
2. Extracts clean headwords
3. Rebuilds the SQLite database with proper structure
4. Adds version tracking and ZVS compliance status
"""

import sqlite3
import json
import sys
import os
import re
import shutil

# Add bible dir for gemini_cookies
SCRIPT_DIR = os.path.dirname(os.path.abspath('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client
import asyncio


def extract_clean_headword(zolai_text):
    """Extract just the headword from Zolai dictionary entry text."""
    if not zolai_text:
        return ''
    
    text = zolai_text.strip().strip('"').strip("'").strip()
    
    # If it's just a single word with no definitions, return it
    if text and not text.startswith('"') and ' ' not in text and '\n' not in text:
        return text
    
    # If it starts with quotes, extract the inner content
    if text.startswith('"') or text.startswith("'"):
        # Find the first word after the opening quote
        inner = text[1:].strip()
        # Take first word/phrase before any period or parenthesis
        first_part = re.split(r'[.!?(]', inner)[0].strip()
        if first_part:
            return first_part
    
    # Take first sentence/phrase - headword is typically at the start
    sentences = re.split(r'[.!?]', text)
    first_sentence = sentences[0] if sentences else text
    
    # Extract headword (first 1-2 words, excluding definitional words)
    words = first_sentence.split()
    if not words:
        return ''
    
    # Filter out common definitional words/phrases
    filter_words = ['n.', 'adj.', 'v.', 'pron.', 'adv.', 'prep.', 'conj.', 
                    'particle', 'auxiliary', 'copula', 'marker', 'prefix', 'suffix']
    
    meaningful_words = []
    for w in words:
        # Skip if it's a short grammatical marker
        if len(w) <= 1:
            continue
        # Skip if it looks like a definition label
        if w.lower() in filter_words:
            continue
        meaningful_words.append(w)
        if len(meaningful_words) >= 2:  # Take at most 2 meaningful words
            break
    
    if meaningful_words:
        headword = ' '.join(meaningful_words)
        # Clean any trailing punctuation
        headword = re.sub(r'[.!?,;]$', '', headword)
        headword = headword.strip()
        if headword and len(headword) > 0:
            return headword
    
    # Fallback: return first word only
    return words[0] if words else ''


async def rebuild_database():
    """Rebuild the SQLite database from JSONL with proper structure."""
    
    # Backup existing database
    backup_path = 'data/zolai.db.bak'
    original_path = 'data/zolai.db'
    
    if os.path.exists(original_path):
        shutil.copy2(original_path, backup_path)
        print(f"Backed up existing DB to {backup_path}")
    
    # Remove existing database to rebuild
    if os.path.exists(original_path):
        os.remove(original_path)
    
    # Create fresh database with proper schema
    conn = sqlite3.connect(original_path)
    cur = conn.cursor()
    
    # Create table with all needed fields including version tracking
    cur.execute('''
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headword TEXT NOT NULL UNIQUE,
            pos TEXT,
            english TEXT,
            sources TEXT,
            raw_json TEXT,
            entry_version TEXT DEFAULT 'v1.0',
            update_remarks TEXT DEFAULT '',
            update_description TEXT DEFAULT '',
            zvs_compliance_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Also create supporting tables
    cur.execute('''
        CREATE TABLE IF NOT EXISTS translation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER,
            translation TEXT,
            FOREIGN KEY (entry_id) REFERENCES entries (id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS provenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER,
            source_file TEXT,
            source_line INTEGER,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (entry_id, source_file)
        )
    ''')
    
    conn.commit()
    
    # Now load entries from JSONL
    with open('data/dictionary/processed/dict_zo_en_verified_v1.jsonl', encoding='utf-8') as f:
        entries = []
        for line_num, line in enumerate(f, 1):
            if line.strip():
                entry = json.loads(line)
                entries.append((line_num, entry))
    
    total = len(entries)
    print(f"Rebuilding database with {total} entries from JSONL...")
    
    updated = 0
    errors = 0
    duplicate_count = 0
    
    for line_num, entry in entries:
        zolai = entry.get('zolai', '') or entry.get('headword', '') or ''
        english = entry.get('english', '') or ''
        sources = entry.get('sources', '') or ''
        raw_json = json.dumps(entry) if isinstance(entry, dict) else ''
        
        if not zolai:
            errors += 1
            if errors <= 5:
                print(f"  Error: No zolai field in entry {line_num}")
            continue
        
        # Extract clean headword
        headword = extract_clean_headword(zolai)
        
        if not headword:
            errors += 1
            continue
        
        # Clean headword for DB storage
        headword_clean = headword.strip().strip('"').strip("'").strip()
        
        # Try to insert, handle duplicates
        try:
            cur.execute(
                '''INSERT INTO dictionary 
                   (headword, pos, english, sources, raw_json, entry_version, 
                    update_remarks, update_description, zvs_compliance_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (headword_clean,
                 entry.get('pos', ''),
                 english[:500] if isinstance(english, str) else str(english)[:500],
                 sources[:200] if isinstance(sources, str) else str(sources)[:200],
                 raw_json,
                 entry.get('entry_version', 'v1.0'),
                 entry.get('update_remarks', ''),
                 entry.get('update_description', ''),
                 entry.get('zvs_compliance_status', 'pending'))
            )
            updated += 1
        except sqlite3.IntegrityError as e:
            # Duplicate headword - skip or handle
            duplicate_count += 1
            if duplicate_count <= 10:
                print(f"  Duplicate headword '{headword_clean}' at entry {line_num}: {e}")
            # Still track it - just skip insert
    
    conn.commit()
    
    # Print summary
    cur.execute("SELECT COUNT(*) FROM dictionary")
    final_count = cur.fetchone()[0]
    
    print(f"\n=== DATABASE REBUILD SUMMARY ===")
    print(f"Total entries from JSONL: {total}")
    print(f"Successfully inserted: {updated}")
    print(f"Duplicates skipped: {duplicate_count}")
    print(f"Errors: {errors}")
    print(f"Final DB count: {final_count}")
    
    # Verify some entries
    cur.execute("SELECT id, headword, entry_version, zvs_compliance_status FROM dictionary LIMIT 10")
    rows = cur.fetchall()
    print(f"\nVerified - first 10 entries:")
    for row in rows:
        print(f"  ID={row[0]}, headword='{row[1][:50] if row[1] else None}', version={row[2]}, status={row[3]}")
    
    # Check ZVS compliance status distribution
    cur.execute("SELECT zvs_compliance_status, COUNT(*) FROM dictionary GROUP BY zvs_compliance_status")
    status_counts = cur.fetchall()
    print(f"\nZVS compliance status distribution:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    
    conn.close()
    return updated


async def main():
    print("=== REGENERATE DICTIONARY DATABASE ===\n")
    await rebuild_database()


if __name__ == "__main__":
    asyncio.run(main())
