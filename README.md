# zolai-datasets — Zolai bilingual corpora & datasets

Build scripts and pointers for Zolai datasets. The heavy corpora live on
**HuggingFace Hub / Kaggle** (never in git).

## What's here
- `scripts/` — data pipeline, dictionary, cleaner, bible builders
- `scripts/reconcile_wiki_dictionary.py` — wiki↔dictionary reconciliation audit
- Dataset pointers (HF `peterpausianlian/zolai-*`, Kaggle `zolai-llm-*`)

## Datasets (published, not in git)
| Dataset | Host |
|---|---|
| Parallel ZO⇄EN pairs (105k+) | HuggingFace Hub |
| Dictionary (152k entries) | HuggingFace Hub |
| Training set v3 (~5.1M) | HuggingFace Hub |
| Bible corpus | HuggingFace Hub |
| LoRA adapters (0.5B/3B) | HuggingFace Hub |

## Principles
- Corpora/datasets mirrored, never committed.
- Tokens from `.env` only.
