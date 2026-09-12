# Path setup for gemini_cookies import
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIBLE_DIR = os.path.join(SCRIPT_DIR, "bible")
if BIBLE_DIR not in sys.path: sys.path.insert(0, BIBLE_DIR)
#!/usr/bin/env python3
"""Fast local Gemini Zolai translator using browser cookies.
Usage: python3 gemini_zolai.py "English text to translate"
       python3 gemini_zolai.py --zo "Zolai text to translate"
"""

import asyncio
import sys





from gemini_cookies import get_gemini_client

GLOSSARY = """Tedim Zolai (ZVS 2018) Translation Rules:

GRAMMAR:
- Word order: Subject-Object-Verb (SOV)
- Agreement markers (ka/na/a) ALWAYS directly before verb
- Adverbs (mahmah) AFTER adjective, BEFORE hi
- Negation: kei (all persons); lo (literary, standalone, NO agreement)
- Questions: hiam (formal), hia (informal) — yes/no at end; bang hang (content question)
- Past simple: khin; Completive: ta; Future: ding; Progressive: lai

PRONOUNS:
- hihte=they (respectful, 146x Bible); amaute=they (standard, 3549x); huate=those/them (36x)
- u=elder brother/sister; nau=younger brother/sister
- sanggam=brother/companion (560x Bible); sanggampa=his brother (217x); sanggamte=brothers (214x)
- uh=plural marker ONLY (NOT standalone "they")

VOCABULARY:
- pasian=God; topa=Lord; tapa=son/life; gam=earth; vantung=heaven
- it=love (verb); itna=love (noun); ki-it=love each other
- ne=eat (general); nek=eat (specific/conditional)
- nasep=work/service; kammal=deed/commandment
- lasak=sing OR take something (polysemous)
- singkung=tree (living); sing=wood (material)
- mankhin=truly/completed; kiman=finished; hoit/siam=good

KEY PATTERNS:
- a u a nau a it = loves his brother (1JN 2:10)
- ute naute a it = love brothers (1PE 2:17)
- Na u a it hi = Love your brother (imperative)
- An na ne hia? = Do you eat? (informal)
- An na ne hiam? = Do you eat? (formal)

FORBIDDEN (use correct form):
- pathian→pasian; ram→gam; fapa→tapa; bawipa→topa; siangpahrang→kumpipa"""


async def translate(text: str, direction: str = "en_to_zo") -> str:
    client = get_gemini_client()
    
    if direction == "en_to_zo":
        prompt = f"{GLOSSARY}\n\nTranslate to Tedim Zolai. Reply ONLY with translation:\n\n{text}"
    else:
        prompt = f"Translate Zolai to English. Reply ONLY with translation:\n\n{text}"
    
    output = await client.generate_content(
        prompt=prompt,
        model="gemini-3-flash"
    )
    
    result = output.text or ""
    if "<ElicitationsGroup" in result:
        result = result[:result.index("<ElicitationsGroup")].strip()
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 gemini_zolai.py 'text to translate'")
        print("       python3 gemini_zolai.py --zo 'Zolai text to translate'")
        sys.exit(1)
    
    if sys.argv[1] == "--zo":
        text = sys.argv[2]
        direction = "zo_to_en"
    else:
        text = sys.argv[1]
        direction = "en_to_zo"
    
    result = asyncio.run(translate(text, direction))
    print(result)
