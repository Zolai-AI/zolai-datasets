import sys, os, asyncio
SCRIPT_DIR = os.path.dirname(os.path.abspath('/tmp/test_gemini2.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)
from gemini_cookies import get_gemini_client

async def test_single():
    client = get_gemini_client()
    tests = [
        'Translate to Tedim Zolai. Reply ONLY with the translation: They love their brother.',
        'Translate to Tedim Zolai. Reply ONLY with the translation: I went.',
        'Translate to Tedim Zolai. Reply ONLY with the translation: Do you eat?',
        'Translate to Tedim Zolai. Reply ONLY with the translation: Be healed.',
    ]
    for t in tests:
        output = await client.generate_content(prompt=t, model='gemini-3-flash')
        text = output.text or ''
        if '<ElicitationsGroup' in text:
            text = text[:text.index('<ElicitationsGroup')].strip()
        print(f'PROMPT: {t[:40]}...')
        print(f'RESULT: {text}')
        print()

asyncio.run(test_single())
