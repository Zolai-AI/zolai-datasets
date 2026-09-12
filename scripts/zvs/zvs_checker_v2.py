#!/usr/bin/env python3
"""
ZVS 2018 Compliance Checker v2.

Reads dict_zo_en_verified_v1.jsonl (clean headwords) and checks each
against ZVS 2018 forbidden forms using Gemini Web API.

Updates the SQLite database with compliance status.
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


async def check_zvs_compliance(headword):
    """Use Gemini to check ZVS 2018 compliance for a headword."""
    client = get_gemini_client()
    
    ZVS_PROMPT = """You are a Zolai Standard (ZVS 2018) compliance checker.

Check if this Zolai word violates ZVS 2018 orthography rules.

FORBIDDEN forms (ALWAYS flag as "failed", replace with correct form):
- pathian → pasian (God) — ALWAYS forbidden
- ram → gam (earth/land) — ALWAYS forbidden  
- fapa → tapa (life/son) — ALWAYS forbidden
- bawipa → topa (Lord/master) — ALWAYS forbidden
- siangpahrang → kumpipa (Savior) — ALWAYS forbidden
- cu/cun → tua (that/conjunction) — ALWAYS forbidden

Return ONLY valid JSON:
{"zolai":"<headword>","zvs_violation":true/false,"zvs_correct_form":"<correct form or empty>","compliance_status":"passed|failed|pending","remarks":"<brief reason>","description":"<brief description>"}
"""
    
    try:
        # Clean the headword
        hw = headword.strip().strip('"').strip("'").strip()
        
        prompt = ZVS_PROMPT + "\n\nZolai word: " + hw
        output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
        text = output.text or ''
        
        # Clean up any Markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            json_str = text[start:end+1]
            result = json.loads(json_str)
        else:
            # Try parsing whole cleaned text
            result = json.loads(text.strip())
        
        return result
        
    except Exception as e:
        print(f"Error checking '{headword}': {e}")
        return {
            "zolai": headword,
            "zvs_violation": False,
            "zvs_correct_form": "",
            "compliance_status": "pending",
            "remarks": f"Error: {e!s}",
            "description": ""
        }


async def process_jsonl_entries(batch_size=100):
    """Process entries from dict_zo_en_verified_v1.jsonl and update database."""
    conn = sqlite3.connect('data/zolai.db')
    cur = conn.cursor()
    
    # Get all entries from JSONL
    with open('data/dictionary/processed/dict_zo_en_verified_v1.jsonl', encoding='utf-8') as f:
        entries = []
        for line in f:
            if line.strip():
                entry = json.loads(line)
                entries.append(entry)
    
    total = len(entries)
    print(f"Total entries from JSONL: {total}")
    
    # Get pending entries from DB
    cur.execute("SELECT * FROM dictionary WHERE zvs_compliance_status='pending'")
    pending_ids = set(row[0] for row in cur.fetchall())
    
    # Filter to only entries we can update in DB
    entries_to_check = [e for e in entries if e.get('id') in pending_ids or e.get('zolai')]
    
    # Actually, let's just process all JSONL entries and map by headword
    # The JSONL has 'zolai' field with the headword
    
    client = get_gemini_client()
    
    updated = 0
    violations = 0
    passed = 0
    
    for i, entry in enumerate(entries):
        zolai = entry.get('zolai', '') or entry.get('headword', '') or ''
        if not zolai:
            continue
        
        # Clean headword
        hw = zolai.strip().strip('"').strip("'").strip()
        if not hw or len(hw) < 1:
            continue
        
        # Check ZVS compliance
        result = await check_zvs_compliance(hw)
        zvs_status = result.get('compliance_status', 'pending')
        
        # Find the DB entry by headword
        cur.execute("SELECT * FROM dictionary WHERE headword=?", (hw,))
        db_row = cur.fetchone()
        
        if db_row:
            db_id = db_row[0]
            # Update the database
            cur.execute(
                "UPDATE dictionary SET entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
                (result.get('entry_version', 'v1.0'),
                 result.get('remarks', ''),
                 result.get('description', ''),
                 zvs_status,
                 db_id)
            )
            updated += 1
            
            if zvs_status == 'failed':
                violations += 1
                correct = result.get('zvs_correct_form', '')
                print(f"  VIOLATION: '{hw}' → Status: {zvs_status}, Correct: {correct}")
            elif zvs_status == 'passed':
                passed += 1
        
        # Commit in batches
        if (i + 1) % batch_size == 0:
            conn.commit()
            print(f"Progress: {i+1}/{total} entries done "
                  f"(updated={updated}, violations={violations}, passed={passed})")
    
    conn.commit()
    
    # Final summary
    cur.execute("SELECT * FROM dictionary GROUP BY zvs_compliance_status")
    final_status = cur.fetchall()
    print("\n=== FINAL SUMMARY ===")
    print(f"Total JSONL entries: {total}")
    print(f"Updated in DB: {updated}")
    for status, count in final_status:
        print(f"  {status}: {count}")
    print(f"Violations (ZVS forbidden forms): {violations}")
    print(f"Passed compliance: {passed}")
    conn.close()


async def main():
    print("=== ZVS 2018 COMPLIANCE CHECK v2 ===\n")
    await process_jsonl_entries(batch_size=500)


if __name__ == "__main__":
    asyncio.run(main())
