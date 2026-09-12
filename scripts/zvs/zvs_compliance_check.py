import sqlite3
import json
import sys
import os

# Add bible dir for gemini_cookies
SCRIPT_DIR = os.path.dirname(os.path.abspath('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client
import asyncio

async def process_batch(batch_size=100):
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    
    # Get headwords that need processing (pending status)
    cur.execute("SELECT id, headword FROM entries WHERE zvs_compliance_status='pending' LIMIT ?", (batch_size,))
    rows = cur.fetchall()
    
    if not rows:
        print("No pending entries found")
        conn.close()
        return
    
    print(f"Processing {len(rows)} entries...")
    
    client = get_gemini_client()
    
    ZVS_PROMPT = """You are a Zolai Standard (ZVS 2018) compliance checker.

Check if this dictionary entry violates ZVS 2018 orthography rules.

FORBIDDEN forms (must be flagged as "failed"):
- pathian -> pasian (God) — always forbidden
- ram -> gam (earth/land) — always forbidden
- fapa -> tapa (life/son) — always forbidden
- bawipa -> topa (Lord/master) — always forbidden
- siangpahrang -> kumpipa (Savior) — always forbidden
- cu/cun -> tua (that/conjunction) — always forbidden

NOT forbidden (these are valid ZVS 2018 forms):
- suah — valid in certain contexts
- nunnak — valid in certain contexts

Return ONLY JSON:
{"zolai":"<headword>","zvs_violation":true/false,"zvs_correct_form":"<correct form or empty>","compliance_status":"passed|failed|pending","remarks":"<brief reason or compliance note>","description":"<brief ZVS compliance description>"}
"""
    
    updated = 0
    
    for row_id, headword in rows:
        headword_clean = headword.strip().strip('"').strip("'").strip('[]').strip()
        
        try:
            prompt = ZVS_PROMPT + "\n\nDictionary entry: zolai='" + headword_clean + "', english=" + json.dumps({})
            output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
            text = output.text or ''
            
            json_match = None
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    json_match = line
                    break
            
            if json_match:
                result = json.loads(json_match)
            else:
                result = {"zolai": headword_clean, "zvs_violation": False, "zvs_correct_form": "", "compliance_status": "pending", "remarks": "Could not parse Gemini output", "description": ""}
            
            # Update the database
            cur.execute(
                "UPDATE entries SET entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
                (result.get('entry_version', 'v1.0'),
                 result.get('update_remarks', ''),
                 result.get('update_description', ''),
                 result.get('zvs_compliance_status', 'pending'),
                 row_id)
            )
            updated += 1
            
        except Exception as e:
            print(f"Error on {headword_clean}: {e}")
    
    conn.commit()
    print(f"Updated {updated} entries")
    conn.close()

asyncio.run(process_batch(batch_size=50))
