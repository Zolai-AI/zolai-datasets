"""OpenRouter configuration for Zolai grammar testing."""
import os
from pathlib import Path

# Load key from .env
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            os.environ.setdefault("OPENROUTER_API_KEY", line.split("=", 1)[1])

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rate limits for free models (OpenRouter docs)
# Free models: 20 requests/min, 200 requests/day per model
RATE_LIMIT = {
    "requests_per_minute": 18,   # Stay under 20
    "requests_per_day": 180,     # Stay under 200
    "delay_between_requests": 3.5,  # seconds (60/18 = 3.33, round up)
    "retry_after_429": 60,       # seconds to wait after 429
    "max_retries": 3,
    "timeout": 30,               # seconds per request
}

# All free models available on OpenRouter
FREE_MODELS = [
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron Ultra 550B", "ctx": 1_000_000, "size": "550B"},
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron Super 120B", "ctx": 262_144, "size": "120B"},
    {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "name": "Nemotron Nano 30B", "ctx": 256_000, "size": "30B"},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning", "ctx": 1_000_000, "size": "large"},
    {"id": "nvidia/nemotron-3.5-content-safety:free", "name": "Nemotron 3.5 Safety", "ctx": 128_000, "size": "medium"},
    {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "ctx": 262_144, "size": "31B"},
    {"id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B", "ctx": 262_144, "size": "26B"},
    {"id": "nex-agi/nex-n2.5-pro:free", "name": "NEX N2.5 Pro", "ctx": 262_144, "size": "pro"},
    {"id": "nex-agi/nex-n2.5-mini:free", "name": "NEX N2.5 Mini", "ctx": 262_144, "size": "mini"},
    {"id": "thinkingmachines/inkling:free", "name": "Inkling", "ctx": 1_048_576, "size": "large"},
    {"id": "thinkingmachines/inkling-small:free", "name": "Inkling Small", "ctx": 1_048_576, "size": "small"},
    {"id": "poolside/laguna-s-2.1:free", "name": "Laguna S 2.1", "ctx": 262_144, "size": "s"},
    {"id": "poolside/laguna-xs-2.1:free", "name": "Laguna XS 2.1", "ctx": 262_144, "size": "xs"},
    {"id": "cohere/north-mini-code:free", "name": "North Mini Code", "ctx": 256_000, "size": "mini"},
    {"id": "liquid/lfm-2.5-2.6b:free", "name": "LFM 2.5 2.6B", "ctx": 65_536, "size": "2.6B"},
    {"id": "inclusionai/ling-3.0-flash-sante:free", "name": "Ling 3.0 Flash Sante", "ctx": 262_144, "size": "flash"},
    {"id": "inclusionai/ling-3.0-flash-fin:free", "name": "Ling 3.0 Flash Fin", "ctx": 262_144, "size": "flash"},
    {"id": "dots-studio/dots-3-note-preview:free", "name": "Dots 3 Note", "ctx": 512_000, "size": "note"},
]

# CORRECTED Zolai grammar system prompt (native-speaker verified)
ZOLAI_SYSTEM = """You are a Zolai language expert for Tedim Zolai (ZVS 2018).

PRONOUNS:
- ka = I
- na = you (singular)
- a = he/she (agreement marker, placed before verb)
- amah = he/she (emphatic standalone, placed before a)
- amau / amaute = they
- ki = we/us
- umau = you all

VERBS:
- pai = go (NEVER kal)
- mu = see (NEVER zoh)
- ne = eat (NEVER ei)
- dawn = drink (NEVER pi)
- thei = know (NEVER thei)
- bawl = create (NEVER ser)
- om = exist (NEVER um)
- ci = say (NEVER ti)
- dam = know
- tapa = life (NEVER fapa)
- topa = Lord (NEVER bawipa)

NEGATION:
- kei placed BEFORE verb for ALL persons (NEVER si)
- Correct: Ka pai kei hi. (I don't go)
- Correct: Na pai kei hi. (You don't go)
- Correct: A pai kei hi. (He/she doesn't go)
- Correct: Amau pai kei hi. (They don't go)

QUESTIONS:
- hiam placed at END of sentence (NEVER ze as question marker)
- Correct: Na pai hiam? (Do you go?)
- Correct: Na ne hiam? (Do you eat?)
- ze = emphatic/playful marker (NOT a question marker)

FUTURE:
- ding placed AFTER verb (NEVER dang)
- Correct: Ka pai ding hi. (I will go)
- Correct: Na ne ding hi. (You will eat)

PRESENT:
- hi at end of sentence (NEVER di)
- Correct: Ka pai hi. (I go)
- Correct: A pai hi. (He/she goes)

SOV WORD ORDER: Subject - Object - Verb
- Ka gam mu hi. (I land see = I see the land)
- Na tui dawn hi. (You water drink = You drink water)

EMPHATIC PRONOUN:
- Amah a pai hi. = HE goes (emphatic, emphasizing HE)
- A pai hi. = He goes (normal)
- Amah a pai kei hi. = HE doesn't go (emphatic negative)

FORBIDDEN FORMS (ZVS 2018):
- pathian -> pasian (God)
- ram -> gam (land, earth)
- fapa -> tapa (life)
- bawipa -> topa (Lord, master)
- siangpahrang -> kumpipa (Savior)
- cu/cun -> tua (that, conjunction)

ANSWER WITH ONLY THE ZOLAI SENTENCE. No English explanation."""
