"""Shared configuration for dataset export scripts.

Loads tokens from environment variables and defines dataset metadata.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Tokens (from environment — never hardcode)
# ---------------------------------------------------------------------------

def get_hf_token() -> str:
    """Return the HuggingFace API token from the HF_TOKEN env var."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN environment variable is not set")
    return token


def get_kaggle_token() -> str:
    """Return the Kaggle API token from the KAGGLE_API_TOKEN env var."""
    token = os.environ.get("KAGGLE_API_TOKEN")
    if not token:
        raise RuntimeError("KAGGLE_API_TOKEN environment variable is not set")
    return token


# ---------------------------------------------------------------------------
# Data paths (relative to repo root → sibling ../data/ tree)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # zolai-datasets/

PARALLEL_PATH = REPO_ROOT / "../data/parallel/zo_en_pairs_combined_v1.jsonl"
DICTIONARY_PATH = REPO_ROOT / "../data/dictionary/processed/dict_canonical_v1.jsonl"
TRAINING_PATH = REPO_ROOT / "../data/clean/master.jsonl"
BIBLE_DIR = REPO_ROOT / "../data/corpus/bible/"

# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------

DATASETS: dict[str, dict[str, str | list[str]]] = {
    "zolai-parallel-zo-en": {
        "path": str(PARALLEL_PATH),
        "repo_id": "Zolai-AI/zolai-parallel-zo-en",
        "description": "Bilingual Zomi–English parallel corpus (ZVS 2018 orthography).",
        "license": "cc-by-4.0",
        "tags": ["zomi", "tedim", "parallel-corpus", "bilingual", "nlp"],
    },
    "zolai-dictionary": {
        "path": str(DICTIONARY_PATH),
        "repo_id": "Zolai-AI/zolai-dictionary",
        "description": "Unified Tedim Zomi–English dictionary dataset.",
        "license": "cc-by-4.0",
        "tags": ["zomi", "tedim", "dictionary", "lexicon", "nlp"],
    },
    "zolai-training-master": {
        "path": str(TRAINING_PATH),
        "repo_id": "Zolai-AI/zolai-training-master",
        "description": "Cleaned master training corpus for Zomi language models.",
        "license": "cc-by-4.0",
        "tags": ["zomi", "tedim", "training", "corpus", "nlp"],
    },
    "zolai-bible-corpus": {
        "path": str(BIBLE_DIR),
        "repo_id": "Zolai-AI/zolai-bible-corpus",
        "description": "Tedim Zomi Bible corpus in USX and Markdown formats.",
        "license": "cc-by-4.0",
        "tags": ["zomi", "tedim", "bible", "corpus", "nlp"],
    },
}
