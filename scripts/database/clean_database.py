#!/usr/bin/env python3
"""
Clean and normalize the dictionary database.

1. Extract clean headwords from JSONL file
2. Update database headword fields
3. Set proper entry versions
4. Mark ZVS compliance status
"""

import sqlite3
import json
import sys
import os
import re

# Add bible dir for gemini_cookies
SCRIPT_DIR = os.path.dirname(os.path.abspath('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client
import asyncio


def extract_clean_headword(zolai_text):
    """Extract just the headword from Zolai text."""
    if not zolai_text:
        return ''
    
    text = zolai_text.strip().strip('"').strip("'").strip()
    
    # If it's just a single word, return it
    if text and not text.startswith('"') and len(text.split()) == 1:
        return text
    
    # If it starts with quotes, extract the inner content
    if text.startswith('"') or text.startswith("'"):
        text = text[1:-1] if len(text) > 1 else text
    
    # Take first sentence/phrase
    sentences = re.split(r'[.!?]', text)
    first_sentence = sentences[0] if sentences else text
    
    # Extract headword (first word or first phrase before complex definitions)
    words = first_sentence.split()
    if words:
        headword = ' '.join(words[:2])
        headword = re.sub(r'\s+\([^)]*\)\s*', ' ', headword)
        headword = headword.strip()
        if headword and len(headword) > 0:
            return headword
    
    return text[:50]


async def update_database_from_jsonl():
    """Update the database with clean headwords from JSONL."""
    conn = sqlite3.connect('data/zolai.db')
    cur = conn.cursor()
    
    # Load all entries from JSONL
    with open('data/dictionary/processed/dict_zo_en_verified_v1.jsonl', encoding='utf-8') as f:
        entries = []
        for line in f:
            if line.strip():
                entry = json.loads(line)
                entries.append(entry)
    
    total = len(entries)
    print(f"Loading {total} entries from JSONL...")
    
    updated = 0
    skipped = 0
    
    for i, entry in enumerate(entries):
        zolai = entry.get('zolai', '') or entry.get('headword', '') or ''
        # Use the rowid from JSONL if available, otherwise find by matching
        entry_id = entry.get('id', '') or entry.get('id_entry', '') or ''
        
        if not zolai:
            skipped += 1
            continue
        
        clean_headword = extract_clean_headword(zolai)
        
        if not clean_headword:
            skipped += 1
            continue
        
        # Try to find the DB entry by matching the original headword, then update
        # Use a more robust approach: find entries where headword matches or is empty
        # And update them using their internal ID
        
        # Try to get the ID from the entry
        if entry_id and entry_id.isdigit():
            try:
                cur.execute(
                    "UPDATE dictionary SET zolai=?, entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
                    (clean_headword, 
                     entry.get('entry_version', 'v1.0'),
                     entry.get('update_remarks', ''),
                     entry.get('update_description', ''),
                     entry.get('zvs_compliance_status', 'pending'),
                     int(entry_id))
                )
                updated += 1
            except Exception as e:
                print(f"Error updating ID {entry_id}: {e}")
                skipped += 1
        else:
            # Alternative: find entries where the current headword matches the zolai from JSONL
            # or where headword is empty/needs updating
            try:
                # Search for entries where headword is empty or matches pattern
                cur.execute("SELECT id FROM dictionary WHERE zolai=? OR headword=''", (zolai.strip().strip('"').strip("'").strip()[:50],))
                matches = cur.fetchall()
                if matches:
                    db_id = matches[0][0]
                    cur.execute(
                        "UPDATE dictionary SET zolai=?, entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
                        (clean_headword, 
                         entry.get('entry_version', 'v1.0'),
                         entry.get('update_remarks', ''),
                         entry.get('update_description', ''),
                         entry.get('zvs_compliance_status', 'pending'),
                         db_id)
                    )
                    updated += 1
                else:
                    # Last resort: just try to update by creating a new approach
                    # We'll use the ID from the JSONL if we can find a mapping
                    skipped += 1
            except Exception as e:
                print(f"Error in alternative update: {e}")
                skipped += 1
        
        if (i + 1) % 10000 == 0:
            conn.commit()
            print(f"Progress: {i+1}/{total} entries done (updated={updated}, skipped={skipped})")
    
    conn.commit()
    
    print(f"\n=== DONE ===")
    print(f"Total entries: {total}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    
    # Verify - check first 5 headwords
    cur.execute("SELECT id, headword FROM dictionary LIMIT 5")
    rows = cur.fetchall()
    print("\nVerified - first 5 entries:")
    for row in rows:
        print(f"  ID={row[0]}, headword='{row[1][:60] if row[1] else None}' (len={len(row[1]) if row[1] else 0})")
    
    conn.close()


async def main():
    print("=== DATABASE CLEANUP AND HEADWORD EXTRACTION ===\n")
    await update_database_from_jsonl()


if __name__ == "__main__":
    asyncio.run(main())
