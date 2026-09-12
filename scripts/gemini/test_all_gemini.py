import os
#!/usr/bin/env python3
"""
Real Zolai Knowledge Test — ALL Gemini models using local package.
"""
import asyncio
import sys
import json
import sqlite3
import random

sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))
from gemini.client import ZolaiGeminiClient
from shared.zvs_context import get_compact_prompt

DB = "data/zolai.db"


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


def build_prompts(category, items):
    if category == "dict":
        return [f"{get_compact_prompt()}\n\nWhat does '{z}' mean in English? One word/phrase." for z, e in items]
    elif category == "bible":
        return [f"{get_compact_prompt()}\n\nTranslate this Zolai Bible verse to natural English:\n{z}" for _, z, _ in items]
    elif category == "eng2zo":
        return [f"{get_compact_prompt()}\n\nHow do you say this in Zolai? Just the Zolai word:\n{e}" for _, e, _ in items]
    elif category == "grammar":
        return [f"{get_compact_prompt()}\n\nGrammar patterns in this Zolai (SOV, ergative, negation, questions, agreement, tense):\n{z}" for _, z in items]
    return []


async def run_model(model, client, dict_prompts, bible_prompts, eng_prompts, grammar_prompts):
    """Run all categories for one model."""
    results = {}
    
    results["Dictionary"] = await client.ask_batch(model, dict_prompts)
    results["Bible Translation"] = await client.ask_batch(model, bible_prompts)
    results["English→Zolai"] = await client.ask_batch(model, eng_prompts)
    results["Grammar Analysis"] = await client.ask_batch(model, grammar_prompts)
    
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


async def main():
    print("═══ ZOLAI GEMINI KNOWLEDGE TEST — LOCAL PACKAGE ═══")
    
    dict_words, bible_verses, eng_words, grammar_sents = fetch_test_cases()
    print(f"Test cases: Dict={len(dict_words)}, Bible={len(bible_verses)}, Eng→Zo={len(eng_words)}, Grammar={len(grammar_sents)}")
    
    # Build prompts
    dict_prompts = build_prompts("dict", dict_words)
    bible_prompts = build_prompts("bible", bible_verses)
    eng_prompts = build_prompts("eng2zo", eng_words)
    grammar_prompts = build_prompts("grammar", grammar_sents)
    
    client = ZolaiGeminiClient()
    MODELS = client.MODELS
    
    all_results = {}
    
    for model in MODELS:
        print(f"\n--- {model} ---")
        model_results = await run_model(model, client, dict_prompts, bible_prompts, eng_prompts, grammar_prompts)
        all_results[model] = model_results
    
    await client.close()
    
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
    
    for cat_name in ["Dictionary", "Bible Translation", "English→Zolai", "Grammar Analysis"]:
        print(f"\n--- {cat_name} ---")
        data = test_data[cat_name]
        
        model_scores = {}
        for model in MODELS:
            model_results = all_results[model][cat_name]
            if cat_name == "Dictionary":
                scores = [score_dict_word(model_results[i], data[i][1]) for i in range(len(model_results))]
            elif cat_name == "Bible Translation":
                scores = [score_translation(model_results[i], data[i][2]) for i in range(len(model_results))]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(model_results[i], data[i][0]) for i in range(len(model_results))]
            else:
                scores = [score_grammar(model_results[i], data[i][1]) for i in range(len(model_results))]
            
            avg_score = sum(scores) / len(scores) if scores else 0
            model_scores[model] = {"avg": avg_score, "scores": scores}
        
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1]["avg"], reverse=True)
        print(f"\n{'Model':<35} {'Avg':>6}  Scores")
        print("-" * 60)
        for model, stats in sorted_models:
            detail = " ".join(f"{s:.1f}" for s in stats["scores"])
            print(f"{model:<35} {stats['avg']:>6.2f}  [{detail}]")
    
    # Save to DB
    save_results(all_results, dict_words, bible_verses, eng_words, grammar_sents)
    print("\n✅ Complete. Saved to training_runs.")


def save_results(results, dict_words, bible_verses, eng_words, grammar_sents):
    conn = get_db()
    c = conn.cursor()
    for cat_name, cat_results in results.items():
        for model in cat_results:
            model_results = cat_results[model]
            if cat_name == "Dictionary":
                scores = [score_dict_word(model_results[i], dict_words[i][1]) for i in range(len(model_results))]
            elif cat_name == "Bible Translation":
                scores = [score_translation(model_results[i], bible_verses[i][2]) for i in range(len(model_results))]
            elif cat_name == "English→Zolai":
                scores = [score_eng_to_zolai(model_results[i], eng_words[i][0]) for i in range(len(model_results))]
            else:
                scores = [score_grammar(model_results[i], grammar_sents[i][1]) for i in range(len(model_results))]
            avg_score = sum(scores) / len(scores) if scores else 0
            c.execute("""
                INSERT INTO training_runs (model_name, test_type, test_date, total_tests, passed_tests, score, details)
                VALUES (?, ?, datetime('now'), ?, ?, ?, ?)
            """, (model, cat_name, len(model_results), len([s for s in scores if s > 0]), avg_score, json.dumps({"scores": scores})))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
