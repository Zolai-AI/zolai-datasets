#!/usr/bin/env python3
"""
Gemini Data Learning — Uses local AI package and database.
Modes: myanmar, verify, unknowns, all
"""
import asyncio
import sys
import os
import json
import sqlite3
import argparse
from pathlib import Path

# Add local package
sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient
from shared.zvs_context import get_system_prompt

DB_PATH = Path(os.environ.get("DATA", "data")) / "zolai.db"


def get_db():
    return sqlite3.connect(DB_PATH)


async def fill_myanmar(client: ZolaiGeminiOpenAIClient, limit: int = 30):
    """Fill missing Myanmar translations."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT id, zolai, english_clean FROM dictionary
        WHERE myanmar IS NULL OR myanmar = ''
        AND english_clean IS NOT NULL AND english_clean != ''
        AND source IN ('bible_zo_en', 'bible_learned', 'supplement', 'zvs_master')
        ORDER BY RANDOM() LIMIT ?
    """, (limit,))
    
    entries = c.fetchall()
    conn.close()
    
    print(f"Filling Myanmar for {len(entries)} entries...")
    
    results = []
    for entry_id, zolai, english in entries:
        prompt = (
            f"Translate this Zolai word to Myanmar/Burmese script.\n"
            f"Zolai: {zolai}\n"
            f"English: {english}\n"
            f"Reply with ONLY the Myanmar translation."
        )
        
        try:
            # Use gemini-3-flash for speed
            result = await client.ask("gemini-3-flash", prompt, use_system_prompt=True)
            
            # Save to DB
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE dictionary SET myanmar = ? WHERE id = ?", (result.strip(), entry_id))
            conn.commit()
            conn.close()
            
            print(f"  {zolai:20s} → {english:30s} → {result.strip()}")
            results.append({"id": entry_id, "zolai": zolai, "english": english, "myanmar": result.strip()})
            
        except Exception as e:
            print(f"  {zolai:20s} → ERROR: {e}")
            results.append({"id": entry_id, "zolai": zolai, "error": str(e)})
        
        await asyncio.sleep(1)
    
    return results


async def verify_dictionary(client: ZolaiGeminiOpenAIClient, limit: int = 30):
    """Verify high-frequency dictionary entries."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT d.id, d.zolai, d.english_clean, v.frequency
        FROM dictionary d
        JOIN vocab v ON v.headword = d.zolai
        WHERE d.source = 'bible_zo_en'
        AND d.zolai != d.english_clean
        AND v.frequency > 100
        ORDER BY v.frequency DESC
        LIMIT ?
    """, (limit,))
    
    entries = c.fetchall()
    conn.close()
    
    print(f"Verifying {len(entries)} high-frequency entries...")
    
    results = []
    for entry_id, zolai, english, freq in entries:
        prompt = (
            f"You are a Zolai (Tedim Chin) language expert. ZVS 2018.\n"
            f"Is this translation correct?\n"
            f"Word: {zolai}\n"
            f"Our translation: {english}\n"
            f"Answer ONLY: correct OR incorrect: [correction]"
        )
        
        try:
            result = await client.ask("gemini-3-flash", prompt, use_system_prompt=True)
            
            is_correct = result.lower().startswith("correct")
            print(f"  {zolai:20s} ({freq:>5}) → {english:30s} → {result}")
            results.append({
                "id": entry_id, "zolai": zolai, "english": english, 
                "frequency": freq, "gemini_result": result, "correct": is_correct
            })
            
        except Exception as e:
            print(f"  {zolai:20s} → ERROR: {e}")
            results.append({"id": entry_id, "zolai": zolai, "error": str(e)})
        
        await asyncio.sleep(1)
    
    return results


async def identify_unknowns(client: ZolaiGeminiOpenAIClient, limit: int = 30):
    """Identify unknown/bad dictionary entries."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT id, zolai, english, source FROM dictionary
        WHERE (english LIKE '%[%' OR english LIKE '""%' OR LENGTH(english) < 3 OR zolai = english)
        AND source IN ('bible_learned', 'bible_zo_en', 'supplement')
        ORDER BY RANDOM() LIMIT ?
    """, (limit,))
    
    entries = c.fetchall()
    conn.close()
    
    print(f"Identifying {len(entries)} unknown entries...")
    
    results = []
    for entry_id, zolai, english, source in entries:
        prompt = (
            f"You are a Zolai (Tedim Chin) language expert. ZVS 2018.\n"
            f"What does this Zolai word mean in English?\n"
            f"Word: {zolai}\n"
            f"Context: Found in Zolai Bible text.\n"
            f"Reply with ONLY the English translation."
        )
        
        try:
            result = await client.ask("gemini-3-flash", prompt, use_system_prompt=True)
            
            # Update DB
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                UPDATE dictionary 
                SET english = ?, english_clean = ?, update_remarks = ?
                WHERE id = ?
            """, (result.strip(), result.strip(), f"gemini_corrected_from_{source}", entry_id))
            conn.commit()
            conn.close()
            
            print(f"  {zolai:20s} (was: {english:30s}) → {result.strip()}")
            results.append({
                "id": entry_id, "zolai": zolai, "old_english": english, 
                "new_english": result.strip(), "source": source
            })
            
        except Exception as e:
            print(f"  {zolai:20s} → ERROR: {e}")
            results.append({"id": entry_id, "zolai": zolai, "error": str(e)})
        
        await asyncio.sleep(1)
    
    return results


async def main():
    parser = argparse.ArgumentParser(description="Gemini Data Learning")
    parser.add_argument("--mode", choices=["myanmar", "verify", "unknowns", "all"], default="all")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    
    client = ZolaiGeminiOpenAIClient(use_zvs_context=True)
    await client.init()
    
    all_results = {}
    
    modes = ["myanmar", "verify", "unknowns"] if args.mode == "all" else [args.mode]
    
    for mode in modes:
        print(f"\n{'='*60}")
        print(f"MODE: {mode.upper()}")
        print(f"{'='*60}")
        
        if mode == "myanmar":
            results = await fill_myanmar(client, args.limit)
        elif mode == "verify":
            results = await verify_dictionary(client, args.limit)
        elif mode == "unknowns":
            results = await identify_unknowns(client, args.limit)
        
        all_results[mode] = results
        
        # Save to training_runs
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO training_runs (model_name, test_type, test_date, total_tests, passed_tests, score, details)
            VALUES (?, ?, datetime('now'), ?, ?, ?, ?)
        """, ("gemini-3-flash", f"data_learning_{mode}", len(results), 
              len([r for r in results if "error" not in r]), 0.0, json.dumps(results)))
        conn.commit()
        conn.close()
    
    await client.close()
    
    print(f"\n✅ Complete. Results saved to training_runs.")


if __name__ == "__main__":
    asyncio.run(main())
