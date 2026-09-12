#!/usr/bin/env python3
"""
Ensemble Voter — Multi-model ensemble voting for Zolai NLP tasks.
Supports all 9 Gemini models with 4 voting strategies.
"""
import asyncio
import json
import os
import re
import sqlite3
import sys
import argparse
from typing import Any, ClassVar

sys.path.insert(
    0,
    os.environ.get(
        "ZOLAI_AI_LOCAL",
        "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local",
    ),
)

try:
    from gemini.client_openai import ZolaiGeminiOpenAIClient

    HAS_LOCAL = True
except ImportError:
    HAS_LOCAL = False

# ── DB Path ─────────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("ZOLAI_DB_PATH", "/home/peter/Documents/Projects/zolai-ai/data/zolai.db")


def save_model_result(
    task: str,
    model: str,
    input_text: str,
    output_json: str,
    confidence: float | None = None,
    ensemble_agreement: float | None = None,
    source: str | None = None,
) -> None:
    """Save Gemini model result to DB for history tracking."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO gemini_model_results 
            (task, model, input_text, output_json, confidence, ensemble_agreement, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task, model, input_text, output_json, confidence, ensemble_agreement, source),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  WARN [DB]: Failed to save model result: {e}")


# ── All 9 Gemini models ─────────────────────────────────────────────────────
MODELS: dict[str, str] = {
    "flash": "gemini-3-flash",
    "pro": "gemini-3-pro",
    "pro_plus": "gemini-3-pro-plus",
    "flash_think": "gemini-3-flash-thinking",
    "flash_plus": "gemini-3-flash-plus",
    "flash_think_plus": "gemini-3-flash-thinking-plus",
    "pro_adv": "gemini-3-pro-advanced",
    "flash_adv": "gemini-3-flash-advanced",
    "flash_think_adv": "gemini-3-flash-thinking-advanced",
}


def _extract_json(text: str) -> Any:
    """Extract JSON object or array from text."""
    # Try object first
    obj_match = re.search(r"\{[\s\S]*?\}", text)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass
    # Try array
    arr_match = re.search(r"\[[\s\S]*?\]", text)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass
    return None


def majority_vote(responses: list[Any]) -> Any:
    """Return the most common response across models."""
    counts: dict[str, int] = {}
    for resp in responses:
        key = json.dumps(resp, sort_keys=True, ensure_ascii=False)
        counts[key] = counts.get(key, 0) + 1
    best_key = max(counts, key=lambda k: counts[k])
    return json.loads(best_key)


def compute_confidence(responses: list[Any], final: Any) -> float:
    """Compute agreement ratio (0.0–1.0)."""
    if not responses:
        return 0.0
    final_key = json.dumps(final, sort_keys=True, ensure_ascii=False)
    agree = sum(
        1
        for r in responses
        if json.dumps(r, sort_keys=True, ensure_ascii=False) == final_key
    )
    return agree / len(responses)


# ── Ensemble Voter ───────────────────────────────────────────────────────────
class EnsembleVoter:
    """Multi-model ensemble voting for Zolai NLP tasks."""

    STRATEGIES: ClassVar[dict[str, list[str]]] = {
        "fast": [
            "gemini-3-flash",
            "gemini-3-pro",
            "gemini-3-pro-plus",
        ],
        "accurate": [
            "gemini-3-pro",
            "gemini-3-pro-plus",
            "gemini-3-pro-advanced",
            "gemini-3-flash-thinking",
            "gemini-3-flash-thinking-plus",
        ],
        "full": list(MODELS.values()),
        "reasoning": [
            "gemini-3-flash-thinking",
            "gemini-3-flash-thinking-plus",
            "gemini-3-flash-thinking-advanced",
        ],
    }

    def __init__(self, strategy: str = "fast"):
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Valid: {list(self.STRATEGIES.keys())}"
            )
        self.strategy = strategy
        self.models = self.STRATEGIES[strategy]
        self.client: ZolaiGeminiOpenAIClient | None = None

    async def init(self) -> None:
        """Initialize the Gemini client."""
        if not HAS_LOCAL:
            raise RuntimeError(
                "zolai-ai-local package not found. "
                "Install or set ZOLAI_AI_LOCAL env var."
            )
        self.client = ZolaiGeminiOpenAIClient(use_zvs_context=False)
        await self.client.init()

    async def close(self) -> None:
        """Close all clients."""
        if self.client and hasattr(self.client, "close"):
            await self.client.close()

    async def vote(self, prompt: str, task: str = "general") -> dict:
        """Query all models in strategy, return majority vote result."""
        if not self.client:
            await self.init()

        votes: dict[str, Any] = {}
        for model in self.models:
            try:
                result = await self.client.ask(
                    model, prompt, use_system_prompt=False
                )
                parsed = _extract_json(result)
                if parsed is not None:
                    votes[model] = parsed
                    # Save individual model result to DB
                    save_model_result(
                        task=task,
                        model=model,
                        input_text=prompt,
                        output_json=json.dumps(parsed, ensure_ascii=False),
                        source="ensemble_voter",
                    )
            except Exception as exc:
                print(f"  WARN [{model}]: {exc}")
            await asyncio.sleep(1)

        if not votes:
            return {
                "result": None,
                "confidence": 0.0,
                "models_used": 0,
                "models_total": len(self.models),
                "strategy": self.strategy,
            }

        parsed = list(votes.values())
        final = majority_vote(parsed)
        confidence = compute_confidence(parsed, final)

        # Save ensemble result to DB
        save_model_result(
            task=task,
            model="ensemble",
            input_text=prompt,
            output_json=json.dumps(final, ensure_ascii=False),
            confidence=confidence,
            ensemble_agreement=confidence,
            source=f"ensemble_{self.strategy}",
        )

        return {
            "result": final,
            "confidence": confidence,
            "models_used": len(parsed),
            "models_total": len(self.models),
            "strategy": self.strategy,
            "votes": votes,
        }

    # ── Task-specific vote methods ──────────────────────────────────────────

    async def vote_pos(self, word: str, english: str) -> dict:
        """POS tag for a single Zolai word."""
        prompt = (
            f"POS tag for Zolai word: {word} ({english}).\n"
            "Tags: NOUN, VERB, ADJ, ADV, PRON, DET, POST, CONJ, PART, NUM, INTJ\n"
            'Output JSON: {"pos": "NOUN"}'
        )
        return await self.vote(prompt, task="pos")

    async def vote_pos_sentence(
        self, sentence: str
    ) -> dict:
        """POS tag every word in a Zolai sentence."""
        prompt = (
            "POS tag this Zolai sentence word by word.\n"
            "Output JSON array of [word, tag] pairs.\n"
            f"Sentence: {sentence}"
        )
        return await self.vote(prompt, task="pos_sentence")

    async def vote_morphology(
        self, word: str, syllables: str = ""
    ) -> dict:
        """Morphological analysis of a Zolai word."""
        syll_info = f" (syllables: {syllables})" if syllables else ""
        prompt = (
            f"Morphology of Zolai word: {word}{syll_info}.\n"
            "Output JSON:\n"
            '{"root": "...", "prefix": "", "suffix": "", '
            '"morphemes": ["root"], "POS": "NOUN"}'
        )
        return await self.vote(prompt, task="morphology")

    async def vote_similarity(
        self,
        w1: str,
        e1: str,
        w2: str,
        e2: str,
    ) -> dict:
        """Semantic similarity between two Zolai words."""
        prompt = (
            "Semantic similarity (0.0–1.0) between:\n"
            f"  Zolai 1: {w1} ({e1})\n"
            f"  Zolai 2: {w2} ({e2})\n"
            'Output JSON: {"similarity": 0.85}'
        )
        return await self.vote(prompt, task="similarity")

    async def vote_translation(
        self, zo: str, context: str = ""
    ) -> dict:
        """Translate Zolai sentence to English."""
        ctx = f"\nContext: {context}" if context else ""
        prompt = (
            f"Translate this Zolai to English:{ctx}\n"
            f"Zolai: {zo}\n"
            'Output JSON: {"translation": "..."}'
        )
        return await self.vote(prompt, task="translation")

    async def vote_ner(self, sentence: str) -> dict:
        """Named entity recognition in Zolai."""
        prompt = (
            "Named entities in this Zolai sentence.\n"
            "Types: PER, LOC, ORG\n"
            'Output JSON: {"entities": [{"text": "...", "type": "PER"}]}\n'
            f"Sentence: {sentence}"
        )
        return await self.vote(prompt, task="ner")

    async def vote_classify(self, text: str) -> dict:
        """Classify topic of Zolai text."""
        topics = (
            "religion, education, news, story, "
            "grammar, proverb, song, conversation"
        )
        prompt = (
            f"Classify topic of this Zolai text.\n"
            f"Topics: {topics}\n"
            'Output JSON: {"topic": "...", "confidence": 0.9}\n'
            f"Text: {text}"
        )
        return await self.vote(prompt, task="classify")


# ── CLI ──────────────────────────────────────────────────────────────────────
async def cli(args: argparse.Namespace) -> None:
    """Run CLI commands."""
    voter = EnsembleVoter(strategy=args.strategy)
    await voter.init()

    try:
        result: dict = {}
        if args.task == "pos":
            result = await voter.vote_pos(args.word, args.english)
        elif args.task == "pos-sent":
            result = await voter.vote_pos_sentence(args.sentence)
        elif args.task == "morph":
            result = await voter.vote_morphology(
                args.word, getattr(args, "syllables", "")
            )
        elif args.task == "sim":
            result = await voter.vote_similarity(
                args.w1, args.e1, args.w2, args.e2
            )
        elif args.task == "translate":
            result = await voter.vote_translation(
                args.zo, getattr(args, "context", "")
            )
        elif args.task == "ner":
            result = await voter.vote_ner(args.sentence)
        elif args.task == "classify":
            result = await voter.vote_classify(args.text)
        else:
            print(f"Unknown task: {args.task}")
            return

        # Print result
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        await voter.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="9-model ensemble voter for Zolai NLP tasks"
    )
    parser.add_argument(
        "--strategy",
        choices=["fast", "accurate", "full", "reasoning"],
        default="fast",
        help="Ensemble strategy (default: fast = 3 models)",
    )
    parser.add_argument(
        "--task",
        required=True,
        choices=[
            "pos",
            "pos-sent",
            "morph",
            "sim",
            "translate",
            "ner",
            "classify",
        ],
        help="NLP task to run",
    )

    # POS arguments
    parser.add_argument("--word", default="")
    parser.add_argument("--english", default="")

    # Sentence arguments
    parser.add_argument("--sentence", default="")

    # Morphology arguments
    parser.add_argument("--syllables", default="")

    # Similarity arguments
    parser.add_argument("--w1", default="")
    parser.add_argument("--e1", default="")
    parser.add_argument("--w2", default="")
    parser.add_argument("--e2", default="")

    # Translation arguments
    parser.add_argument("--zo", default="")
    parser.add_argument("--context", default="")

    # Classify arguments
    parser.add_argument("--text", default="")

    args = parser.parse_args()
    asyncio.run(cli(args))


if __name__ == "__main__":
    main()
