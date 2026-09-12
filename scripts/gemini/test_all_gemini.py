#!/usr/bin/env python3
"""Real Zolai Knowledge Test — ALL 9 Gemini Models + Cross-Model Evaluation.

Uses REAL data from zolai.db: dictionary entries, Bible verses,
grammar patterns. Runs each model on 4 categories, then
cross-evaluates results across models.

Test Categories:
  A — Dictionary Verification (15 words)
  B — Bible Translation ZO→EN (8 verses)
  C — English→Zolai (10 words)
  D — Grammar Recognition (5 sentences)

Cross-Model Evaluation:
  After all models respond, each model evaluates another's answer.
  Round-robin: model[i] evaluates model[(i+1) % 9].

Usage:
  python3 test_all_gemini.py
"""

import asyncio
import json
import os
import sqlite3
import sys
import time

# Add bible dir for gemini_cookies
BIBLE_DIR = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai",
    "zolai-datasets/scripts/bible",
)
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client

DB_PATH = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai", "data/zolai.db"
)

MAX_RETRIES = 3
RATE_LIMIT = 2  # seconds between Gemini calls

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

# Persistent event loop
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def get_db() -> sqlite3.Connection:
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


# ── Database queries ─────────────────────────────────────
def _get_dict_words(n: int = 15) -> list:
    """Pick n random dictionary words for verification."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT zolai, english_clean FROM dictionary "
        "WHERE source = 'bible_zo_en' "
        "AND english_clean IS NOT NULL "
        "AND english_clean != zolai "
        "AND LENGTH(english_clean) > 2 "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_bible_verses(n: int = 8) -> list:
    """Pick n random Bible verses for ZO→EN translation."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ref, zo_tdb77, en_kJV FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND LENGTH(zo_tdb77) BETWEEN 30 AND 200 "
        "AND en_kJV IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_eng_words(n: int = 10) -> list:
    """Pick n high-frequency English words for EN→ZO."""
    words = [
        "God", "water", "earth", "man", "woman",
        "child", "king", "house", "day", "night",
        "father", "mother", "brother", "sister",
        "heart", "life", "death", "love", "fear",
        "good", "evil", "great", "small", "new",
    ]
    import random
    random.shuffle(words)
    return [{"english": w} for w in words[:n]]


def _get_grammar_sentences(n: int = 5) -> list:
    """Pick n Bible verses with known grammar patterns."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ref, zo_tdb77 FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND (zo_tdb77 LIKE '%in%' "
        "OR zo_tdb77 LIKE '%kei%' "
        "OR zo_tdb77 LIKE '%hiam%' "
        "OR zo_tdb77 LIKE '%ding%' "
        "OR zo_tdb77 LIKE '%lo%') "
        "AND LENGTH(zo_tdb77) > 15 "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Gemini call with retry ──────────────────────────────
async def _call_gemini(client, prompt: str, model: str) -> tuple:
    """Call Gemini with retry + exponential backoff."""
    delay = 5  # 5s, 10s, 20s
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


# ── Scoring functions ───────────────────────────────────
def _score_dict(gemini_answer: str, expected: str) -> int:
    """Score 0-2: exact=2, partial=1, wrong=0."""
    ga = gemini_answer.lower().strip().rstrip(".")
    eb = expected.lower().strip().rstrip(".")
    if ga == eb:
        return 2
    g_words = set(ga.split())
    e_words = set(eb.split())
    if g_words & e_words:
        return 1
    return 0


def _score_bible(gemini_answer: str, expected: str) -> float:
    """Score 0.0-2.0 by word overlap ratio."""
    ga = set(
        gemini_answer.lower()
        .replace(",", "").replace(".", "").split()
    )
    eb = set(
        expected.lower()
        .replace(",", "").replace(".", "").split()
    )
    if not eb:
        return 0.0
    overlap = ga & eb
    return round(len(overlap) / len(eb) * 2, 1)


_KNOWN_PATTERNS = {
    "sov": ["subject.*verb", "SOV", "subject.*object.*verb"],
    "ergative": ["in", "ergative", "by"],
    "negation": ["kei", "lo", "negation", "not"],
    "question": ["hiam", "question", "?"],
    "future": ["ding", "future", "will"],
    "agreement": ["a ", "ka ", "na ", "agreement"],
}


def _score_grammar(
    gemini_answer: str, zo_text: str
) -> tuple:
    """Score grammar recognition. Returns (score, max)."""
    text_lower = gemini_answer.lower()
    detected = set()
    for pattern, keywords in _KNOWN_PATTERNS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                detected.add(pattern)
                break

    actual = set()
    if " in " in zo_text:
        actual.add("ergative")
    if "kei" in zo_text:
        actual.add("negation")
    if "hiam" in zo_text:
        actual.add("question")
    if "ding" in zo_text:
        actual.add("future")
    if any(zo_text.startswith(p) for p in ["a ", "ka ", "na "]):
        actual.add("agreement")

    if not actual:
        return (1.0 if detected else 0.0, 1.0)
    hits = detected & actual
    return (len(hits), len(actual))


# ── Category runners ────────────────────────────────────
async def _run_category_a(
    client, model: str, words: list
) -> dict:
    """Category A: Dictionary Verification — 15 words."""
    prompt_lines = [
        "You are a Zolai (Tedim Chin) language expert.",
        "What does each Zolai word mean in English?",
        "Reply with ONLY the translations, one per line.",
        "Format: word = translation",
        "",
    ]
    for w in words:
        prompt_lines.append(f"{w['zolai']} = ?")

    prompt = "\n".join(prompt_lines)
    text, elapsed = await _call_gemini(client, prompt, model)

    answers = {}
    for line in text.split("\n"):
        line = line.strip()
        if "=" in line:
            parts = line.split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                val = parts[1].strip()
                if val and val != "?":
                    answers[key] = val

    total = 0
    details = []
    for w in words:
        zolai = w["zolai"]
        expected = w["english_clean"]
        gemini_ans = answers.get(zolai.lower(), "(not found)")
        score = _score_dict(gemini_ans, expected)
        total += score
        details.append({
            "word": zolai,
            "expected": expected,
            "gemini": gemini_ans,
            "score": score,
        })

    return {
        "category": "A — Dict Verify",
        "model": model,
        "total_score": total,
        "max_score": len(words) * 2,
        "details": details,
        "elapsed": elapsed,
    }


async def _run_category_b(
    client, model: str, verses: list
) -> dict:
    """Category B: Bible Translation ZO→EN — 8 verses."""
    results = []
    total_score = 0.0

    for v in verses:
        prompt = (
            "Translate this Zolai (Tedim Chin) sentence "
            "to English:\n"
            f'{v["zo_tdb77"]}\n\n'
            "Reply with ONLY the English translation."
        )
        text, _elapsed = await _call_gemini(client, prompt, model)
        await asyncio.sleep(RATE_LIMIT)

        score = _score_bible(text, v["en_kJV"])
        total_score += score
        results.append({
            "ref": v["ref"],
            "zolai": v["zo_tdb77"][:80],
            "expected_en": v["en_kJV"][:80],
            "gemini_en": text[:80],
            "score": score,
        })

    avg = round(total_score / len(verses), 2) if verses else 0
    return {
        "category": "B — Bible ZO→EN",
        "model": model,
        "total_score": total_score,
        "max_score": len(verses),
        "avg_score": avg,
        "details": results,
    }


async def _run_category_c(
    client, model: str, eng_words: list
) -> dict:
    """Category C: English→Zolai — 10 words."""
    results = []
    found_in_db = 0

    for item in eng_words:
        word = item["english"]
        prompt = (
            "Translate this English word to Zolai "
            "(Tedim Chin, ZVS 2018):\n"
            f"{word}\n\n"
            "Reply with ONLY the Zolai translation."
        )
        text, _elapsed = await _call_gemini(client, prompt, model)
        await asyncio.sleep(RATE_LIMIT)

        gemini_zo = text.strip().split("\n")[0].strip()

        # Check if Gemini's answer exists in our DB
        conn = get_db()
        cur = conn.execute(
            "SELECT zolai FROM dictionary "
            "WHERE LOWER(zolai) = LOWER(?) LIMIT 1",
            (gemini_zo,),
        )
        in_db = len(cur.fetchall()) > 0
        conn.close()

        if in_db:
            found_in_db += 1

        results.append({
            "english": word,
            "gemini_zolai": gemini_zo,
            "db_match": in_db,
        })

    return {
        "category": "C — EN→ZO",
        "model": model,
        "total_score": found_in_db,
        "max_score": len(eng_words),
        "details": results,
    }


async def _run_category_d(
    client, model: str, sentences: list
) -> dict:
    """Category D: Grammar Recognition — 5 sentences."""
    results = []
    correct_count = 0.0

    for s in sentences:
        prompt = (
            "Identify the grammar patterns in this "
            "Zolai (Tedim Chin) sentence:\n"
            f'{s["zo_tdb77"]}\n\n'
            "List patterns like: SOV order, ergative 'in', "
            "negation 'kei', question 'hiam', future 'ding', "
            "agreement marker, etc.\n"
            "Reply with a comma-separated list of patterns."
        )
        text, _elapsed = await _call_gemini(client, prompt, model)
        await asyncio.sleep(RATE_LIMIT)

        hits, total = _score_grammar(text, s["zo_tdb77"])
        correct_count += hits / total if total else 1.0

        # Extract detected pattern names
        detected = set()
        text_lower = text.lower()
        for pattern, keywords in _KNOWN_PATTERNS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    detected.add(pattern)
                    break

        # Extract actual pattern names
        actual = set()
        if " in " in s["zo_tdb77"]:
            actual.add("ergative")
        if "kei" in s["zo_tdb77"]:
            actual.add("negation")
        if "hiam" in s["zo_tdb77"]:
            actual.add("question")
        if "ding" in s["zo_tdb77"]:
            actual.add("future")
        if any(
            s["zo_tdb77"].startswith(p)
            for p in ["a ", "ka ", "na "]
        ):
            actual.add("agreement")

        ratio = hits / total if total else 1.0
        results.append({
            "ref": s["ref"],
            "sentence": s["zo_tdb77"][:60],
            "gemini_patterns": ", ".join(detected),
            "actual_patterns": ", ".join(actual),
            "match_ratio": round(ratio, 2),
        })

    avg = (
        round(correct_count / len(sentences), 2)
        if sentences else 0
    )
    return {
        "category": "D — Grammar",
        "model": model,
        "total_score": correct_count,
        "max_score": len(sentences),
        "avg_score": avg,
        "details": results,
    }


# ── Cross-model evaluation ──────────────────────────────
async def _cross_evaluate(
    client, category_name: str,
    prompts: list, all_model_answers: dict
) -> list:
    """Cross-evaluate: model[i] evaluates model[(i+1)%9].

    Returns list of dicts with evaluator, target, correct,
    total, rate.
    """
    n = len(MODELS)
    eval_results = []

    for i, evaluator in enumerate(MODELS):
        target = MODELS[(i + 1) % n]
        correct = 0
        total = len(prompts)

        for j, prompt in enumerate(prompts):
            target_answer = (
                all_model_answers[target][j]
                if j < len(all_model_answers[target])
                else "(no answer)"
            )
            eval_prompt = (
                "You are a Zolai language expert "
                "evaluating another AI's answer.\n"
                f"Question: {prompt}\n"
                f"Answer to evaluate: {target_answer}\n\n"
                "Is this answer correct? "
                "Reply with ONLY: correct or incorrect: <reason>"
            )
            text, _ = await _call_gemini(
                client, eval_prompt, evaluator
            )
            await asyncio.sleep(RATE_LIMIT)

            if text.lower().strip().startswith("correct"):
                correct += 1

        rate = round(correct / total * 100, 1) if total else 0
        eval_results.append({
            "evaluator": evaluator,
            "target": target,
            "correct": correct,
            "total": total,
            "rate": rate,
        })

        print(
            f"  {evaluator} evaluates {target}: "
            f"{correct}/{total} ({rate}%)"
        )

    return eval_results


# ── Print functions ─────────────────────────────────────
def _print_category(result: dict) -> None:
    """Print results for one category."""
    cat = result["category"]
    model = result["model"]
    total = result["total_score"]
    maximum = result["max_score"]

    print(f"\n  ┌─ {cat} ─────────────────")
    print(f"  │ Model: {model}")

    pct = (total / maximum * 100) if maximum else 0
    marker = "🟢" if pct >= 80 else (
        "🟡" if pct >= 50 else "🔴"
    )
    print(f"  │ Score: {total}/{maximum} {marker} {pct:.0f}%")
    print("  │")

    for d in result["details"]:
        if "word" in d:
            icon = "✅" if d["score"] == 2 else (
                "⚠️" if d["score"] == 1 else "❌"
            )
            print(
                f"  │ {icon} {d['word']:15s} "
                f"expected: {d['expected']:20s} "
                f"gemini: {d['gemini']}"
            )
        elif "ref" in d and "zolai" in d:
            score_bar = "█" * int(d["score"] * 5)
            print(
                f"  │ {d['ref']:10s} "
                f"{d['score']:.1f} {score_bar}"
            )
            print(f"  │   ZO: {d['zolai'][:50]}")
            print(
                f"  │   EN: {d.get('gemini_en', '')[:50]}"
            )
        elif "english" in d:
            icon = "✅" if d.get("db_match") else "❌"
            print(
                f"  │ {icon} {d['english']:10s} "
                f"→ {d['gemini_zolai']:15s}"
            )
        elif "sentence" in d:
            ratio = d.get("match_ratio", 0)
            icon = "✅" if ratio >= 0.7 else (
                "⚠️" if ratio >= 0.3 else "❌"
            )
            print(
                f"  │ {icon} {d['ref']:10s} "
                f"match={ratio:.0%}"
            )
            print(
                f"  │   Gemini: {d['gemini_patterns']}"
            )
            print(
                f"  │   Actual: {d['actual_patterns']}"
            )

    print("  └──────────────────────────")


def _print_summary(all_results: dict) -> None:
    """Print formatted comparison table."""
    models = MODELS
    cats = [
        "A — Dict Verify",
        "B — Bible ZO→EN",
        "C — EN→ZO",
        "D — Grammar",
    ]

    print(f"\n{'=' * 80}")
    print("  MODEL COMPARISON SUMMARY")
    print(f"{'=' * 80}")

    # Header
    print(f"  {'Category':<20} ", end="")
    for m in models:
        short = m.replace("gemini-3-", "").replace("-", "")[:10]
        print(f"{short:>11}", end="")
    print()
    print(f"  {'-' * 20} ", end="")
    for _ in models:
        print(f"{'-' * 11}", end="")
    print()

    # Rows
    for i, cat_name in enumerate(cats):
        print(f"  {cat_name:<20} ", end="")
        for model in models:
            cat_data = all_results.get(cat_name, {})
            if model in cat_data:
                r = cat_data[model]
                score = f"{r['total_score']:.0f}/{r['max_score']}"
                print(f"{score:>11}", end="")
            else:
                print(f"{'—':>11}", end="")
        print()

    # Overall
    print(f"  {'-' * 20} ", end="")
    for _ in models:
        print(f"{'-' * 11}", end="")
    print()

    print(f"  {'Overall':<20} ", end="")
    for model in models:
        total_score = 0
        total_max = 0
        for cat_name in cats:
            cat_data = all_results.get(cat_name, {})
            if model in cat_data:
                r = cat_data[model]
                total_score += r["total_score"]
                total_max += r["max_score"]
        pct = (
            total_score / total_max * 100 if total_max else 0
        )
        print(f"{pct:>10.0f}%", end="")
    print()
    print(f"{'=' * 80}")


def _print_eval_matrix(eval_results: dict) -> None:
    """Print cross-model evaluation matrix."""
    print(f"\n{'=' * 80}")
    print("  CROSS-MODEL EVALUATION MATRIX")
    print("  (Model[i] evaluates Model[(i+1)%9])")
    print(f"{'=' * 80}")

    for cat_name, results in eval_results.items():
        print(f"\n  --- {cat_name} ---")
        for entry in results:
            print(
                f"  {entry['evaluator']:30s} → "
                f"{entry['target']:30s}  "
                f"{entry['correct']}/{entry['total']} "
                f"({entry['rate']}%)"
            )

    print(f"{'=' * 80}")


# ── Save to database ─────────────────────────────────────
def _log_run(
    model: str, dataset: str, count: int,
    metrics: dict, status: str = "completed",
) -> None:
    """Save to training_runs table."""
    conn = get_db()
    conn.execute(
        "INSERT INTO training_runs "
        "(model_name, dataset_name, entry_count, "
        "metrics_json, status) VALUES (?, ?, ?, ?, ?)",
        (model, dataset, count, json.dumps(metrics), status),
    )
    conn.commit()
    conn.close()


def _save_all_results(
    all_results: dict, eval_results: dict,
    dict_words: list, bible_verses: list,
    eng_words: list, grammar_sents: list,
) -> None:
    """Save all results to training_runs."""
    test_data = {
        "Dictionary": dict_words,
        "Bible Translation": bible_verses,
        "English→Zolai": eng_words,
        "Grammar": grammar_sents,
    }

    for cat_name, cat_results in all_results.items():
        for model in MODELS:
            if model not in cat_results:
                continue
            r = cat_results[model]
            _log_run(
                model,
                cat_name,
                r["max_score"],
                {
                    "total_score": r["total_score"],
                    "max_score": r["max_score"],
                    "avg_score": r.get("avg_score", 0),
                    "details": r["details"],
                },
            )

    # Save cross-eval results
    for cat_name, eval_list in eval_results.items():
        for entry in eval_list:
            _log_run(
                entry["evaluator"],
                f"cross_eval:{cat_name}",
                entry["total"],
                {
                    "target": entry["target"],
                    "correct": entry["correct"],
                    "rate": entry["rate"],
                },
            )


# ── Main ─────────────────────────────────────────────────
async def _run_all(client) -> dict:
    """Run all 4 categories on all 9 models."""
    print("=" * 60)
    print("  ZOLAI GEMINI KNOWLEDGE TEST — ALL 9 MODELS")
    print("=" * 60)
    print(f"  Models: {len(MODELS)}")
    print(f"  DB: {DB_PATH}")

    # Fetch test cases
    print("\nFetching test cases from database...")
    dict_words = _get_dict_words(15)
    bible_verses = _get_bible_verses(8)
    eng_words = _get_eng_words(10)
    grammar_sents = _get_grammar_sentences(5)
    print(f"  Dict words (A):    {len(dict_words)}")
    print(f"  Bible verses (B):  {len(bible_verses)}")
    print(f"  Eng→Zolai (C):     {len(eng_words)}")
    print(f"  Grammar (D):       {len(grammar_sents)}")

    # Run all categories for all models
    all_results = {}
    all_model_answers = {
        "Dictionary": {m: [] for m in MODELS},
        "Bible Translation": {m: [] for m in MODELS},
        "English→Zolai": {m: [] for m in MODELS},
        "Grammar": {m: [] for m in MODELS},
    }

    for model in MODELS:
        print(f"\n{'=' * 60}")
        print(f"  MODEL: {model}")
        print(f"{'=' * 60}")

        # A — Dictionary Verification
        print("  Running A — Dictionary Verification...")
        r = await _run_category_a(client, model, dict_words)
        all_results.setdefault("Dictionary", {})[model] = r
        all_model_answers["Dictionary"][model] = [
            d["gemini"] for d in r["details"]
        ]
        await asyncio.sleep(RATE_LIMIT)

        # B — Bible Translation
        print("  Running B — Bible Translation ZO→EN...")
        r = await _run_category_b(client, model, bible_verses)
        all_results.setdefault("Bible Translation", {})[model] = r
        all_model_answers["Bible Translation"][model] = [
            d["gemini_en"] for d in r["details"]
        ]
        await asyncio.sleep(RATE_LIMIT)

        # C — English→Zolai
        print("  Running C — English→Zolai...")
        r = await _run_category_c(client, model, eng_words)
        all_results.setdefault("English→Zolai", {})[model] = r
        all_model_answers["English→Zolai"][model] = [
            d["gemini_zolai"] for d in r["details"]
        ]
        await asyncio.sleep(RATE_LIMIT)

        # D — Grammar Recognition
        print("  Running D — Grammar Recognition...")
        r = await _run_category_d(client, model, grammar_sents)
        all_results.setdefault("Grammar", {})[model] = r
        all_model_answers["Grammar"][model] = [
            d["gemini_patterns"] for d in r["details"]
        ]

    # Print category results for each model
    for model in MODELS:
        for cat_name in [
            "Dictionary", "Bible Translation",
            "English→Zolai", "Grammar"
        ]:
            if model in all_results.get(cat_name, {}):
                _print_category(all_results[cat_name][model])

    # Print summary table
    _print_summary(all_results)

    # Cross-model evaluation (Dictionary + Bible only)
    print("\n" + "=" * 60)
    print("  CROSS-MODEL EVALUATION")
    print("=" * 60)

    eval_results = {}
    dict_prompts = [
        f"Zolai expert. What does '{w['zolai']}' mean?"
        for w in dict_words
    ]
    bible_prompts = [
        f"Translate: {v['zo_tdb77']}"
        for v in bible_verses
    ]

    print("\n  Evaluating Dictionary category...")
    eval_results["Dictionary"] = await _cross_evaluate(
        client, "Dictionary", dict_prompts,
        all_model_answers["Dictionary"],
    )

    print("\n  Evaluating Bible Translation category...")
    eval_results["Bible Translation"] = await _cross_evaluate(
        client, "Bible Translation", bible_prompts,
        all_model_answers["Bible Translation"],
    )

    # Print eval matrix
    _print_eval_matrix(eval_results)

    # Save to DB
    _save_all_results(
        all_results, eval_results,
        dict_words, bible_verses,
        eng_words, grammar_sents,
    )
    print("\n✅ Test complete. Results saved to training_runs.")

    return all_results


def main():
    """Run Gemini knowledge test."""
    start = time.time()
    client = get_gemini_client()
    try:
        _loop.run_until_complete(_run_all(client))
    finally:
        elapsed = time.time() - start
        print(f"\n  Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
