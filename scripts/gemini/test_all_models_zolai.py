#!/usr/bin/env python3
"""
Benchmark all 9 Gemini models on Zolai→Myanmar translation accuracy.
Tests against known translations from the database.

Usage:
    python test_all_models_zolai.py
    python test_all_models_zolai.py --sample-size 100
    python test_all_models_zolai.py --models gemini-3-flash,gemini-3-pro
"""

import asyncio
import sqlite3
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

from gemini.client_openai import ZolaiGeminiOpenAIClient

DB_PATH = Path(os.environ.get("DATA", "/home/peter/Documents/Projects/zolai-ai/data")) / "zolai.db"
RESULTS_FILE = Path(__file__).parent / "model_benchmark_results.json"

ALL_MODELS = [
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


def get_test_pairs(conn: sqlite3.Connection, limit: int = 100) -> List[Dict]:
    """Get Zolai→Myanmar pairs where Myanmar is already known (ground truth)."""
    cursor = conn.execute("""
        SELECT zolai, english_clean, myanmar
        FROM dictionary
        WHERE myanmar IS NOT NULL AND myanmar != ''
        AND zolai GLOB '[a-z]*'
        AND english_clean IS NOT NULL AND english_clean != ''
        AND is_deleted = 0
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    return [{"zolai": r["zolai"], "english": r["english_clean"],
             "expected": r["myanmar"]} for r in cursor]


async def test_model(client: ZolaiGeminiOpenAIClient, model: str, pairs: List[Dict]) -> Dict:
    """Test a single model on all pairs."""
    correct = 0
    total = len(pairs)
    errors = []
    latencies = []

    for i, pair in enumerate(pairs):
        start = time.time()
        try:
            prompt = f"""Translate this Zolai (Tedim Chin) word to Myanmar/Burmese script.

Zolai: {pair['zolai']}
English: {pair['english']}

Reply with ONLY the Myanmar translation (no explanation, no quotes)."""

            result = await client.ask(model, prompt, use_system_prompt=False)
            predicted = result.strip().strip('"').strip("'")
            latency = time.time() - start
            latencies.append(latency)

            if predicted == pair["expected"]:
                correct += 1
            else:
                errors.append({
                    "zolai": pair["zolai"],
                    "expected": pair["expected"],
                    "predicted": predicted,
                    "english": pair["english"],
                })

            if (i + 1) % 20 == 0:
                print(f"  [{model}] {i+1}/{total} ({correct/(i+1)*100:.0f}% accuracy)")

            await asyncio.sleep(1.5)

        except Exception as e:
            latency = time.time() - start
            latencies.append(latency)
            errors.append({"zolai": pair["zolai"], "error": str(e)})
            await asyncio.sleep(3)

    accuracy = correct / total if total > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return {
        "model": model,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "avg_latency_s": round(avg_latency, 2),
        "errors_count": len(errors),
        "sample_errors": errors[:5],
    }


async def run_benchmark(sample_size: int = 100, models: List[str] = None):
    if models is None:
        models = ALL_MODELS

    conn = sqlite3.connect(str(DB_PATH))
    pairs = get_test_pairs(conn, sample_size)
    conn.close()

    print(f"📋 Benchmark: {len(pairs)} test pairs, {len(models)} models")
    print(f"Models: {', '.join(models)}\n")

    client = ZolaiGeminiOpenAIClient(rate_limit_rpm=10, rate_limit_burst=2)
    await client.init()

    results = []
    try:
        for model in models:
            print(f"\n🧪 Testing {model}...")
            result = await test_model(client, model, pairs)
            results.append(result)
            print(f"  ✅ {model}: {result['accuracy']:.1%} accuracy, "
                  f"{result['avg_latency_s']:.1f}s avg latency")

            # Save intermediate results
            RESULTS_FILE.write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sample_size": len(pairs),
                "results": sorted(results, key=lambda x: x["accuracy"], reverse=True),
            }, indent=2))

    finally:
        await client.close()

    # Final summary
    results.sort(key=lambda x: x["accuracy"], reverse=True)
    print(f"\n{'='*70}")
    print(f"{'MODEL':<40} {'ACCURACY':>10} {'LATENCY':>10}")
    print(f"{'='*70}")
    for r in results:
        print(f"{r['model']:<40} {r['accuracy']:>9.1%} {r['avg_latency_s']:>8.1f}s")
    print(f"{'='*70}")

    # Find best model
    best = results[0]
    print(f"\n🏆 Best model: {best['model']} ({best['accuracy']:.1%})")

    RESULTS_FILE.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(pairs),
        "best_model": best["model"],
        "results": results,
    }, indent=2))
    print(f"\n📄 Results saved to {RESULTS_FILE}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark Gemini models on Zolai translation")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--models", type=str, default=None, help="Comma-separated model list")
    args = parser.parse_args()

    models = args.models.split(",") if args.models else None
    await run_benchmark(args.sample_size, models)

if __name__ == "__main__":
    asyncio.run(main())
