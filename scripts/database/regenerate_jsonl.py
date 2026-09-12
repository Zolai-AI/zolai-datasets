#!/usr/bin/env python3
"""
Regenerate dictionary JSONL files from SQLite database.

Reads the master database and outputs clean JSONL files
for the Zolai dictionary system.
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


def extract_headword_from_raw_json(raw_json):
    """Extract the headword from the raw_json JSONB field."""
    try:
        if not raw_json:
            return ''
        rj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        if isinstance(rj, dict):
            # Try multiple fields
            for field in ['headword', 'zolai', 'term', 'word']:
                if rj.get(field):
                    hw = str(rj[field]).strip()
                    hw = hw.strip('"').strip("'").strip()
                    if hw and len(hw) > 0:
                        return hw
            # Fallback: return first meaningful part
            if rj.get('headword'):
                return str(rj['headword']).strip('"').strip("'").strip()
        return ''
    except Exception as e:
        print(f"Error extracting headword: {e}")
        return ''


async def regenerate_verified_dict():
    """Regenerate dict_zo_en_verified_v1.jsonl from database."""
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    
    # Get all entries with their fields
    cur.execute("SELECT id, headword, pos, english, sources, raw_json, entry_version, update_remarks, update_description, zvs_compliance_status FROM entries")
    all_entries = cur.fetchall()
    
    total = len(all_entries)
    print(f"Regenerating dict_zo_en_verified_v1.jsonl from {total} entries...")
    
    output_entries = []
    skipped = 0
    
    for i, entry in enumerate(all_entries):
        entry_id, headword, pos, english, sources, raw_json, version, remarks, description, zvs_status = entry
        
        if not headword:
            skipped += 1
            continue
        
        # Clean the headword and English translations
        headword_clean = headword.strip().strip('"').strip("'").strip()
        english_clean = english.strip() if english else ''
        sources_clean = sources.strip() if sources else ''
        version_clean = version.strip() if version else 'v1.0'
        remarks_clean = remarks.strip() if remarks else ''
        description_clean = description.strip() if description else ''
        zvs_status_clean = zvs_status.strip() if zvs_status else 'pending'
        
        # Build the JSONL entry matching the original format
        # The original dict_zo_en_verified_v1.jsonl has: zolai, english, source, pos, etc.
        entry_dict = {
            'zolai': headword_clean,
            'english': english_clean if english_clean else [],
            'source': sources_clean if sources_clean else 'database_rebuilt',
            'pos': pos.strip() if pos else '',
            'entry_version': version_clean,
            'update_remarks': remarks_clean,
            'update_description': description_clean,
            'zvs_compliance_status': zvs_status_clean
        }
        
        # Add additional fields if they have values
        if raw_json:
            try:
                rj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                if isinstance(rj, dict):
                    # Preserve any additional fields from original
                    for key in ['sources', 'raw_json', 'notes', 'etymology']:
                        if key in rj and rj[key]:
                            entry_dict[key] = rj[key]
            except:
                pass
        
        output_entries.append(json.dumps(entry_dict, ensure_ascii=False))
        
        if (i + 1) % 10000 == 0:
            print(f"  Progress: {i+1}/{total} entries processed (skipped={skipped})")
    
    conn.close()
    
    # Write the output JSONL file
    output_path = 'data/dictionary/processed/dict_zo_en_verified_v1.jsonl'
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in output_entries:
            f.write(line + '\n')
    
    print(f"\\n=== regenerated: {output_path} ===")
    print(f"Total entries: {total}")
    print(f"Successfully written: {len(output_entries)}")
    print(f"Skipped (no headword): {skipped}")


async def regenerate_master_dict():
    """Regenerate dict_zo_en_master_v1.jsonl from database."""
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    
    cur.execute("SELECT id, headword, pos, english, sources, raw_json, entry_version, update_remarks, update_description, zvs_compliance_status FROM entries")
    all_entries = cur.fetchall()
    
    total = len(all_entries)
    print(f"\\nRegenerating dict_zo_en_master_v1.jsonl from {total} entries...")
    
    output_entries = []
    skipped = 0
    
    for i, entry in enumerate(all_entries):
        entry_id, headword, pos, english, sources, raw_json, version, remarks, description, zvs_status = entry
        
        if not headword:
            skipped += 1
            continue
        
        headword_clean = headword.strip().strip('"').strip("'").strip()
        english_clean = english.strip() if english else ''
        sources_clean = sources.strip() if sources else ''
        version_clean = version.strip() if version else 'v1.0'
        remarks_clean = remarks.strip() if remarks else ''
        description_clean = description.strip() if description else ''
        zvs_status_clean = zvs_status.strip() if zvs_status else 'pending'
        
        # Master version includes additional metadata
        entry_dict = {
            'zolai': headword_clean,
            'english': english_clean if english_clean else [],
            'source': sources_clean if sources_clean else 'database_master',
            'pos': pos.strip() if pos else '',
            'entry_version': version_clean,
            'update_remarks': remarks_clean,
            'update_description': description_clean,
            'zvs_compliance_status': zvs_status_clean,
            'id': entry_id  # Include ID for tracking
        }
        
        # Preserve raw_json if available
        if raw_json:
            try:
                rj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                if isinstance(rj, dict):
                    entry_dict['raw_json'] = rj
            except:
                pass
        
        output_entries.append(json.dumps(entry_dict, ensure_ascii=False))
        
        if (i + 1) % 10000 == 0:
            print(f"  Progress: {i+1}/{total} entries processed (skipped={skipped})")
    
    conn.close()
    
    output_path = 'data/dictionary/processed/dict_zo_en_master_v1.jsonl'
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in output_entries:
            f.write(line + '\n')
    
    print(f"\\n=== regenerated: {output_path} ===")
    print(f"Total entries: {total}")
    print(f"Successfully written: {len(output_entries)}")
    print(f"Skipped (no headword): {skipped}")


async def main():
    print("=== REGENERATE DICTIONARY JSONL FILES FROM DATABASE ===\n")
    await regenerate_verified_dict()
    await regenerate_master_dict()


if __name__ == "__main__":
    asyncio.run(main())
