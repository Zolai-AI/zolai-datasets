"""Test ALL Gemini models WITHOUT glossary — raw Zolai knowledge comparison."""
import asyncio
import sys
sys.path.insert(0, '/home/peter/Documents/Project/pcore/pcore-webai/packages/gemini-webapi')
from gemini_webapi import GeminiClient

PROMPT = """Translate to Zolai (Tedim Chin language, spoken in Myanmar/India).
Reply ONLY with numbered translations, no explanations:
1. He went.
2. They went.
3. Do you eat?
4. They are very good.
5. Be healed.
6. The work is done.
7. He has seen it.
8. The elder brother is good.
9. The younger sister sings.
10. They love their brother.
11. They love their brothers.
12. Love your brother."""

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

async def test_model(model):
    try:
        client = GeminiClient()
        output = await client.generate_content(prompt=PROMPT, model=model)
        text = output.text or ""
        if "<ElicitationsGroup" in text:
            text = text[:text.index("<ElicitationsGroup")].strip()
        return text
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

async def main():
    results = {}
    for model in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")
        result = await test_model(model)
        print(result)
        results[model] = result

    # Summary comparison
    print(f"\n\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    for model, result in results.items():
        lines = result.strip().split('\n')
        print(f"\n--- {model} ---")
        for line in lines[:12]:
            print(f"  {line}")

asyncio.run(main())
