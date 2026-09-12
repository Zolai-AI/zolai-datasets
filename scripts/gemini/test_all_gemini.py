#!/usr/bin/env python3
"""
Real Zolai Knowledge Test — ALL Gemini models with cross-evaluation.
Uses real Bible sentences, dictionary words, grammar patterns.
"""
import asyncio
import sys
import time
import json
import sqlite3
import random
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents/Projects/pcore/pcore-webai/packages/gemini-webapi"))
from gemini_webapi import GeminiClient

DB = "data/zolai.db"

# ALL available models
MODELS = [
    "gemini-3-flash",
    "gemini-3-pro-plus",
    "gemini-3-pro",
    "gemini-3-flash-thinking",
    "gemini-3-flash-plus",
    "gemini-3-flash-thinking-plus",
    "gemini-3-pro-advanced",
    "gemini-3-flash-advanced",
    "gemini-3-flash-thinking-advanced",
]

MAX_RETRIES = 3
RATE_LIMIT = 2  # seconds between calls


def get_db():
    return sqlite3.connect(DB)


def fetch_test_cases():
    """Fetch real Zolai test cases from database."""
    conn = get_db()
    c = conn.cursor()
    
    # A: Dictionary words (high freq, real Zolai→English)
    c.execute("""
        SELECT zolai, english_clean FROM dictionary 
        WHERE source = 'bible_zo_en' 
        AND zolai != english_clean 
        AND LENGTH(english_clean) > 2
        AND LENGTH(zolai) > 1
        ORDER BY RANDOM() LIMIT 15
    """)
    dict_words = c.fetchall()
    
    # B: Bible verses (short, real parallel)
    c.execute("""
        SELECT ref, zo_tdb77, en_kJV FROM bible_verses 
        WHERE zo_tdb77 IS NOT NULL AND en_kJV IS NOT NULL
        AND LENGTH(zo_tdb77) BETWEEN 30 AND 200
        ORDER BY RANDOM() LIMIT 8
    """)
    bible_verses = c.fetchall()
    
    # C: English words (high freq in vocab)
    c.execute("""
        SELECT d.zolai, d.english_clean, v.frequency
        FROM dictionary d
        JOIN vocab v ON v.headword = d.zolai
        WHERE d.source = 'bible_zo_en' 
        AND d.zolai != d.english_clean
        AND v.frequency > 100
        ORDER BY v.frequency DESC LIMIT 10
    """)
    eng_words = c.fetchall()
    
    # D: Grammar sentences
    c.execute("""
        SELECT ref, zo_tdb77 FROM bible_verses 
        WHERE zo_tdb77 IS NOT NULL
        AND LENGTH(zo_tdb77) BETWEEN 20 AND 150
        ORDER BY RANDOM() LIMIT 5
    """)
    grammar_sents = c.fetchall()
    
    conn.close()
    return dict_words, bible_verses, eng_words, grammar_sents


async def call_model(client, model, prompt, retries=MAX_RETRIES):
    """Call a model with retry and rate limiting."""
    delay = 5
    last_err = None
    
    for attempt in range(1, retries + 1):
        try:
            result = await client.generate_content(prompt=prompt, model=model)
            return {"model": model, "response": result, "error": None, "attempt": attempt}
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"  [{model}] Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"  [{model}] All {retries} attempts failed: {e}")
    
    return {"model": model, "response": None, "error": str(last_err), "attempt": retries}


async def run_category(name, prompts, models):
    """Run a category across all models."""
    print(f"\n{'='*60}")
    print(f"CATEGORY: {name}")
    print(f"{'='*60}")
    
    client = GeminiClient()
    await client.init()
    
    results = {model: [] for model in models}
    
    for i, prompt in enumerate(prompts):
        print(f"\n  Test {i+1}/{len(prompts)}...")
        for model in models:
            result = await call_model(client, model, prompt)
            results[model].append(result)
            if result["error"]:
                print(f"    {model}: ERROR - {result['error'][:50]}")
            else:
                print(f"    {model}: {result['response'][:60]}...")
            await asyncio.sleep(RATE_LIMIT)
    
    await client.close()
    return results


def score_dict_word(gemini_ans, our_ans):
    """Score dictionary translation."""
    if not gemini_ans or not our_ans:
        return 0
    g = gemini_ans.lower().strip()
    o = our_ans.lower().strip()
    if g == o:
        return 2
    # Check word overlap
    g_words = set(g.split())
    o_words = set(o.split())
    if g_words & o_words:
        return 1
    return 0


def score_translation(gemini_ans, kjv_ans):
    """Score Bible translation by word overlap."""
    if not gemini_ans or not kjv_ans:
        return 0.0
    g = set(gemini_ans.lower().split())
    k = set(kjv_ans.lower().split())
    if not k:
        return 0.0
    overlap = len(g & k) / len(k)
    return round(overlap * 2, 1)  # max 2


def score_eng_to_zolai(gemini_ans, our_zolai):
    """Score English→Zolai."""
    if not gemini_ans or not our_zolai:
        return 0
    g = gemini_ans.lower().strip()
    o = our_zolai.lower().strip()
    if g == o:
        return 2
    return 0


def score_grammar(gemini_ans, zo_text):
    """Score grammar analysis - check for key patterns."""
    if not gemini_ans:
        return 0
    patterns = ["sov", "in", "kei", "lo", "hiam", "bang hang", "a ", "ka ", "na ", "ding", "ta", "hi", "lai", "zo", "khin", "directional"]
    score = 0
    ans_lower = gemini_ans.lower()
    for p in patterns:
        if p in ans_lower:
            score += 1
    return min(score, 5)  # max 5


async def main():
    print("═══ ZOLAI GEMINI KNOWLEDGE TEST — ALL MODELS ═══")
    print(f"Models: {', '.join(MODELS)}")
    
    # Fetch test cases
    print("\nFetching test cases from database...")
    dict_words, bible_verses, eng_words, grammar_sents = fetch_test_cases()
    print(f"  Dict words: {len(dict_words)}")
    print(f"  Bible verses: {len(bible_verses)}")
    print(f"  Eng→Zolai: {len(eng_words)}")
    print(f"  Grammar: {len(grammar_sents)}")
    
    # Build prompts for each category
    # A: Dictionary
    dict_prompts = []
    for zolai, eng in dict_words:
        dict_prompts.append(
            f"You are a Zolai (Tedim Chin) language expert. ZVS 2018 orthography.\n"
            f"What does this Zolai word mean in English?\n"
            f"Word: {zolai}\n"
            f"Reply with ONLY the English translation (one word or short phrase)."
        )
    
    # B: Bible translation
    bible_prompts = []
    for ref, zo, en in bible_verses:
        bible_prompts.append(
            f"Translate this Zolai (Tedim Chin) sentence to English.\n"
            f"Sentence: {zo}\n"
            f"Reply with ONLY the English translation."
        )
    
    # C: English→Zolai
    eng_prompts = []
    for zolai, eng, freq in eng_words:
        eng_prompts.append(
            f"Translate to Zolai (Tedim Chin, ZVS 2018). Reply ONLY with the Zolai word:\n"
            f"{eng}"
        )
    
    # D: Grammar
    grammar_prompts = []
    for ref, zo in grammar_sents:
        grammar_prompts.append(
            f"Analyze the grammar of this Zolai sentence. List patterns found:\n"
            f"SOV order, ergative 'in', negation (kei/lo), question (hiam/bang hang), "
            f"agreement (a/ka/na), tense (hi/ta/ding/lai/zo/khin), directionals.\n"
            f"Sentence: {zo}"
        )
    
    # Run all categories
    all_results = {}
    
    all_results["Dictionary"] = await run_category(
        "Dictionary Verification (Zolai→English)", dict_prompts, MODELS
    )
    all_results["Bible Translation"] = await run_category(
        "Bible Translation (Zolai→English)", bible_prompts, MODELS
    )
    all_results["English→Zolai"] = await run_category(
        "English→Zolai", eng_prompts, MODELS
    )
    all_results["Grammar Analysis"] = await run_category(
        "Grammar Analysis", grammar_prompts, MODELS
    )
    
    # Score and display results
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    
    # Print detailed table for each category
    for cat_name, results in all_results.items():
        print(f"\n--- {cat_name} ---")
        
        # Per-model scores
        model_scores = {}
        for model in MODELS:
            model_results = results[model]
            if cat_name == "Dictionary Verification (Zolai→English)":
                scores = [score_dict_word(r["response"], dict_words[i][1]) 
                         for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "Bible Translation (Zolai→English)":
                scores = [score_translation(r["response"], bible_verses[i][2]) 
                         for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(r["response"], eng_words[i][0]) 
                         for i, r in enumerate(model_results) if r["response"]]
            else:  # Grammar
                scores = [score_grammar(r["response"], grammar_sents[i][1]) 
                         for i, r in enumerate(model_results) if r["response"]]
            
            avg_score = sum(scores) / len(scores) if scores else 0
            success_rate = len([r for r in model_results if r["response"]]) / len(model_results) * 100
            model_scores[model] = {"avg": avg_score, "success": success_rate, "scores": scores}
        
        # Sort by avg score
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1]["avg"], reverse=True)
        
        print(f"\n{'Model':<35} {'Avg Score':>10} {'Success%':>10} {'Details'}")
        print("-" * 75)
        for model, stats in sorted_models:
            detail = " ".join(f"{s:.1f}" for s in stats["scores"][:5])
            print(f"{model:<35} {stats['avg']:>10.2f} {stats['success']:>9.1f}%  [{detail}]")
    
    # Save to database
    save_results(all_results, dict_words, bible_verses, eng_words, grammar_sents)
    
    print("\n✅ Test complete. Results saved to training_runs table.")


def save_results(results, dict_words, bible_verses, eng_words, grammar_sents):
    """Save test results to training_runs table."""
    conn = get_db()
    c = conn.cursor()
    
    for cat_name, cat_results in results.items():
        for model in MODELS:
            model_results = cat_results[model]
            successful = [r for r in model_results if r["response"]]
            total = len(model_results)
            
            if cat_name == "Dictionary Verification (Zolai→English)":
                scores = [score_dict_word(r["response"], dict_words[i][1]) 
                         for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "Bible Translation (Zolai→English)":
                scores = [score_translation(r["response"], bible_verses[i][2]) 
                         for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(r["response"], eng_words[i][0]) 
                         for i, r in enumerate(model_results) if r["response"]]
            else:
                scores = [score_grammar(r["response"], grammar_sents[i][1]) 
                         for i, r in enumerate(model_results) if r["response"]]
            
            avg_score = sum(scores) / len(scores) if scores else 0
            
            c.execute("""
                INSERT INTO training_runs (model_name, test_type, test_date, total_tests, 
                    passed_tests, score, details)
                VALUES (?, ?, datetime('now'), ?, ?, ?, ?)
            """, (
                model, cat_name, total, len(successful), avg_score,
                json.dumps({"scores": scores, "test_items": total})
            ))
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
