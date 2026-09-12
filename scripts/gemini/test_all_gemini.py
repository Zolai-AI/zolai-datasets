"""Test ALL Gemini models — raw Zolai knowledge comparison.

Uses retry with exponential backoff and proper error reporting.
"""
import asyncio
import sys
import time

sys.path.insert(
    0,
    "/home/peter/Documents/Project/pcore/"
    "pcore-webai/packages/gemini-webapi",
)
from gemini_webapi import GeminiClient

PROMPT = (
    "Translate to Zolai (Tedim Chin language, "
    "spoken in Myanmar/India).\n"
    "Reply ONLY with numbered translations, "
    "no explanations:\n"
    "1. He went.\n"
    "2. They went.\n"
    "3. Do you eat?\n"
    "4. They are very good.\n"
    "5. Be healed.\n"
    "6. The work is done.\n"
    "7. He has seen it.\n"
    "8. The elder brother is good.\n"
    "9. The younger sister sings.\n"
    "10. They love their brother.\n"
    "11. They love their brothers.\n"
    "12. Love your brother."
)

MODELS = [
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-3-flash-thinking",
    "gemini-3-pro-plus",
    "gemini-3-flash-plus",
    "gemini-3-flash-thinking-plus",
    "gemini-3-pro-advanced",
    "gemini-3-flash-advanced",
    "gemini-3-flash-thinking-advanced",
]

MAX_RETRIES = 3
RETRY_DELAY = 3  # seconds


async def test_model(model):
    """Test a single Gemini model with retry."""
    client = GeminiClient()
    delay = RETRY_DELAY
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            output = await client.generate_content(
                prompt=PROMPT, model=model
            )
            elapsed = time.time() - start
            text = output.text or ""
            if "<ElicitationsGroup" in text:
                text = text[
                    : text.index("<ElicitationsGroup")
                ].strip()
            return text, elapsed
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                print(
                    f"    Retry {attempt}/{MAX_RETRIES} "
                    f"after {delay}s: {e}",
                    file=sys.stderr,
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                return (
                    f"ERROR after {MAX_RETRIES} attempts: "
                    f"{type(e).__name__}: {e}",
                    0,
                )
    return f"ERROR: {last_err}", 0


async def main():
    results = {}
    timings = {}
    total_start = time.time()

    print("=" * 60)
    print("GEMINI MODEL COMPARISON — Zolai Translation")
    print("=" * 60)
    print(f"Testing {len(MODELS)} models...\n")

    for model in MODELS:
        print(f"\n{'=' * 60}")
        print(f"MODEL: {model}")
        print(f"{'=' * 60}")
        text, elapsed = await test_model(model)
        results[model] = text
        timings[model] = elapsed
        status = "OK" if not text.startswith("ERROR") else "FAIL"
        print(f"  Status: {status} ({elapsed:.1f}s)")
        print(text)

    # Summary comparison table
    total_elapsed = time.time() - total_start
    print(f"\n\n{'=' * 60}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 60}")

    # Table header
    print(
        f"\n{'Model':<35} {'Status':<8} {'Time':<8}"
    )
    print("-" * 55)
    for model in MODELS:
        result = results[model]
        elapsed = timings[model]
        status = (
            "OK"
            if not result.startswith("ERROR")
            else "FAIL"
        )
        print(
            f"{model:<35} {status:<8} {elapsed:<7.1f}s"
        )

    # Show side-by-side translations for each model
    print(f"\n\n{'=' * 60}")
    print("DETAILED TRANSLATIONS")
    print(f"{'=' * 60}")
    for model in MODELS:
        lines = results[model].strip().split("\n")
        print(f"\n--- {model} ---")
        for line in lines[:14]:
            print(f"  {line}")

    print(f"\nTotal time: {total_elapsed:.1f}s")
    working = sum(
        1 for r in results.values()
        if not r.startswith("ERROR")
    )
    print(
        f"Models working: {working}/{len(MODELS)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
