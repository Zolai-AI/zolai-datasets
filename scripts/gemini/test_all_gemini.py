#!/usr/bin/env python3
"""
Real Zolai Knowledge Test — ALL Gemini models with persistent chats.
Reuses chat sessions, ZVS 2018 compliant, natural prompts.
"""
import asyncio
import sys
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

MAX_RETRIES = 2
RATE_LIMIT = 1

# Persistent clients per model
_model_clients = {}


async def get_model_client(model):
    """Get or create persistent client for a model."""
    if model not in _model_clients:
        client = GeminiClient()
        await client.init()
        _model_clients[model] = client
    return _model_clients[model]


async def close_all_clients():
    """Close all persistent clients."""
    for model, client in _model_clients.items():
        try:
            await client.close()
        except:
            pass
    _model_clients.clear()


def get_db():
    return sqlite3.connect(DB)


def fetch_test_cases():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT zolai, english_clean FROM dictionary 
        WHERE source = 'bible_zo_en' AND zolai != english_clean AND LENGTH(english_clean) > 2
        ORDER BY RANDOM() LIMIT 8
    """)
    dict_words = c.fetchall()
    
    c.execute("""
        SELECT ref, zo_tdb77, en_kJV FROM bible_verses 
        WHERE zo_tdb77 IS NOT NULL AND en_kJV IS NOT NULL
        AND LENGTH(zo_tdb77) BETWEEN 30 AND 200
        ORDER BY RANDOM() LIMIT 4
    """)
    bible_verses = c.fetchall()
    
    c.execute("""
        SELECT d.zolai, d.english_clean, v.frequency
        FROM dictionary d JOIN vocab v ON v.headword = d.zolai
        WHERE d.source = 'bible_zo_en' AND d.zolai != d.english_clean AND v.frequency > 100
        ORDER BY v.frequency DESC LIMIT 6
    """)
    eng_words = c.fetchall()
    
    c.execute("""
        SELECT ref, zo_tdb77 FROM bible_verses 
        WHERE zo_tdb77 IS NOT NULL AND LENGTH(zo_tdb77) BETWEEN 20 AND 150
        ORDER BY RANDOM() LIMIT 3
    """)
    grammar_sents = c.fetchall()
    
    conn.close()
    return dict_words, bible_verses, eng_words, grammar_sents


async def call_model(model, prompt, retries=MAX_RETRIES):
    """Call a model with persistent client."""
    client = await get_model_client(model)
    delay = 5
    
    for attempt in range(1, retries + 1):
        try:
            result = await client.generate_content(prompt=prompt, model=model)
            text = result.text if hasattr(result, 'text') else str(result)
            return {"model": model, "response": text, "error": None, "attempt": attempt}
        except Exception as e:
            err_str = str(e)
            if "timeout" in err_str.lower() or "unavailable" in err_str.lower() or attempt < retries:
                if attempt < retries:
                    await asyncio.sleep(delay)
                    delay *= 2
                continue
            return {"model": model, "response": None, "error": err_str[:80], "attempt": attempt}
    return {"model": model, "response": None, "error": "max retries"}


async def run_category(model, name, prompts):
    """Run all prompts for one model sequentially (reusing chat)."""
    results = []
    for i, prompt in enumerate(prompts):
        print(f"  [{model}] {name} {i+1}/{len(prompts)}...", end=" ", flush=True)
        result = await call_model(model, prompt)
        results.append(result)
        if result["error"]:
            print(f"ERR")
        else:
            print(f"OK")
        await asyncio.sleep(RATE_LIMIT)
    return results


def score_dict_word(gemini_ans, our_ans):
    if not gemini_ans or not our_ans: return 0
    g = gemini_ans.lower().strip()
    o = our_ans.lower().strip()
    if g == o: return 2
    if set(g.split()) & set(o.split()): return 1
    return 0


def score_translation(gemini_ans, kjv_ans):
    if not gemini_ans or not kjv_ans: return 0.0
    g = set(gemini_ans.lower().split())
    k = set(kjv_ans.lower().split())
    if not k: return 0.0
    return round(len(g & k) / len(k) * 2, 1)


def score_eng_to_zolai(gemini_ans, our_zolai):
    if not gemini_ans or not our_zolai: return 0
    return 2 if gemini_ans.lower().strip() == our_zolai.lower().strip() else 0


def score_grammar(gemini_ans, zo_text):
    if not gemini_ans: return 0
    patterns = ["sov", "in", "kei", "lo", "hiam", "bang hang", "a ", "ka ", "na ", "ding", "ta", "hi", "lai", "zo", "khin", "directional", "ergative", "negation", "question", "agreement", "tense", "aspect"]
    return min(sum(1 for p in patterns if p in gemini_ans.lower()), 5)


def build_prompts(category, items):
    """Build natural, ZVS 2018 compliant prompts."""
    zvs_context = (
        "You are a Zolai (Tedim Chin) language expert. "
        "Use ZVS 2018 orthography: pasian (not pathian), gam (not ram), "
        "tapa (not fapa), topa (not bawipa), kumpipa (not siangpahrang), "
        "tua (not cu/cun), suahtakna (not suah), nuntakna (not nunnak). "
        "Grammar: SOV order, ergative 'in', negation 'kei' (all persons), "
        "question 'hiam', agreement 'a/ka/na'."
    )
    
    if category == "dict":
        return [f"{zvs_context}\n\nWhat does this Zolai word mean in English? Reply with just the meaning:\nWord: {z}" for z, e in items]
    elif category == "bible":
        return [f"{zvs_context}\n\nTranslate this Zolai Bible verse to natural English:\n{z}" for _, z, _ in items]
    elif category == "eng2zo":
        return [f"{zvs_context}\n\nHow do you say this in Zolai (Tedim Chin)? Reply with just the Zolai word:\n{e}" for _, e, _ in items]
    elif category == "grammar":
        return [f"{zvs_context}\n\nAnalyze the grammar in this Zolai sentence. List: SOV, ergative, negation, questions, agreement, tense/aspect, directionals:\n{z}" for _, z in items]
    return []


async def main():
    print("═══ ZOLAI GEMINI KNOWLEDGE TEST — 9 MODELS (PERSISTENT CHATS) ═══")
    print(f"Models: {', '.join(MODELS)}")
    
    dict_words, bible_verses, eng_words, grammar_sents = fetch_test_cases()
    print(f"\nTest cases: Dict={len(dict_words)}, Bible={len(bible_verses)}, Eng→Zo={len(eng_words)}, Grammar={len(grammar_sents)}")
    
    # Build prompts
    dict_prompts = build_prompts("dict", dict_words)
    bible_prompts = build_prompts("bible", bible_verses)
    eng_prompts = build_prompts("eng2zo", eng_words)
    grammar_prompts = build_prompts("grammar", grammar_sents)
    
    # Run each model through all categories (reusing chat)
    all_results = {}
    
    for model in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")
        
        model_results = {}
        model_results["Dictionary"] = await run_category(model, "Dict", dict_prompts)
        model_results["Bible Translation"] = await run_category(model, "Bible", bible_prompts)
        model_results["English→Zolai"] = await run_category(model, "Eng→Zo", eng_prompts)
        model_results["Grammar Analysis"] = await run_category(model, "Gram", grammar_prompts)
        
        all_results[model] = model_results
    
    await close_all_clients()
    
    # Score and display
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    
    test_data = {
        "Dictionary": dict_words,
        "Bible Translation": bible_verses,
        "English→Zolai": eng_words,
        "Grammar Analysis": grammar_sents
    }
    
    # Transpose: category -> model -> results
    by_category = {}
    for cat_name in ["Dictionary", "Bible Translation", "English→Zolai", "Grammar Analysis"]:
        by_category[cat_name] = {}
        for model in MODELS:
            by_category[cat_name][model] = all_results[model][cat_name]
    
    for cat_name, cat_results in by_category.items():
        print(f"\n--- {cat_name} ---")
        data = test_data[cat_name]
        
        model_scores = {}
        for model in MODELS:
            model_results = cat_results[model]
            if cat_name == "Dictionary":
                scores = [score_dict_word(r["response"], data[i][1]) for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "Bible Translation":
                scores = [score_translation(r["response"], data[i][2]) for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(r["response"], data[i][0]) for i, r in enumerate(model_results) if r["response"]]
            else:
                scores = [score_grammar(r["response"], data[i][1]) for i, r in enumerate(model_results) if r["response"]]
            
            avg_score = sum(scores) / len(scores) if scores else 0
            success = len([r for r in model_results if r["response"]]) / len(model_results) * 100
            model_scores[model] = {"avg": avg_score, "success": success, "scores": scores}
        
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1]["avg"], reverse=True)
        print(f"\n{'Model':<35} {'Avg':>6} {'Succ%':>7}  Scores")
        print("-" * 70)
        for model, stats in sorted_models:
            detail = " ".join(f"{s:.1f}" for s in stats["scores"][:8])
            print(f"{model:<35} {stats['avg']:>6.2f} {stats['success']:>6.1f}%  [{detail}]")
    
    # Save
    save_results(by_category, dict_words, bible_verses, eng_words, grammar_sents)
    print("\n✅ Complete. Saved to training_runs.")


def save_results(results, dict_words, bible_verses, eng_words, grammar_sents):
    conn = get_db()
    c = conn.cursor()
    for cat_name, cat_results in results.items():
        for model in MODELS:
            model_results = cat_results[model]
            successful = [r for r in model_results if r["response"]]
            total = len(model_results)
            if cat_name == "Dictionary":
                scores = [score_dict_word(r["response"], dict_words[i][1]) for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "Bible Translation":
                scores = [score_translation(r["response"], bible_verses[i][2]) for i, r in enumerate(model_results) if r["response"]]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(r["response"], eng_words[i][0]) for i, r in enumerate(model_results) if r["response"]]
            else:
                scores = [score_grammar(r["response"], grammar_sents[i][1]) for i, r in enumerate(model_results) if r["response"]]
            avg_score = sum(scores) / len(scores) if scores else 0
            c.execute("""
                INSERT INTO training_runs (model_name, test_type, test_date, total_tests, passed_tests, score, details)
                VALUES (?, ?, datetime('now'), ?, ?, ?, ?)
            """, (model, cat_name, total, len(successful), avg_score, json.dumps({"scores": scores})))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
