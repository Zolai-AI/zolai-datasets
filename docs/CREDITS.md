# Zolai-AI — Data Sources & Attribution

**Last Updated:** 2026-09-07

---

## Why We Use the Bible

The Bible is our **primary training corpus** because it is the **only complete, trusted, EN/ZO parallel corpus** available for Tedim Zolai:

- **31,102 parallel verses** (EN↔ZO) — no other source comes close
- **Complete text** — all 66 books, covering all registers
- **Multiple versions** — TDB77, Tedim2010, Hakha, Falam, Paite
- **Community-validated** — decades of translation work by native speakers
- **Publicly available** — open access for language preservation

**Note:** We use the Bible as a *language learning corpus*, not for religious purposes.

---

## Our Published Datasets

### HuggingFace

| Dataset | URL | Size | Content |
|---------|-----|------|---------|
| Zolai-AI/zolai-datasets | https://huggingface.co/datasets/Zolai-AI/zolai-datasets | — | Org datasets |
| peterpausianlian/zolai-knowledge-vectors | https://huggingface.co/datasets/peterpausianlian/zolai-knowledge-vectors | 100K-1M | Sentence embeddings for RAG |
| peterpausianlian/zolai-language-corpus | https://huggingface.co/datasets/peterpausianlian/zolai-language-corpus | — | Language corpus |

### HuggingFace Models

| Model | URL | Type |
|-------|-----|------|
| peterpausianlian/zolai-qwen2.5-3b-lora | https://huggingface.co/peterpausianlian/zolai-qwen2.5-3b-lora | LoRA adapter (Qwen2.5-3B) |

### Kaggle

| Dataset | URL | Size | Content |
|---------|-----|------|---------|
| peterpausianlian/zolai-llm-training-dataset | https://kaggle.com/datasets/peterpausianlian/zolai-llm-training-dataset | 94MB | LLM training data |
| peterpausianlian/zolai-tedim-cleaned-master | https://kaggle.com/datasets/peterpausianlian/zolai-tedim-cleaned-master | 120MB | Cleaned Tedim corpus |
| peterpausianlian/zolai-master-data | https://kaggle.com/datasets/peterpausianlian/zolai-master-data | 3.3MB | Master data |
| peterpausianlian/zolai-language-dataset-v2 | https://kaggle.com/datasets/peterpausianlian/zolai-language-dataset-v2 | 3.3MB | Language dataset |
| peterpausianlian/zolai-hf-dataset | https://kaggle.com/datasets/peterpausianlian/zolai-hf-dataset | 122MB | HuggingFace base |
| peterpausianlian/zolai-hf-advanced | https://kaggle.com/datasets/peterpausianlian/zolai-hf-advanced | 67MB | HuggingFace advanced |
| peterpausianlian/bible-datasets | https://kaggle.com/datasets/peterpausianlian/bible-datasets | 72MB | Bible USX format |
| peterpausianlian/zolai-unified | https://kaggle.com/datasets/peterpausianlian/zolai-unified | 343KB | Unified corpus |

---

## Data Sources

### Bible Corpus

| Source | Repository | Versions | Entries |
|--------|-----------|----------|---------|
| Bible JSON | [dalsuum/bible-master](https://github.com/dalsuum/bible-master) | Tedim 1932, Tedim 2010, TDB77, Hakha 1920, Falam 1973, Paite 1971 | 31,102 verses |

### Dictionary Sources

| Source | Repository | Entries | Type |
|--------|-----------|---------|------|
| Zolai→English | [ZomiLanguage/dictionary](https://github.com/ZomiLanguage/dictionary) | 93,931 | Primary ZO→EN |
| English→Zolai | [ZomiLanguage/dictionary](https://github.com/ZomiLanguage/dictionary) | 112,220 | Primary EN→ZO |
| Trilingual | [dalsuum/zolai-dictionary](https://github.com/dalsuum/zolai-dictionary) | 7,861 | ZO-EN-MY |
| TongDot | [paumkim/zomi-dataset](https://github.com/paumkim/zomi-dataset) | 5,004 | ZO-EN |

### Corpus Sources

| Source | Repository | Size | Content |
|--------|-----------|------|---------|
| Clean corpus | [paumkim/zomi-dataset](https://github.com/paumkim/zomi-dataset) | 208MB | 3M+ sentences |
| Worship songs | [paumkim/zomi-dataset](https://github.com/paumkim/zomi-dataset) | 573KB | Lyrics |
| Conversational | [paumkim/zomi-dataset](https://github.com/paumkim/zomi-dataset) | 547KB | Spoken data |

### Reference Materials

| Material | Year | Content |
|----------|------|---------|
| Zolai Grammar Vol 1 | 2010 | 17,196 lines — authoritative grammar |
| Zolai Sinna | 2010 | 6,259 lines — 34-lesson textbook |
| ZVS 2018 | 2018 | Orthography standard |
| Gentehna Tuamtuam | Various | 51 Bible stories |

### Bible Translation Organizations

| Organization | Role |
|-------------|------|
| Myanmar Bible Society | Tedim Bible publication |
| Zomi Christian Literature Society | Zolai Bible publishing |
| Alliance Bible Committee | Translation coordination |

---

## Tools & Frameworks

| Tool | License | Usage |
|------|---------|-------|
| PyTorch | BSD-3 | ML framework |
| sentence-transformers | Apache 2.0 | Embeddings for RAG |
| FastAPI | MIT | API server |
| Next.js | MIT | Learner platform |
| React 19 | MIT | Landing page |
| Vite | MIT | Build tool |
| Three.js | MIT | 3D visualization |
| Cloudflare Workers | — | MCP server hosting |
| Cloudflare Pages | — | Landing page hosting |
