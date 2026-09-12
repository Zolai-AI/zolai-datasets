import sys, os, asyncio
SCRIPT_DIR = os.path.dirname(os.path.abspath('/tmp/test_gemini.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)
from gemini_cookies import get_gemini_client

async def test_single():
    client = get_gemini_client()
    output = await client.generate_content(
        prompt='Translate to Tedim Zolai. Reply ONLY with the translation: He went.',
        model='gemini-3-flash'
    )
    text = output.text or ''
    if '<ElicitationsGroup' in text:
        text = text[:text.index('<ElicitationsGroup')].strip()
    print('RESULT:', text)

asyncio.run(test_single())
