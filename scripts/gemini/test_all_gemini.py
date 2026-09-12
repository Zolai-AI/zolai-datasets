#!/usr/bin/env python3
"""Real Zolai Knowledge Test — Gemini Model Comparison.

Uses REAL data from zolai.db: dictionary entries, Bible
verses, grammar patterns. Scores Gemini against our DB
on 4 categories with 2 model comparison.

Test Categories:
  A — Dictionary Verification (10 words from bible_zo_en)
  B — Bible Translation ZO→EN (5 verses)
  C — English→Zolai (5 words)
  D — Grammar Recognition (3 sentences)

Usage:
  python3 test_all_gemini.py              # Run all 4 categories, 2 models
  python3 test_all_gemini.py --model flash # Run only gemini-3-flash
"""

import asyncio
import os
import random
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
    "/home/peter/Documents/Projects/zolai-ai",
    "data/zolai.db",
)
MAX_RETRIES = 3
RATE_LIMIT = 2  # seconds between Gemini calls

# ── Persistent event loop ──────────────────────────────
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def _get_client():
    """Lazy-init Gemini client."""
    return get_gemini_client()


# ── Database helpers ───────────────────────────────────
def _query_db(sql: str, params: tuple = ()) -> list:
    """Run a SQL query and return rows as dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _get_dict_words(n: int = 10) -> list:
    """Pick n random high-frequency dictionary words."""
    return _query_db(
        "SELECT zolai, english_clean "
        "FROM dictionary "
        "WHERE source = 'bible_zo_en' "
        "AND english_clean IS NOT NULL "
        "AND LENGTH(zolai) > 2 "
        "AND LENGTH(english_clean) > 1 "
        "AND english_clean NOT LIKE '%[%' "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    )


def _get_bible_verses(n: int = 5) -> list:
    """Pick n random Bible verses for ZO→EN translation."""
    return _query_db(
        "SELECT ref, zo_tdb77, en_kJV "
        "FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND LENGTH(zo_tdb77) > 20 "
        "AND LENGTH(zo_tdb77) < 200 "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    )


def _get_common_english(n: int = 5) -> list:
    """Pick common English words to translate ZO."""
    words = [
        "God", "water", "earth", "man", "woman",
        "child", "king", "house", "day", "night",
        "father", "mother", "brother", "sister",
        "heart", "life", "death", "love", "fear",
        "good", "evil", "great", "small", "new",
    ]
    random.shuffle(words)
    return words[:n]


def _get_grammar_sentences(n: int = 3) -> list:
    """Pick n Bible verses known to have grammar patterns."""
    return _query_db(
        "SELECT ref, zo_tdb77, en_kJV "
        "FROM bible_verses "
        "WHERE zo_tdb77 IS NOT NULL "
        "AND (zo_tdb77 LIKE '%in%' "
        "OR zo_tdb77 LIKE '%kei%' "
        "OR zo_tdb77 LIKE '%hiam%' "
        "OR zo_tdb77 LIKE '%ding%' "
        "OR zo_tdb77 LIKE '%lo%') "
        "AND LENGTH(zo_tdb77) > 15 "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    )


# ── Gemini call with retry ─────────────────────────────
async def _call_gemini(
    client, prompt: str, model: str
) -> tuple:
    """Call Gemini with retry + rate limit."""
    delay = 5  # exponential backoff: 5s, 10s, 20s
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            output = await client.generate_content(
                prompt=prompt, model=model
            )
            elapsed = time.time() - start
            text = output.text or ""
            # Clean elicitation artifacts
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
                return (
                    f"ERROR: {type(e).__name__}: {e}",
                    0,
                )
    return f"ERROR: {last_err}", 0


# ── Scoring functions ──────────────────────────────────
def _score_dict(gemini_answer: str, expected: str) -> int:
    """Score 0-2: exact=2, partial=1, wrong=0."""
    ga = gemini_answer.lower().strip().rstrip(".")
    eb = expected.lower().strip().rstrip(".")
    if ga == eb:
        return 2
    # partial: word overlap
    g_words = set(ga.split())
    e_words = set(eb.split())
    overlap = g_words & e_words
    if overlap:
        return 1
    return 0


def _score_bible(gemini_answer: str, expected: str) -> float:
    """Score 0.0-1.0 by word overlap ratio."""
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
    return round(len(overlap) / len(eb), 2)


# Pattern detection for grammar test
_KNOWN_PATTERNS = {
    "sov": [
        "subject.*verb", "SOV", "subject.*object.*verb",
    ],
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


# ── Category A: Dictionary Verification ────────────────
async def _test_category_a(client, model: str) -> dict:
    """Dictionary Verification — 10 words."""
    words = _get_dict_words(10)

    # Single batch prompt for efficiency
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

    # Parse Gemini answers
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

    # Score each word
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
        "category": "A — Dictionary Verification",
        "model": model,
        "total_score": total,
        "max_score": len(words) * 2,
        "details": details,
        "elapsed": elapsed,
    }


# ── Category B: Bible Translation ZO→EN ───────────────
async def _test_category_b(client, model: str) -> dict:
    """Bible Translation ZO→EN — 5 verses."""
    verses = _get_bible_verses(5)
    results = []
    total_score = 0.0

    for v in verses:
        prompt = (
            "Translate this Zolai (Tedim Chin) sentence "
            "to English:\n"
            f'{v["zo_tdb77"]}\n\n'
            "Reply with ONLY the English translation."
        )
        text, _elapsed = await _call_gemini(
            client, prompt, model
        )
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
        "category": "B — Bible Translation ZO→EN",
        "model": model,
        "total_score": total_score,
        "max_score": len(verses),
        "avg_score": avg,
        "details": results,
        "elapsed": 0,
    }


# ── Category C: English→Zolai ─────────────────────────
async def _test_category_c(client, model: str) -> dict:
    """English→Zolai — 5 words."""
    en_words = _get_common_english(5)
    results = []
    found_in_db = 0

    for word in en_words:
        prompt = (
            "Translate this English word to Zolai "
            "(Tedim Chin):\n"
            f"{word}\n\n"
            "Reply with ONLY the Zolai translation."
        )
        text, _elapsed = await _call_gemini(
            client, prompt, model
        )
        await asyncio.sleep(RATE_LIMIT)

        # Parse Gemini answer
        gemini_zo = text.strip().split("\n")[0].strip()

        # Check if Gemini's answer exists in our DB
        db_match = _query_db(
            "SELECT zolai FROM dictionary "
            "WHERE LOWER(zolai) = LOWER(?) LIMIT 1",
            (gemini_zo,),
        )
        in_db = len(db_match) > 0
        if in_db:
            found_in_db += 1

        # Find our expected Zolai word for this English
        db_en = _query_db(
            "SELECT zolai, english_clean "
            "FROM dictionary "
            "WHERE LOWER(english_clean) LIKE ? "
            "OR LOWER(english) LIKE ? LIMIT 3",
            (f"%{word.lower()}%", f"%{word.lower()}%"),
        )
        expected_zo = (
            db_en[0]["zolai"] if db_en else "(not in DB)"
        )

        results.append({
            "english": word,
            "gemini_zolai": gemini_zo,
            "db_match": in_db,
            "db_expected": expected_zo,
        })

    return {
        "category": "C — English→Zolai",
        "model": model,
        "total_score": found_in_db,
        "max_score": len(en_words),
        "details": results,
        "elapsed": 0,
    }


# ── Category D: Grammar Recognition ───────────────────
async def _test_category_d(client, model: str) -> dict:
    """Grammar Recognition — 3 sentences."""
    sentences = _get_grammar_sentences(3)
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
        text, _elapsed = await _call_gemini(
            client, prompt, model
        )
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
        if sentences
        else 0
    )
    return {
        "category": "D — Grammar Recognition",
        "model": model,
        "total_score": correct_count,
        "max_score": len(sentences),
        "avg_score": avg,
        "details": results,
        "elapsed": 0,
    }


# ── Print results ──────────────────────────────────────
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
            score_bar = "█" * int(d["score"] * 10)
            print(
                f"  │ {d['ref']:10s} "
                f"{d['score']:.0%} {score_bar}"
            )
            print(f"  │   ZO: {d['zolai'][:50]}")
            print(
                f"  │   EN: {d.get('gemini_en', '')[:50]}"
            )
        elif "english" in d:
            icon = "✅" if d.get("db_match") else "❌"
            print(
                f"  │ {icon} {d['english']:10s} "
                f"→ {d['gemini_zolai']:15s} "
                f"[DB: {d['db_expected']}]"
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


# ── Comparison summary table ───────────────────────────
def _print_summary_table(all_results: dict) -> None:
    """Print formatted comparison table."""
    models = list(all_results.keys())
    cats = [
        "A — Dict Verify",
        "B — Bible ZO→EN",
        "C — EN→ZO",
        "D — Grammar",
    ]

    print(f"\n{'=' * 60}")
    print("  MODEL COMPARISON SUMMARY")
    print(f"{'=' * 60}")
    print(
        f"  {'Category':<30} "
        + " ".join(f"{m:<15}" for m in models)
    )
    print(f"  {'-' * 30} " + " ".join("-" * 15 for _ in models))

    for i, cat_name in enumerate(cats):
        scores = []
        for model in models:
            r = all_results[model][i]
            scores.append(f"{r['total_score']}/{r['max_score']}")
        print(
            f"  {cat_name:<30} "
            + " ".join(f"{s:<15}" for s in scores)
        )

    # Averages
    print(f"  {'-' * 30} " + " ".join("-" * 15 for _ in models))
    for model in models:
        avg = sum(
            r["total_score"] for r in all_results[model]
        )
        mx = sum(r["max_score"] for r in all_results[model])
        pct = avg / mx * 100 if mx else 0
        print(
            f"  {'Overall':30s} {model}: "
            f"{avg}/{mx} ({pct:.0f}%)"
        )
    print(f"{'=' * 60}")


# ── Save to training_runs ──────────────────────────────
def _save_results(all_results: dict) -> None:
    """Save test results to training_runs table."""
    import json

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    for model, categories in all_results.items():
        for cat in categories:
            conn.execute(
                "INSERT INTO training_runs "
                "(model_name, dataset_name, entry_count, "
                "metrics_json, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    model,
                    cat["category"],
                    cat["max_score"],
                    json.dumps({
                        "score": cat["total_score"],
                        "max": cat["max_score"],
                        "details": cat["details"],
                    }),
                    "completed",
                ),
            )

    conn.commit()
    conn.close()


# ── Main ───────────────────────────────────────────────
async def _run_all(
    client, models: list
) -> dict:
    """Run all 4 categories on all models."""
    all_results = {}

    for model in models:
        print(f"\n{'=' * 60}")
        print(f"  MODEL: {model}")
        print(f"{'=' * 60}")

        results = []
        # A — Dictionary Verification
        print("  Running A — Dictionary Verification...")
        r = await _test_category_a(client, model)
        results.append(r)
        await asyncio.sleep(RATE_LIMIT)

        # B — Bible Translation
        print("  Running B — Bible Translation ZO→EN...")
        r = await _test_category_b(client, model)
        results.append(r)
        await asyncio.sleep(RATE_LIMIT)

        # C — English→Zolai
        print("  Running C — English→Zolai...")
        r = await _test_category_c(client, model)
        results.append(r)
        await asyncio.sleep(RATE_LIMIT)

        # D — Grammar Recognition
        print("  Running D — Grammar Recognition...")
        r = await _test_category_d(client, model)
        results.append(r)

        all_results[model] = results

        for r in results:
            _print_category(r)

    return all_results


def main():
    """Run Gemini knowledge test."""
    start = time.time()

    print("=" * 60)
    print("  REAL ZOLAI KNOWLEDGE TEST — Gemini Comparison")
    print("=" * 60)
    print("  Data source: zolai.db (dictionary + Bible)")
    print("  Models: gemini-3-flash vs gemini-3-pro-plus")
    print("  Categories: Dict | Bible | EN→ZO | Grammar")
    print("=" * 60)

    client = _get_client()
    models = ["gemini-3-flash", "gemini-3-pro-plus"]

    all_results = _loop.run_until_complete(
        _run_all(client, models)
    )

    # Print comparison table
    _print_summary_table(all_results)

    total_elapsed = time.time() - start
    print(f"\n  Total time: {total_elapsed:.1f}s")
    print(f"{'=' * 60}")

    # Save results
    _save_results(all_results)
    print("  Results saved to training_runs table.")


if __name__ == "__main__":
    main()
