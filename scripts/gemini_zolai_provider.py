#!/usr/bin/env python3
"""Gemini Web Session Zolai Provider — standalone service for pcore-brain.
Runs on port 4080. Provides /translate, /chat, /health endpoints.
Uses browser cookies (no API key needed, bypasses geo-restriction).
"""

import asyncio
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

WEB_API_PATH = '/home/peter/Documents/Project/pcore/pcore-webai/packages/gemini-webapi'
sys.path.insert(0, WEB_API_PATH)

from gemini_webapi import GeminiClient

app = FastAPI(title="Gemini Zolai Provider", version="2.0.0")

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

KEY PATTERNS:
- a u a nau a it = loves his brother (1JN 2:10)
- ute naute a it = love brothers (1PE 2:17)
- Na u a it hi = Love your brother (imperative)

FORBIDDEN (use correct form):
- pathian→pasian; ram→gam; fapa→tapa; bawipa→topa; siangpahrang→kumpipa"""


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "gemini-3-flash"
    glossary: bool = True

class TranslateRequest(BaseModel):
    text: str
    direction: str = "en_to_zo"
    model: str = "gemini-3-flash"
    glossary: bool = True


def clean_response(text: str) -> str:
    if "<ElicitationsGroup" in text:
        text = text[:text.index("<ElicitationsGroup")].strip()
    return text


async def call_gemini(prompt: str, model: str) -> str:
    client = GeminiClient()
    output = await client.generate_content(prompt=prompt, model=model)
    return clean_response(output.text or "")


@app.post("/chat/completions")
async def chat_completions(req: ChatRequest):
    """OpenAI-compatible /chat/completions endpoint."""
    try:
        # Build prompt from messages
        system_parts = []
        user_parts = []
        for msg in req.messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            elif msg.role == "user":
                user_parts.append(msg.content)

        glossary_block = f"{GLOSSARY}\n\n" if req.glossary else ""
        system_block = "\n\n".join(system_parts)
        user_block = "\n\n".join(user_parts)

        prompt = f"{glossary_block}{system_block}\n\n{user_block}" if system_block else f"{glossary_block}{user_block}"

        result = await call_gemini(prompt, req.model)

        return {
            "choices": [{
                "message": {"role": "assistant", "content": result},
                "finish_reason": "stop"
            }],
            "model": req.model,
            "provider": "gemini-web"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate")
async def translate(req: TranslateRequest):
    """Simple translate endpoint."""
    try:
        if req.direction == "en_to_zo":
            prefix = "Translate the following to Tedim Zolai. Reply ONLY with the translation:\n\n"
        else:
            prefix = "Translate the following Zolai text to English. Reply ONLY with the translation:\n\n"

        glossary_block = f"{GLOSSARY}\n\n" if req.glossary else ""
        prompt = f"{glossary_block}{prefix}{req.text}"

        result = await call_gemini(prompt, req.model)
        return {"translation": result, "model": req.model, "provider": "gemini-web"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-3-flash", "provider": "gemini-web", "version": "2.0.0"}


@app.get("/models")
async def models():
    return {"models": [
        "gemini-3-pro", "gemini-3-flash", "gemini-3-flash-thinking",
        "gemini-3-pro-plus", "gemini-3-flash-plus", "gemini-3-flash-thinking-plus",
        "gemini-3-pro-advanced", "gemini-3-flash-advanced", "gemini-3-flash-thinking-advanced"
    ]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4080)
