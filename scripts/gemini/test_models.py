import sys, os, asyncio
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath('/tmp/test_models.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client

GLOSSARY = """Tedim Zolai (ZVS 2018) Translation Rules:

GRAMMAR:
- Word order: Subject-Object-Verb (SOV)
- Agreement markers (ka/na/a) ALWAYS directly before verb
- Adverbs (mahmah) AFTER adjective, BEFORE hi
- Negation: kei (all persons); lo (literary, standalone, NO agreement)
- Questions: hiam (formal), hia (informal); bang hang (content question)
- Past simple: khin; Completive: ta; Future: ding; Progressive: lai

PRONOUNS:
- hihte=they (respectful); amaute=they (standard); huate=those/them
- u=elder brother/sister; nau=younger brother/sister
- sanggam=brother/companion (560x Bible); sanggampa=his brother; sanggamte=brothers (214x)
- uh=plural marker ONLY (NOT standalone "they")

VOCABULARY:
- pasian=God; topa=Lord; tapa=son/life; gam=earth; vantung=heaven
- it=love (verb); itna=love (noun); ki-it=love each other
- ne=eat (general); nek=eat (specific/conditional)
- nasep=work/service; kammal=deed/commandment
- lasak=sing OR take something (polysemous)
- singkung=tree (living); sing=wood (material)
- mankhin=truly/completed; kiman=finished; siam=good

FORBIDDEN (use correct form):
- pathian→pasian; ram→gam; fapa→tapa; bawipa→topa; siangpahrang→kumpipa"""

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

async def test_model(model, with_glossary=False):
    try:
        client = get_gemini_client()
        prompt = f"{GLOSSARY}\n\n{PROMPT}" if with_glossary else PROMPT
        output = await client.generate_content(prompt=prompt, model=model)
        text = output.text or ""
        if "<ElicitationsGroup" in text:
            text = text[:text.index("<ElicitationsGroup")].strip()
        # Clean up section tags
        text = re.sub(r'<Section.*?</Section>', '', text, flags=re.DOTALL)
        text = re.sub(r'<TextBox.*?>', '', text, flags=re.DOTALL)
        text = re.sub(r'</TextBox>', '', text, flags=re.DOTALL)
        text = text.strip()
        return text
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

async def main():
    models = ["gemini-3-flash", "gemini-3-pro-plus"]
    for model in models:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")
        result = await test_model(model, with_glossary=True)
        print(result)
        print()

asyncio.run(main())
