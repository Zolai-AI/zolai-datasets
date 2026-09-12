import sys, os, asyncio
SCRIPT_DIR = os.path.dirname(os.path.abspath('/tmp/test_gemini3.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)
from gemini_cookies import get_gemini_client

async def test_single():
    client = get_gemini_client()
    tests = [
        ('They love their brother', False),  # without glossary
        ('I went', False),
        ('Do you eat?', False),
        ('Be healed', False),
    ]
    for t, with_glossary in tests:
        prompt = f"{GLOSSARY}\n\nTranslate to Tedim Zolai. Reply ONLY with the translation:\n\n{t}" if with_glossary else f"Translate to Tedim Zolai. Reply ONLY with the translation:\n\n{t}"
        output = await client.generate_content(prompt=t, model='gemini-3-flash')
        text = output.text or ''
        if '<ElicitationsGroup' in text:
            text = text[:text.index('<ElicitationsGroup')].strip()
        # Also strip section tags
        import re
        text = re.sub(r'<Section.*?</Section>', '', text, flags=re.DOTALL)
        text = re.sub(r'<TextBox.*?>', '', text, flags=re.DOTALL)
        text = re.sub(r'</TextBox>', '', text, flags=re.DOTALL)
        text = text.strip()
        print(f'WITH_GLOSSARY={with_glossary}: {t} → {text}')

GLOSSARY = """Tedim Zolai (ZVS 2018) Translation Rules:"""

asyncio.run(test_single())
