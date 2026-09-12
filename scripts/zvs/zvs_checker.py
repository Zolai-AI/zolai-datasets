#!/usr/bin/env python3
"""
ZVS 2018 Compliance Checker for Dictionary Database.

Extracts headwords from SQLite database and checks them against
ZVS 2018 forbidden forms using Gemini Web API.

Forbidden forms (must NOT appear in ZVS 2018 Zolai):
- pathian → pasian (God)
- ram → gam (earth/land)
- fapa → tapa (life/son)
- bawipa → topa (Lord/master)
- siangpahrang → kumpipa (Savior)
- cu/cun → tua (that/conjunction)

Also tracks:
- suah → valid in certain contexts (holiness)
- nunnak → valid in certain contexts (life)
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


async def extract_headword(raw_json_str):
    """Extract the actual Zolai headword from raw_json JSONB field."""
    try:
        if not raw_json_str:
            return None
        rj = json.loads(raw_json_str) if isinstance(raw_json_str, str) else raw_json_str
        if isinstance(rj, dict):
            # Try multiple fields for headword
            for field in ['headword', 'zolai', 'term']:
                if rj.get(field):
                    hw = str(rj[field]).strip()
                    # Clean up common formatting
                    hw = hw.strip('"').strip("'").strip()
                    if hw and len(hw) > 0:
                        return hw
        # Fallback: try to get first meaningful word from headword field
        return None
    except Exception as e:
        print(f"Error extracting headword: {e}")
        return None


async def check_zvs_compliance(headword):
    """Use Gemini to check ZVS 2018 compliance for a headword."""
    client = get_gemini_client()
    
    ZVS_PROMPT = """You are a Zolai Standard (ZVS 2018) compliance checker.

Check if this Zolai word violates ZVS 2018 orthography rules.

FORBIDDEN forms (ALWAYS flag as violation):
- pathian → pasian (God) — ALWAYS forbidden, must be "pasian"
- ram → gam (earth/land) — ALWAYS forbidden, must be "gam"
- fapa → tapa (life/son) — ALWAYS forbidden, must be "tapa"
- bawipa → topa (Lord/master) — ALWAYS forbidden, must be "topa"
- siangpahrang → kumpipa (Savior) — ALWAYS forbidden, must be "kumpipa"
- cu/cun → tua (that/conjunction) — ALWAYS forbidden, must be "tua"

NOT forbidden (valid ZVS 2018 forms):
- suah — valid in certain contexts (holiness-related)
- nunnak — valid in certain contexts (life-related)
- loro — valid Zolai word

Return ONLY valid JSON, no code blocks, no explanations:
{"zolai":"<headword>","zvs_violation":true/false,"zvs_correct_form":"<correct form or empty>","compliance_status":"passed|failed|pending","remarks":"<brief reason or compliance note>","description":"<brief ZVS compliance description>"}
"""
    
    try:
        prompt = ZVS_PROMPT + "\n\nZolai word: " + headword
        output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
        text = output.text or ''
        
        # Clean up any Markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        
        # Find JSON object
        json_match = None
        # Try to find { ... } block
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            json_str = text[start:end+1]
            json_match = json_str
        
        if json_match:
            result = json.loads(json_match)
        else:
            # Try parsing whole text
            result = json.loads(text.strip())
        
        return result
        
    except Exception as e:
        print(f"Gemini error for '{headword}': {e}")
        return {
            "zolai": headword,
            "zvs_violation": False,
            "zvs_correct_form": "",
            "compliance_status": "pending",
            "remarks": f"Gemini API error: {e!s}",
            "description": ""
        }


async def process_all_entries(batch_size=100):
    """Process all entries in the dictionary database for ZVS compliance."""
    conn = sqlite3.connect('data/zolai.db')
    cur = conn.cursor()
    
    # Get all entries that need processing
    cur.execute("SELECT * FROM dictionary WHERE zvs_compliance_status='pending'")
    all_rows = cur.fetchall()
    
    total = len(all_rows)
    print(f"Total entries to check: {total}")
    
    if total == 0:
        # Check distribution
        cur.execute("SELECT * FROM dictionary GROUP BY zvs_compliance_status")
        rows = cur.fetchall()
        print("Status distribution:")
        for status, count in rows:
            print(f"  {status}: {count}")
        conn.close()
        return
    
    client = get_gemini_client()
    
    updated = 0
    violations_found = 0
    passed = 0
    pending_count = 0
    
    for i, (row_id, headword, raw_json) in enumerate(all_rows):
        # Extract actual headword from raw_json if headword is empty
        hw = headword
        if not hw or headword.strip() == '':
            hw = await extract_headword(raw_json)
        
        if not hw:
            # Skip entries we can't extract headword from
            pending_count += 1
            if (i + 1) % 5000 == 0:
                conn.commit()
                print(f"Progress: {i+1}/{total}, updated={updated}, violations={violations_found}, passed={passed}")
            continue
        
        # Clean up the headword
        hw = hw.strip().strip('"').strip("'").strip()
        if not hw or len(hw) < 1:
            pending_count += 1
            if (i + 1) % 5000 == 0:
                conn.commit()
                print(f"Progress: {i+1}/{total}, updated={updated}, violations={violations_found}, passed={passed}")
            continue
        
        # Check ZVS compliance
        result = await check_zvs_compliance(hw)
        
        # Update database
        zvs_status = result.get('compliance_status', 'pending')
        update_remarks = result.get('remarks', '')
        update_description = result.get('description', '')
        
        # Only update if we got a meaningful result
        if zvs_status in ['passed', 'failed']:
            cur.execute(
                "UPDATE dictionary SET entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
                (result.get('entry_version', 'v1.0'),
                 update_remarks,
                 update_description,
                 zvs_status,
                 row_id)
            )
            updated += 1
            
            if zvs_status == 'failed':
                violations_found += 1
                # Also print the violation details
                correct_form = result.get('zvs_correct_form', '')
                print(f"  VIOLATION [{row_id}]: {hw} → Status: {zvs_status}, Correct: {correct_form}, Remarks: {update_remarks[:80]}")
            elif zvs_status == 'passed':
                passed += 1
        else:
            pending_count += 1
        
        updated_count = updated + pending_count
        
        # Commit in batches
        if (i + 1) % batch_size == 0:
            conn.commit()
            print(f"Progress: {i+1}/{total} entries done "
                  f"(updated={updated}, violations={violations_found}, passed={passed}, pending={pending_count})")
    
    # Final commit
    conn.commit()
    
    # Print final summary
    cur.execute("SELECT * FROM dictionary GROUP BY zvs_compliance_status")
    final_status = cur.fetchall()
    print("\n=== FINAL SUMMARY ===")
    print(f"Total entries: {total}")
    for status, count in final_status:
        print(f"  {status}: {count}")
    print(f"Updated this session: {updated}")
    print(f"Violations (ZVS forbidden forms): {violations_found}")
    print(f"Passed compliance: {passed}")
    print(f"Still pending: {pending_count}")
    conn.close()


async def main():
    # First, let's test with a few known entries
    print("=== TESTING WITH SAMPLE ENTRIES ===")
    conn = sqlite3.connect('data/zolai.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM dictionary LIMIT 5")
    test_rows = cur.fetchall()
    conn.close()
    
    for row_id, headword, raw_json in test_rows:
        hw = headword
        if not hw or headword.strip() == '':
            hw = await extract_headword(raw_json)
        print(f"Entry {row_id}: headword='{headword[:30] if headword else ''}'... extracted='{hw}'")
    
    # Now process all entries
    print("\n=== PROCESSING ALL ENTRIES ===")
    await process_all_entries(batch_size=100)


if __name__ == "__main__":
    asyncio.run(main())
