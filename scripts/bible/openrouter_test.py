#!/usr/bin/env python3
"""OpenRouter Zolai Grammar Test — rate-limited, all free models, multiple categories.

Usage:
    python3 openrouter_test.py                     # Quick test (1 question, all models)
    python3 openrouter_test.py --full               # Full test (all questions, all models)
    python3 openrouter_test.py --model nex-agi/nex-n2.5-pro:free   # Single model
    python3 openrouter_test.py --category negation  # Single category
    python3 openrouter_test.py --list               # List all free models
    python3 openrouter_test.py --external           # Test models OUTSIDE Zolai knowledge
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            import os
            os.environ.setdefault("OPENROUTER_API_KEY", line.split("=", 1)[1])

API_KEY = __import__("os").environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rate limits: 20 req/min per free model
DELAY = 3.5          # seconds between requests (60/18 ≈ 3.33, rounded up)
TIMEOUT = 30         # seconds per request
MAX_RETRIES = 3
RETRY_WAIT = 65      # seconds after 429

# ── System Prompt ───────────────────────────────────────────────────────────

ZOLAI_SYSTEM = """You are a Zolai language expert for Tedim Zolai (ZVS 2018).

PRONOUNS: ka=I, na=you, a=he/she (agreement marker before verb), amah=emphatic standalone, amau/amaute=they, ki=we.
VERBS: pai=go, mu=see, ne=eat, dawn=drink, thei=know, bawl=create, om=exist, ci=say, tapa=life, topa=Lord.
NEGATION: kei before verb for ALL persons. Correct: Ka pai kei hi. NEVER use si.
QUESTIONS: hiam at end. Correct: Na pai hiam? NEVER use ze as question.
FUTURE: ding after verb. Correct: Ka pai ding hi. NEVER use dang.
PRESENT: hi at end. Correct: Ka pai hi. NEVER use di.
SOV word order: Subject-Object-Verb.
EMPHATIC: Amah a pai hi = HE goes (emphatic). A pai hi = He goes (normal).
FORBIDDEN: pathian->pasian, ram->gam, fapa->tapa, bawipa->topa, siangpahrang->kumpipa, cu/cun->tua.
ANSWER WITH ONLY THE ZOLAI SENTENCE."""

EXTERNAL_SYSTEM = """You are a helpful multilingual assistant. Answer accurately in the language or topic asked about."""

# ── Models ──────────────────────────────────────────────────────────────────

ALL_FREE_MODELS = [
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron Ultra 550B", "ctx": "1M", "size": "550B"},
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron Super 120B", "ctx": "262K", "size": "120B"},
    {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "name": "Nemotron Nano 30B", "ctx": "256K", "size": "30B"},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning", "ctx": "1M", "size": "large"},
    {"id": "nvidia/nemotron-3.5-content-safety:free", "name": "Nemotron 3.5 Safety", "ctx": "128K", "size": "medium"},
    {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "ctx": "262K", "size": "31B"},
    {"id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B", "ctx": "262K", "size": "26B"},
    {"id": "nex-agi/nex-n2.5-pro:free", "name": "NEX N2.5 Pro", "ctx": "262K", "size": "pro"},
    {"id": "nex-agi/nex-n2.5-mini:free", "name": "NEX N2.5 Mini", "ctx": "262K", "size": "mini"},
    {"id": "thinkingmachines/inkling:free", "name": "Inkling", "ctx": "1M", "size": "large"},
    {"id": "thinkingmachines/inkling-small:free", "name": "Inkling Small", "ctx": "1M", "size": "small"},
    {"id": "poolside/laguna-s-2.1:free", "name": "Laguna S 2.1", "ctx": "262K", "size": "S"},
    {"id": "poolside/laguna-xs-2.1:free", "name": "Laguna XS 2.1", "ctx": "262K", "size": "XS"},
    {"id": "cohere/north-mini-code:free", "name": "North Mini Code", "ctx": "256K", "size": "mini"},
    {"id": "liquid/lfm-2.5-2.6b:free", "name": "LFM 2.5 2.6B", "ctx": "65K", "size": "2.6B"},
    {"id": "inclusionai/ling-3.0-flash-sante:free", "name": "Ling 3.0 Sante", "ctx": "262K", "size": "flash"},
    {"id": "inclusionai/ling-3.0-flash-fin:free", "name": "Ling 3.0 Fin", "ctx": "262K", "size": "flash"},
    {"id": "dots-studio/dots-3-note-preview:free", "name": "Dots 3 Note", "ctx": "512K", "size": "note"},
]

# ── Test Cases ──────────────────────────────────────────────────────────────

ZOLAI_TESTS = {
    "negation": [
        ("Say I dont go in Zolai:", ["ka", "pai", "kei"], "Ka pai kei hi."),
        ("Say You dont go in Zolai:", ["na", "pai", "kei"], "Na pai kei hi."),
        ("Say He doesnt go in Zolai:", ["a", "pai", "kei"], "A pai kei hi."),
        ("Say They dont go in Zolai:", ["amau", "pai", "kei"], "Amau pai kei hi."),
        ("Say I dont eat in Zolai:", ["ka", "ne", "kei"], "Ka ne kei hi."),
        ("Say I dont see in Zolai:", ["ka", "mu", "kei"], "Ka mu kei hi."),
        ("Say I wont go in Zolai:", ["ka", "pai", "kei", "ding"], "Ka pai kei ding."),
        ("Say You wont eat in Zolai:", ["na", "ne", "kei", "ding"], "Na ne kei ding."),
    ],
    "questions": [
        ("Say Do you go? in Zolai:", ["na", "pai", "hiam"], "Na pai hiam?"),
        ("Say Do you eat? in Zolai:", ["na", "ne", "hiam"], "Na ne hiam?"),
        ("Say Does he go? in Zolai:", ["a", "pai", "hiam"], "A pai hiam?"),
        ("Say Do they go? in Zolai:", ["amau", "pai", "hiam"], "Amau pai hiam?"),
        ("Say Will you go? in Zolai:", ["na", "pai", "ding", "hiam"], "Na pai ding hiam?"),
        ("Say Do you know? in Zolai:", ["na", "thei", "hiam"], "Na thei hiam?"),
    ],
    "future": [
        ("Say I will go in Zolai:", ["ka", "pai", "ding"], "Ka pai ding hi."),
        ("Say You will go in Zolai:", ["na", "pai", "ding"], "Na pai ding hi."),
        ("Say He will go in Zolai:", ["a", "pai", "ding"], "A pai ding hi."),
        ("Say I will eat in Zolai:", ["ka", "ne", "ding"], "Ka ne ding hi."),
        ("Say I will see in Zolai:", ["ka", "mu", "ding"], "Ka mu ding hi."),
        ("Say I will drink in Zolai:", ["ka", "dawn", "ding"], "Ka dawn ding hi."),
    ],
    "present": [
        ("Say I go in Zolai:", ["ka", "pai", "hi"], "Ka pai hi."),
        ("Say You go in Zolai:", ["na", "pai", "hi"], "Na pai hi."),
        ("Say He goes in Zolai:", ["a", "pai", "hi"], "A pai hi."),
        ("Say I eat in Zolai:", ["ka", "ne", "hi"], "Ka ne hi."),
        ("Say I see in Zolai:", ["ka", "mu", "hi"], "Ka mu hi."),
        ("Say I drink in Zolai:", ["ka", "dawn", "hi"], "Ka dawn hi."),
    ],
    "emphatic": [
        ("Say HE goes (emphatic) in Zolai:", ["amah", "a", "pai"], "Amah a pai hi."),
        ("Say HE doesnt go (emphatic) in Zolai:", ["amah", "a", "pai", "kei"], "Amah a pai kei hi."),
        ("Say SHE goes (emphatic) in Zolai:", ["amah", "a", "pai"], "Amah a pai hi."),
        ("Say SHE doesnt go (emphatic) in Zolai:", ["amah", "a", "pai", "kei"], "Amah a pai kei hi."),
    ],
    "vocabulary": [
        ("What is God in Zolai? One word:", ["pasian"], "Pasian"),
        ("What is land/earth in Zolai? One word:", ["gam"], "Gam"),
        ("What is Lord in Zolai? One word:", ["topa"], "Topa"),
        ("What is life in Zolai? One word:", ["tapa"], "Tapa"),
        ("What is the negation particle in Zolai?", ["kei"], "Kei"),
        ("What does ze mean in Zolai?", ["emphasis", "playful", "emphatic", "not.*question"], "Emphatic marker"),
        ("What does hiam mean in Zolai?", ["question"], "Question marker"),
        ("Say I see the land in Zolai:", ["ka", "gam", "mu"], "Ka gam mu hi."),
        ("Say You drink water in Zolai:", ["na", "tui", "dawn"], "Na tui dawn hi."),
    ],
}

# External knowledge tests (NOT Zolai-specific — tests general model ability)
EXTERNAL_TESTS = [
    ("What is the capital of France?", ["paris"], "Paris"),
    ("What is 2 + 2?", ["4"], "4"),
    ("Translate hello to Spanish:", ["hola"], "Hola"),
    ("What planet is closest to the sun?", ["mercury"], "Mercury"),
    ("Who wrote Romeo and Juliet?", ["shakespeare"], "Shakespeare"),
    ("What is the chemical symbol for water?", ["h2o"], "H2O"),
    ("How many continents are there?", ["7", "seven"], "7"),
    ("What language is spoken in Brazil?", ["portuguese"], "Portuguese"),
]


# ── API Call ────────────────────────────────────────────────────────────────

def call_openrouter(
    model: str,
    system: str,
    user_msg: str,
    max_tokens: int = 100,
    temperature: float = 0.0,
) -> tuple[str, int, str]:
    """Call OpenRouter with retry + rate limit handling.
    Returns (answer, elapsed_ms, error_or_empty).
    """
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            BASE_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"].strip()
                elapsed = int((time.time() - start) * 1000)
                return content, elapsed, ""
        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - start) * 1000)
            if e.code == 429:
                print(f"    ⏳ Rate limited (429). Waiting {RETRY_WAIT}s...")
                time.sleep(RETRY_WAIT)
                continue
            elif e.code == 402:
                return "QUOTA_EXCEEDED", elapsed, "402: Daily quota exceeded"
            else:
                body = e.read().decode()[:200] if hasattr(e, "read") else ""
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)
                    continue
                return "ERROR", elapsed, f"{e.code}: {body}"
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            if attempt < MAX_RETRIES - 1:
                time.sleep(3)
                continue
            return "TIMEOUT", elapsed, str(e)[:100]

    return "MAX_RETRIES", 0, "Exceeded max retries"


def check_keywords(answer: str, keywords: list[str]) -> bool:
    """Check if answer contains all required keywords (case-insensitive)."""
    low = answer.lower()
    for kw in keywords:
        if not re.search(kw.lower(), low):
            return False
    return True


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_list():
    """List all free models."""
    print(f"{'#':<4} {'Model ID':<55} {'Name':<25} {'Ctx':>6}  {'Size'}")
    print("-" * 105)
    for i, m in enumerate(ALL_FREE_MODELS, 1):
        print(f"{i:<4} {m['id']:<55} {m['name']:<25} {m['ctx']:>6}  {m['size']}")


def cmd_quick(model_filter: str | None = None):
    """Quick test — 1 question per model, speed + accuracy."""
    models = ALL_FREE_MODELS
    if model_filter:
        models = [m for m in models if model_filter in m["id"]]

    test_q = "Say I dont go in Zolai."
    print(f"Quick test: \"{test_q}\"")
    print(f"Expected: Ka pai kei hi.")
    print(f"Models: {len(models)} | Delay: {DELAY}s between requests")
    print()
    print(f"{'S':<4} {'Model':<42} {'Time':>7}  Answer")
    print("-" * 110)

    for i, m in enumerate(models):
        if i > 0:
            time.sleep(DELAY)

        content, elapsed, err = call_openrouter(m["id"], ZOLAI_SYSTEM, test_q)

        cl = content.lower()
        ok = "kei" in cl and "pai" in cl and " si " not in cl and "kal" not in cl
        mark = "✅" if ok else ("⏰" if "TIMEOUT" in content or "ERROR" in content else "❌")

        short = m["id"].split("/")[-1].replace(":free", "")
        print(f"{mark:<4} {short:<42} {elapsed:>5}ms  {content[:80]}")

    print(f"\nDone. Used {len(models)} of ~200 daily free quota.")


def cmd_full(model_filter: str | None = None, category: str | None = None):
    """Full test — all questions, all models, detailed report."""
    models = ALL_FREE_MODELS
    if model_filter:
        models = [m for m in models if model_filter in m["id"]]

    tests = ZOLAI_TESTS
    if category:
        tests = {category: tests.get(category, [])}
        if not tests[category]:
            print(f"Unknown category: {category}")
            print(f"Available: {', '.join(ZOLAI_TESTS.keys())}")
            return

    total_q = sum(len(v) for v in tests.values())
    total_requests = len(models) * total_q
    est_time = total_requests * (DELAY + 5) / 60  # minutes

    print(f"Full Zolai Grammar Test")
    print(f"Models: {len(models)} | Questions per model: {total_q} | Total requests: {total_requests}")
    print(f"Estimated time: {est_time:.0f} minutes")
    print(f"Delay: {DELAY}s between requests")
    print()

    # Check daily quota
    if total_requests > 180:
        print(f"⚠️  WARNING: {total_requests} requests exceeds 180/day free quota!")
        print(f"   Consider: --model <specific_model> or --category <specific_category>")
        print()

    all_results = []

    for m in models:
        print(f"\n{'='*80}")
        print(f"Model: {m['name']} ({m['id']})")
        print(f"{'='*80}")

        model_pass = 0
        model_total = 0

        for cat, cases in tests.items():
            print(f"\n  [{cat}]")
            for q, keywords, expected in cases:
                time.sleep(DELAY)
                content, elapsed, err = call_openrouter(m["id"], ZOLAI_SYSTEM, q)

                passed = check_keywords(content, keywords)
                mark = "✅" if passed else ("⏰" if "TIMEOUT" in content or "ERROR" in content else "❌")

                print(f"    {mark} Q: {q}")
                print(f"       A: {content[:100]}")
                if not passed and err:
                    print(f"       ERR: {err}")

                model_total += 1
                if passed:
                    model_pass += 1

                all_results.append({
                    "model": m["id"],
                    "category": cat,
                    "question": q,
                    "answer": content,
                    "expected": expected,
                    "passed": passed,
                    "ms": elapsed,
                })

        acc = (model_pass / model_total * 100) if model_total > 0 else 0
        print(f"\n  RESULT: {model_pass}/{model_total} ({acc:.0f}%)")

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    by_model = {}
    for r in all_results:
        mid = r["model"].split("/")[-1].replace(":free", "")
        if mid not in by_model:
            by_model[mid] = {"pass": 0, "total": 0}
        by_model[mid]["total"] += 1
        if r["passed"]:
            by_model[mid]["pass"] += 1

    print(f"{'Model':<42} {'Pass':>5} {'Total':>6} {'Acc':>6}")
    print("-" * 65)
    for mid, s in sorted(by_model.items(), key=lambda x: -x[1]["pass"]):
        acc = s["pass"] / s["total"] * 100 if s["total"] > 0 else 0
        print(f"{mid:<42} {s['pass']:>5} {s['total']:>6} {acc:>5.0f}%")

    # Save results
    report_path = Path(__file__).resolve().parents[3] / "report" / "openrouter_eval.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nResults saved to: {report_path}")


def cmd_external(model_filter: str | None = None):
    """Test models OUTSIDE Zolai knowledge — general capability."""
    models = ALL_FREE_MODELS
    if model_filter:
        models = [m for m in models if model_filter in m["id"]]

    print(f"External Knowledge Test (NOT Zolai-specific)")
    print(f"Models: {len(models)} | Questions: {len(EXTERNAL_TESTS)} | Delay: {DELAY}s")
    print()

    for m in models:
        print(f"\n  {m['name']} ({m['id']})")
        model_pass = 0
        for q, keywords, expected in EXTERNAL_TESTS:
            time.sleep(DELAY)
            content, elapsed, err = call_openrouter(m["id"], EXTERNAL_SYSTEM, q)
            passed = check_keywords(content, keywords)
            mark = "✅" if passed else "❌"
            short_q = q[:50]
            print(f"    {mark} {short_q:<52} → {content[:60]}")
            if passed:
                model_pass += 1
        acc = model_pass / len(EXTERNAL_TESTS) * 100
        print(f"    Score: {model_pass}/{len(EXTERNAL_TESTS)} ({acc:.0f}%)")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenRouter Zolai Grammar Test")
    parser.add_argument("--list", action="store_true", help="List all free models")
    parser.add_argument("--quick", action="store_true", help="Quick test (1 question per model)")
    parser.add_argument("--full", action="store_true", help="Full test (all questions)")
    parser.add_argument("--external", action="store_true", help="Test outside Zolai knowledge")
    parser.add_argument("--model", type=str, default=None, help="Filter by model ID substring")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: No OPENROUTER_API_KEY found. Set it in .env or environment.")
        sys.exit(1)

    if args.list:
        cmd_list()
    elif args.external:
        cmd_external(args.model)
    elif args.full:
        cmd_full(args.model, args.category)
    else:
        cmd_quick(args.model)


if __name__ == "__main__":
    main()
