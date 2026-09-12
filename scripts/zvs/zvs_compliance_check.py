import sqlite3
import json
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"

# ZVS 2018 forbidden forms (local rules)
FORBIDDEN_FORMS = {
    "pathian": "pasian",
    "ram": "gam",
    "fapa": "tapa",
    "bawipa": "topa",
    "siangpahrang": "kumpipa",
    "cu": "tua",
    "cun": "tua",
}

def check_zvs_local(zolai_word: str) -> dict:
    """Check ZVS 2018 compliance locally (no API needed)."""
    hw = zolai_word.lower().strip()
    
    for forbidden, correct in FORBIDDEN_FORMS.items():
        if hw == forbidden:
            return {
                "zvs_violation": True,
                "zvs_correct_form": correct,
                "compliance_status": "failed",
                "remarks": f"ZVS 2018: \"{forbidden}\" must be \"{correct}\"",
                "description": f"Deprecated form, replaced by \"{correct}\" in ZVS 2018"
            }
    
    return {
        "zvs_violation": False,
        "zvs_correct_form": "",
        "compliance_status": "passed",
        "remarks": "No ZVS 2018 violations detected",
        "description": "Compliant with ZVS 2018 orthography"
    }

async def check_zvs_gemini(headword: str, client) -> dict:
    """Check ZVS 2018 compliance using Gemini API."""
    ZVS_PROMPT = """You are a Zolai Standard (ZVS 2018) compliance checker.
Check if this dictionary entry violates ZVS 2018 orthography rules.

FORBIDDEN forms (must be flagged as "failed"):
- pathian -> pasian (God)
- ram -> gam (earth/land)
- fapa -> tapa (life/son)
- bawipa -> topa (Lord/master)
- siangpahrang -> kumpipa (Savior)
- cu/cun -> tua (that/conjunction)

NOT forbidden: suah, nunnak (valid in certain contexts)

Return ONLY JSON:
{"zvs_violation":true/false,"zvs_correct_form":"<correct or empty>","compliance_status":"passed|failed","remarks":"<reason>","description":"<description>"}
"""
    try:
        prompt = ZVS_PROMPT + "\n\nDictionary entry: zolai='" + zolai_word.strip() + "'"
        output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
        text = output.text or ''
        
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                return json.loads(line)
        
        return check_zvs_local(headword)  # fallback to local
    except Exception:
        return check_zvs_local(headword)  # fallback to local

def process_batch(batch_size=500, mode="local"):
    """
    Process pending ZVS compliance checks.
    Modes: 'local' (fast, no API), 'gemini' (AI-powered, needs network), 'all' (local first, gemini for unclear)
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT id, zolai FROM dictionary WHERE zvs_compliance_status='pending' LIMIT ?", (batch_size,))
    rows = cur.fetchall()
    
    if not rows:
        print("  No pending entries found — all checked!")
        conn.close()
        return
    
    print(f"  Processing {len(rows)} entries (mode: {mode})...")
    
    if mode == "gemini":
        try:
            BIBLE_DIR = "/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/bible"
            if BIBLE_DIR not in sys.path:
                sys.path.insert(0, BIBLE_DIR)
            from gemini_cookies import get_gemini_client
            import asyncio
            client = get_gemini_client()
            use_gemini = True
            print("  ✅ Gemini API connected")
        except Exception as e:
            print(f"  ⚠️ Gemini API unavailable ({e}), falling back to local rules")
            use_gemini = False
    else:
        use_gemini = False
    
    updated = 0
    violations = 0
    
    for i, (row_id, zolai_word) in enumerate(rows, 1):
        zolai_word_clean = zolai_word.strip().strip('"').strip("'").strip('[]').strip()
        
        if use_gemini and mode in ("gemini", "all"):
            result = asyncio.run(check_zvs_gemini(zolai_word_clean, client))
        else:
            result = check_zvs_local(zolai_word_clean)
        
        cur.execute(
            "UPDATE dictionary SET entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
            ('v1.0',
             result.get('remarks', ''),
             result.get('description', ''),
             result.get('compliance_status', 'pending'),
             row_id)
        )
        updated += 1
        if result.get('zvs_violation'):
            violations += 1
            print(f"    ❌ {zolai_word_clean} → {result.get('zvs_correct_form', '?')}")
        
        if i % 100 == 0:
            print(f"    [{i}/{len(rows)}] checked, {violations} violations so far...")
    
    conn.commit()
    conn.close()
    
    print(f"  ✅ Done: {updated} entries checked, {violations} violations found")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    batch = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    process_batch(batch, mode)
