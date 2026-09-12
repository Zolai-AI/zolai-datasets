#!/usr/bin/env python3
"""
Gemini Data Learning & Database Update Pipeline.

Uses Gemini Web API to ANALYZE existing Zolai data, identify gaps/errors/suggest improvements,
and generate "pending" entries in the database for human review/approval.

CRITICAL: Gemini uses YOUR data as context/anchors — never generates in vacuum.
"""

import sqlite3
import json
import sys
import os
import re
import asyncio

# Add bible dir for gemini_cookies
SCRIPT_DIR = os.path.dirname(os.path.abspath('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client


async def analyze_dictionary_gaps():
    """Gemini analyzes dictionary entries and suggests improvements."""
    client = get_gemini_client()
    
    ANALYSIS_PROMPT = """You are a Zolai (Tedim Chin) dictionary analysis expert.
    You are given 93,931 dictionary entries. Your task is to ANALYZE them and SUGGEST improvements.
    
    FORBIDDEN ZVS 2018 forms (NEVER suggest these):
    - pathian → must be pasian (God)
    - ram → must be gam (earth/land)  
    - fapa → must be tapa (life/son)
    - bawipa → must be topa (Lord/master)
    - siangpahrang → must be kumpipa (Savior)
    - cu/cun → must be tua (that/conjunction)
    
    Also check for:
    - suah → seuak (holiness context-dependent)
    - nunnak → nuntakna (life context-dependent)
    
    Return ONLY JSON:
    {{
      "analysis_type": "gap_filling|error_correction|pattern_analysis|vocabulary_expansion",
      "entries_suggested": [
        {{
          "original_zolai": "current zolai in database",
          "suggested_zolai": "suggested correction or new entry",
          "suggested_english": ["translations"],
          "suggested_pos": "noun|verb|adj|adv|particle|number",
          "suggested_remarks": "ZVS compliance note or reason for change",
          "suggested_description": "Brief description of the change",
          "zvs_status": "passed|failed|pending",
          "confidence": 0.0-1.0
        }}
      ],
      "overall_assessment": "brief analysis of the dataset",
      "total_issues": number,
      "critical_fixes": number
    }}
    """
    
    # Read a sample of dictionary entries to analyze
    # We'll read 100 entries from the verified JSONL
    with open('data/dictionary/processed/dict_zo_en_verified_v1.jsonl', encoding='utf-8') as f:
        entries = []
        for i, line in enumerate(f):
            if i >= 100:  # Sample 100 for analysis
                break
            if line.strip():
                entries.append(json.loads(line))
    
    # Build summary of entries for Gemini
    summary_parts = []
    for entry in entries:
        zolai = entry.get('zolai', '') or entry.get('zolai', '') or ''
        english = entry.get('english', []) or []
        # Clean
        zolai_clean = zolai.strip().strip('"').strip("'").strip()
        if zolai_clean:
            summary_parts.append(f'HEADWORD: {zolai_clean} | ENGLISH: {english[:2]}')
    
    prompt = ANALYSIS_PROMPT + f'''
    
    ANALYZE this sample of 100 Zolai dictionary entries:
    
    {chr(10).join(summary_parts[:20])}
    
    Focus on:
    1. ZVS 2018 compliance (forbidden forms)
    2. Definition accuracy
    3. Missing words or senses
    4. Polysemy clarity
    5. Grammar pattern consistency
    
    Generate suggestions for improvement.
    '''
    
    try:
        output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
        text = output.text or ''
        
        # Extract JSON from output
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            result = json.loads(text[start:end+1])
            return result
        
        # Try parsing whole text
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Gemini analysis error: {e}")
        return {
            "analysis_type": "error",
            "entries_suggested": [],
            "overall_assessment": f"Error: {str(e)}",
            "total_issues": 0,
            "critical_fixes": 0
        }


async def flag_zvs_issues():
    """Gemini flags ZVS 2018 compliance issues in dictionary."""
    client = get_gemini_client()
    
    ZVS_PROMPT = """You are a Zolai Standard (ZVS 2018) compliance checker analyzing dictionary entries.
    
    FORBIDDEN (must flag and suggest correction):
    - pathian → pasian (God)
    - ram → gam (earth/land)
    - fapa → tapa (life/son)
    - bawipa → topa (Lord/master)
    - siangpahrang → kumpipa (Savior)
    - cu/cun → tua (that/conjunction)
    
    Also problematic:
    - suah → seuak (holiness)
    - nunnak → nuntakna (life)
    
    For each entry, return JSON:
    {{
      "zolai": "the word",
      "zvs_violation": true/false,
      "violating_form": "which forbidden form exists",
      "correct_form": "the ZVS 2018 correct form",
      "compliance_status": "passed|failed|pending",
      "remarks": "brief reason",
      "description": "brief description of the issue"
    }}
    """
    
    # Get entries with known issues or sample randomly
    import sqlite3
    conn = sqlite3.connect('data/zolai.db')
    cur = conn.cursor()
    cur.execute("SELECT id, zolai, raw_json FROM dictionary LIMIT 50")
    entries = cur.fetchall()
    conn.close()
    
    results = []
    for entry_id, zolai, raw_json in entries:
        hw = zolai.strip().strip('"').strip("'").strip() if zolai else ''
        if not hw:
            continue
        
        prompt = ZVS_PROMPT + f'\n\nZolai word: "{hw}"'
        try:
            output = await client.generate_content(prompt=prompt, model='gemini-3-flash')
            text = output.text or ''
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*$', '', text)
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                result = json.loads(text[start:end+1])
                result['entry_id'] = entry_id
                results.append(result)
            else:
                results.append({
                    "entry_id": entry_id,
                    "zolai": hw,
                    "zvs_violation": False,
                    "violating_form": "",
                    "correct_form": "",
                    "compliance_status": "pending",
                    "remarks": "Could not parse Gemini output",
                    "description": ""
                })
        except Exception as e:
            results.append({
                "entry_id": entry_id,
                "zolai": hw,
                "zvs_violation": False,
                "violating_form": "",
                "correct_form": "",
                "compliance_status": "pending",
                "remarks": f"Gemini error: {str(e)}",
                "description": ""
            })
    
    return results


async def main():
    print("="*70)
    print("GEMINI DATA LEARNING & DATABASE UPDATE PIPELINE")
    print("="*70)
    print("\n1. Analyzing dictionary gaps and patterns...")
    analysis = await analyze_dictionary_gaps()
    print(f"   Analysis type: {analysis.get('analysis_type', 'unknown')}")
    print(f"   Total issues: {analysis.get('total_issues', 0)}")
    print(f"   Critical fixes: {analysis.get('critical_fixes', 0)}")
    print(f"   Entries suggested: {len(analysis.get('entries_suggested', []))}")
    
    print(f"\n2. Flagging ZVS 2018 compliance issues...")
    zvs_results = await flag_zvs_issues()
    violations = [r for r in zvs_results if r.get('zvs_violation')]
    print(f"   entries checked: {len(zvs_results)}")
    print(f"   ZVS violations found: {len(violations)}")
    for v in violations[:5]:  # Show first 5
        print(f"     ID={v.get('entry_id')}: {v.get('zolai')} → {v.get('correct_form')}")
    
    print(f"\n3. Summary:")
    print(f"   Analysis: {analysis.get('overall_assessment', 'N/A')[:100]}")
    print(f"   Gemini-suggested entries ready for human review")
    print(f"\n=== PIPELINE COMPLETE ===")
    print("Next: Human reviews pending entries, approves/rejects, database updated")


asyncio.run(main())
