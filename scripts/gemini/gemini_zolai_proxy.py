"""Gemini Web Session Proxy for Zolai Translation.
Uses browser cookies to access Gemini web (bypasses geo-restriction).
Pcore-brain routes Zolai translations through this when called.
"""

import sys
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, '/home/peter/Documents/Project/pcore/pcore-webai/packages/gemini-webapi')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-zolai-proxy")

app = FastAPI(title="Gemini Zolai Proxy", version="1.0.0")

GLOSSARY = """Tedim Zolai (ZVS 2018) Translation Rules:

GRAMMAR:
- Word order: Subject-Object-Verb (SOV)
- Agreement markers (ka/na/a) ALWAYS directly before verb
- Adverbs (mahmah) AFTER adjective, BEFORE hi
- Negation: kei (all persons); lo (literary, standalone, NO agreement)
- Questions: hiam=formal, hia=informal (yes/no question marker); bang hang (content question)
- Past simple: khin; Completive: ta; Future: ding; Progressive: lai

PRONOUNS:
- hihte=they (respectful, 146x Bible); amaute=they (standard, 3549x); huate=those/them (36x)
- u=elder brother/sister (NOT "they"); nau=younger brother/sister
- uh=plural marker ONLY (NOT standalone "they")

VOCABULARY:
- pasian=God; topa=Lord; tapa=son/life; gam=earth; vantung=heaven
- it=love (verb); itna=love (noun); ki-it=love each other
- ne=eat (general); nek=eat (specific/conditional)
- nasep=work/service; kammal=deed/commandment
- lasak=sing OR take something (polysemous)
- singkung=tree (living); sing=wood (material)
- mankhin=truly/completed; kiman=finished

KEY PATTERNS:
- a u a nau a it = loves his brother (1JN 2:10)
- ute naute a it = love brothers (1PE 2:17)
- Na u a it hi = Love your brother (imperative)

FORBIDDEN (use correct form):
- pathian→pasian; ram→gam; fapa→tapa; bawipa→topa; siangpahrang→kumpipa"""


class TranslationRequest(BaseModel):
    text: str
    direction: str = "en_to_zo"  # en_to_zo or zo_to_en


class TranslationResponse(BaseModel):
    translation: str
    model: str = "gemini-3-flash"
    source: str = "gemini-web"


@app.post("/translate", response_model=TranslationResponse)
async def translate(req: TranslationRequest):
    """Translate text using Gemini web session with Zolai glossary."""
    try:
        from gemini_webapi import GeminiClient
        
        client = GeminiClient()
        
        if req.direction == "en_to_zo":
            prompt = f"{GLOSSARY}\n\nTranslate the following to Tedim Zolai. Reply ONLY with the translation, no explanations:\n\n{req.text}"
        else:
            prompt = f"Translate the following Zolai text to English. Reply ONLY with the English translation:\n\n{req.text}"
        
        output = await client.generate_content(
            prompt=prompt,
            model="gemini-3-flash"
        )
        
        # Clean response - remove elicitation XML
        text = output.text or ""
        if "<ElicitationsGroup" in text:
            text = text[:text.index("<ElicitationsGroup")].strip()
        
        return TranslationResponse(translation=text)
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-3-flash", "source": "gemini-web"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4080)
