#!/usr/bin/env python3
"""Real Zolai Knowledge Test — ALL 9 Gemini models with cross-evaluation.

Uses real Bible sentences, dictionary words, grammar patterns.
Runs each model on 4 categories, then cross-evaluates results.
"""
import asyncio
import json
import os
import sqlite3
import sys
import time


# ── Gemini client import ───────────────────────────────────
BIBLE_DIR = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai",
    "zolai-datasets/scripts/bible",
)
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)
from gemini_cookies import get_gemini_client

DB = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai", "data/zolai.db"
)

# ALL 9 models
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


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


# ── Database queries ───────────────────────────────────────
def fetch_test_cases():
    """Fetch real Zolai test cases from database."""
    conn = get_db()
    c = conn.cursor()

    # A: Dictionary words — LIMIT 15
    c.execute(
        "SELECT zolai, english_clean FROM dictionary "
        "WHERE source='bible_zo_en' AND english_clean IS NOT NULL "
        "AND english_clean != zolai AND LENGTH(english_clean) > 2 "
        "ORDER BY RANDOM() LIMIT 15"
    )
    dict_words = c.fetchall()

    # B: Bible verses — LIMIT 8
    c.execute(
        "SELECT ref, zo_tdb77, en_kJV FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND LENGTH(zo_tdb77) BETWEEN 30 AND 200 "
        "AND en_kJV IS NOT NULL "
        "ORDER BY RANDOM() LIMIT 8"
    )
    bible_verses = c.fetchall()

    # C: High-frequency English→Zolai words — 10 words
    c.execute(
        "SELECT d.zolai, d.english_clean, v.frequency "
        "FROM dictionary d "
        "JOIN vocab v ON v.headword = d.zolai "
        "WHERE d.source='bible_zo_en' "
        "AND d.zolai != d.english_clean "
        "AND v.frequency > 100 "
        "ORDER BY v.frequency DESC LIMIT 10"
    )
    eng_words = c.fetchall()

    # D: Grammar sentences — LIMIT 5
    c.execute(
        "SELECT ref, zo_tdb77 FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND LENGTH(zo_tdb77) BETWEEN 20 AND 150 "
        "AND (zo_tdb77 LIKE '%in%' OR zo_tdb77 LIKE '%kei%' "
        "OR zo_tdb77 LIKE '%hiam%' OR zo_tdb77 LIKE '%ding%' "
        "OR zo_tdb77 LIKE '%lo%') "
        "ORDER BY RANDOM() LIMIT 5"
    )
    grammar_sents = c.fetchall()

    conn.close()
    return dict_words, bible_verses, eng_words, grammar_sents


# ── Gemini call with retry ─────────────────────────────────
async def _call_gemini(
    client, model: str, prompt: str
) -> tuple:
    """Call Gemini with retry + exponential backoff."""
    delay = 5
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            output = await client.generate_content(
                prompt=prompt, model=model
            )
            elapsed = time.time() - start
            text = output.text or ""
            if "<ElicitationsGroup" in text:
                text = text[
                    : text.index("<ElicitationsGroup")
                ].strip()
            return text.strip(), elapsed
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                return f"ERROR: {type(e).__name__}: {e}", 0
    return f"ERROR: {last_err}", 0


# ── Scoring functions ──────────────────────────────────────
def _score_dict(gemini_ans: str, our_ans: str) -> int:
    """Score dictionary translation (max 2)."""
    if not gemini_ans or not our_ans:
        return 0
    g = gemini_ans.lower().strip()
    o = our_ans.lower().strip()
    if g == o:
        return 2
    g_words = set(g.split())
    o_words = set(o.split())
    if g_words & o_words:
        return 1
    return 0


def _score_bible(gemini_ans: str, kjv_ans: str) -> float:
    """Score Bible translation by word overlap (max 2)."""
    if not gemini_ans or not kjv_ans:
        return 0.0
    g = set(gemini_ans.lower().split())
    k = set(kjv_ans.lower().split())
    if not k:
        return 0.0
    overlap = len(g & k) / len(k)
    return round(overlap * 2, 1)


def _score_grammar(gemini_ans: str) -> int:
    """Score grammar analysis — check for key patterns (max 5)."""
    if not gemini_ans:
        return 0
    patterns = [
        "sov", "in", "kei", "lo", "hiam", "bang hang",
        "a ", "ka ", "na ", "ding", "ta", "hi", "lai",
        "zo", "khin", "directional",
    ]
    ans_lower = gemini_ans.lower()
    score = sum(1 for p in patterns if p in ans_lower)
    return min(score, 5)


# ── Build prompts for each category ────────────────────────
def _build_prompts(
    dict_words, bible_verses, eng_words, grammar_sents
):
    dict_prompts = [
        (
            "You are a Zolai (Tedim Chin) language expert. "
            "ZVS 2018 orthography.\n"
            "What does this Zolai word mean in English?\n"
            f"Word: {zolai}\n"
            "Reply with ONLY the English translation "
            "(one word or short phrase)."
        )
        for zolai, _eng in dict_words
    ]

    bible_prompts = [
        (
            "Translate this Zolai (Tedim Chin) sentence "
            "to English.\n"
            f"Sentence: {zo}\n"
            "Reply with ONLY the English translation."
        )
        for _ref, zo, _en in bible_verses
    ]

    eng_prompts = [
        (
            "Translate to Zolai (Tedim Chin, ZVS 2018). "
            "Reply ONLY with the Zolai word:\n"
            f"{eng}"
        )
        for _zolai, eng, _freq in eng_words
    ]

    grammar_prompts = [
        (
            "Analyze the grammar of this Zolai sentence. "
            "List patterns found:\n"
            "SOV order, ergative 'in', negation (kei/lo), "
            "question (hiam/bang hang), "
            "agreement (a/ka/na), tense (hi/ta/ding/lai/zo/khin), "
            "directionals.\n"
            f"Sentence: {zo}"
        )
        for _ref, zo in grammar_sents
    ]

    return dict_prompts, bible_prompts, eng_prompts, grammar_prompts


# ── Run one category across all models ─────────────────────
async def _run_category(
    client, name: str, prompts: list, test_data: list
) -> dict:
    """Run a category across all models, return results."""
    print(f"\n{'=' * 60}")
    print(f"CATEGORY: {name}")
    print(f"{'=' * 60}")

    results = {model: [] for model in MODELS}

    for i, prompt in enumerate(prompts):
        print(f"\n  Test {i + 1}/{len(prompts)}...")
        for model in MODELS:
            text, elapsed = await _call_gemini(client, model, prompt)
            results[model].append(text)
            status = "ERROR" if text.startswith("ERROR") else text[:60]
            print(f"    {model}: {status}... ({elapsed:.1f}s)")
            await asyncio.sleep(RATE_LIMIT)

    return results


# ── Score category results ─────────────────────────────────
def _score_category(
    cat_name: str, results: dict, test_data: list
) -> dict:
    """Score all model results for a category."""
    model_scores = {}
    for model in MODELS:
        scores = []
        for i, text in enumerate(results[model]):
            if text.startswith("ERROR"):
                continue
            if cat_name == "Dictionary":
                scores.append(_score_dict(text, test_data[i][1]))
            elif cat_name == "Bible":
                scores.append(_score_bible(text, test_data[i][2]))
            elif cat_name == "English→Zolai":
                scores.append(_score_dict(text, test_data[i][0]))
            else:  # Grammar
                scores.append(_score_grammar(text))

        avg = sum(scores) / len(scores) if scores else 0
        success = (
            len([r for r in results[model] if not r.startswith("ERROR")])
            / len(results[model]) * 100
        )
        model_scores[model] = {
            "avg": round(avg, 2),
            "success": round(success, 1),
            "scores": scores,
            "total": len(results[model]),
            "success_count": len(scores),
        }
    return model_scores


# ── Cross-model evaluation ─────────────────────────────────
async def _cross_evaluate(
    client, cat_name: str, prompts: list, results: dict
) -> list:
    """Each model evaluates another model's answer (round-robin)."""
    print(f"\n  Cross-evaluating {cat_name}...")
    matrix = []
    n = len(MODELS)

    for i, evaluator in enumerate(MODELS):
        target = MODELS[(i + 1) % n]
        correct = 0
        total = 0

        for j in range(len(prompts)):
            target_answer = results[target][j]
            if target_answer.startswith("ERROR"):
                continue

            eval_prompt = (
                "You are a Zolai language expert evaluating "
                "another AI's answer.\n"
                f"Question: {prompts[j]}\n"
                f"Answer to evaluate: {target_answer}\n"
                "Is this answer correct? "
                "Reply with ONLY: correct or incorrect: <reason>"
            )
            text, _ = await _call_gemini(client, evaluator, eval_prompt)
            await asyncio.sleep(RATE_LIMIT)

            if not text.startswith("ERROR"):
                total += 1
                if text.lower().strip().startswith("correct"):
                    correct += 1

        rate = (correct / total * 100) if total > 0 else 0
        matrix.append({
            "evaluator": evaluator,
            "target": target,
            "correct": correct,
            "total": total,
            "rate": round(rate, 1),
        })
        print(
            f"    {evaluator} → {target}: "
            f"{correct}/{total} ({rate:.1f}%)"
        )

    return matrix


# ── Print results ──────────────────────────────────────────
def _print_summary(
    all_cat_scores: dict, all_evals: dict
):
    """Print combined summary table."""
    print("\n" + "=" * 80)
    print("COMBINED RESULTS — ALL MODELS")
    print("=" * 80)

    # Aggregate scores per model
    agg = {m: {"total_score": 0, "total_items": 0} for m in MODELS}
    for cat_name, cat_scores in all_cat_scores.items():
        for model in MODELS:
            s = cat_scores[model]
            agg[model]["total_score"] += s["avg"] * s["success_count"]
            agg[model]["total_items"] += s["success_count"]

    # Sort by total score
    sorted_models = sorted(
        agg.items(),
        key=lambda x: x[1]["total_score"],
        reverse=True,
    )

    print(f"\n{'Model':<35} {'Score':>8} {'Items':>6} {'Avg':>6}")
    print("-" * 60)
    for model, stats in sorted_models:
        avg = (
            stats["total_score"] / stats["total_items"]
            if stats["total_items"] > 0
            else 0
        )
        print(
            f"{model:<35} "
            f"{stats['total_score']:>8.1f} "
            f"{stats['total_items']:>6} "
            f"{avg:>6.2f}"
        )

    # Cross-eval summary
    if all_evals:
        print(f"\n{'─' * 60}")
        print("CROSS-MODEL EVALUATION (each model evaluates next)")
        print(f"{'─' * 60}")
        for cat_name, eval_matrix in all_evals.items():
            print(f"\n  {cat_name}:")
            for entry in eval_matrix:
                print(
                    f"    {entry['evaluator']:<30} → "
                    f"{entry['target']:<30} "
                    f"{entry['correct']}/{entry['total']} "
                    f"({entry['rate']}%)"
                )


# ── Save to database ──────────────────────────────────────
def _log_run(model, test_type, total, passed, score, details):
    """Save to training_runs table."""
    conn = get_db()
    conn.execute(
        "INSERT INTO training_runs "
        "(model_name, test_type, test_date, total_tests, "
        "passed_tests, score, details) "
        "VALUES (?, ?, datetime('now'), ?, ?, ?, ?)",
        (model, test_type, total, passed, score,
         json.dumps(details)),
    )
    conn.commit()
    conn.close()


def _save_all_results(all_cat_scores, all_evals):
    """Save all results to training_runs."""
    # Save per-model per-category scores
    for cat_name, cat_scores in all_cat_scores.items():
        for model, stats in cat_scores.items():
            _log_run(
                model, cat_name, stats["total"],
                stats["success_count"], stats["avg"],
                {"scores": stats["scores"]},
            )

    # Save cross-eval summary
    for cat_name, eval_matrix in all_evals.items():
        for entry in eval_matrix:
            _log_run(
                entry["evaluator"],
                f"cross_eval:{cat_name}",
                entry["total"],
                entry["correct"],
                entry["rate"],
                {"target": entry["target"]},
            )


# ── Main ───────────────────────────────────────────────────
async def _run_all(client):
    print("═" * 60)
    print("  ZOLAI GEMINI KNOWLEDGE TEST — ALL 9 MODELS")
    print("═" * 60)
    print(f"  Models: {len(MODELS)}")
    print(f"  DB: {DB}")

    # Fetch test cases
    print("\nFetching test cases from database...")
    dict_words, bible_verses, eng_words, grammar_sents = (
        fetch_test_cases()
    )
    print(f"  Dict words (A):    {len(dict_words)}")
    print(f"  Bible verses (B):  {len(bible_verses)}")
    print(f"  Eng→Zolai (C):     {len(eng_words)}")
    print(f"  Grammar (D):       {len(grammar_sents)}")

    # Build prompts
    dict_p, bible_p, eng_p, gram_p = _build_prompts(
        dict_words, bible_verses, eng_words, grammar_sents
    )

    # Run all 4 categories
    all_results = {}
    all_results["Dictionary"] = await _run_category(
        client, "Dictionary Verification (Zolai→English)",
        dict_p, dict_words,
    )
    await asyncio.sleep(RATE_LIMIT)

    all_results["Bible"] = await _run_category(
        client, "Bible Translation (Zolai→English)",
        bible_p, bible_verses,
    )
    await asyncio.sleep(RATE_LIMIT)

    all_results["English→Zolai"] = await _run_category(
        client, "English→Zolai",
        eng_p, eng_words,
    )
    await asyncio.sleep(RATE_LIMIT)

    all_results["Grammar"] = await _run_category(
        client, "Grammar Analysis",
        gram_p, grammar_sents,
    )

    # Score results
    test_data_map = {
        "Dictionary": dict_words,
        "Bible": bible_verses,
        "English→Zolai": eng_words,
        "Grammar": grammar_sents,
    }
    all_cat_scores = {}
    for cat_name, cat_results in all_results.items():
        all_cat_scores[cat_name] = _score_category(
            cat_name, cat_results, test_data_map[cat_name]
        )

    # Cross-model evaluation
    print(f"\n{'=' * 60}")
    print("CROSS-MODEL EVALUATION PHASE")
    print(f"{'=' * 60}")
    all_evals = {}
    all_evals["Dictionary"] = await _cross_evaluate(
        client, "Dictionary", dict_p, all_results["Dictionary"]
    )
    all_evals["Bible"] = await _cross_evaluate(
        client, "Bible", bible_p, all_results["Bible"]
    )

    # Print summary
    _print_summary(all_cat_scores, all_evals)

    # Save to DB
    _save_all_results(all_cat_scores, all_evals)

    print("\n✅ Test complete. Results saved to training_runs.")
    return all_results


def main():
    client = get_gemini_client()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_all(client))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
