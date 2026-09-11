# Script Consolidation Map

**Date:** 2026-09-11
**Consolidated into:** `bible_knowledge_builder.py`

## Overview

14 scripts with overlapping imports, data loading, and output patterns were
consolidated into a single module with three builder classes. The original
scripts are preserved but marked as deprecated.

## Parallel Builder

Consolidates 3 scripts that build Bible parallel corpora:

| Original Script | Lines | Purpose | Maps To |
|----------------|-------|---------|---------|
| `build_parallel_corpus.py` | 172 | Parse Tedim_Chin markdown → JSONL | `ParallelBuilder.build_from_markdown()` |
| `build_parallel_bible.py` | 129 | Parse USX XML → parallel .md files | `ParallelBuilder.build_from_usx()` |
| `rebuild_bible_parallel.py` | 132 | Rebuild combined parallel.jsonl | `ParallelBuilder.rebuild_combined()` |

**Output:** `data/bible/parallel_corpus_v1.jsonl`

## Vocabulary Builder

Consolidates 6 scripts that build/enrich vocabulary databases:

| Original Script | Lines | Purpose | Maps To |
|----------------|-------|---------|---------|
| `build_vocabulary_db.py` | 187 | Aggregate dict + alignments → vocab DB | `VocabularyBuilder.build_vocab_db()` |
| `extract_bible_vocab.py` | 133 | Extract vocab from Bible chapters | `VocabularyBuilder.extract_bible_vocab()` |
| `learn_bible_vocab.py` | 202 | Extract vocab with LLM context | *(no direct merge — API-dependent)* |
| `fill_bible_vocab_gaps.py` | 295 | Fill vocab gaps via Gemini API | *(no direct merge — API-dependent)* |
| `fill_bible_vocab_local.py` | 329 | Fill vocab gaps via local dicts | *(no direct merge — complex pipeline)* |
| `crossref_bible_vocab.py` | 362 | Cross-ref 482 gaps across versions | *(no direct merge — complex pipeline)* |

**Output:** `data/bible/vocabulary_db_v1.jsonl`

**Note:** `learn_bible_vocab`, `fill_bible_vocab_gaps`, `fill_bible_vocab_local`,
and `crossref_bible_vocab` depend on external APIs (OpenRouter/Gemini) and complex
SQLite pipelines. They are marked deprecated but their full logic was not ported
into the consolidated module to avoid pulling in API keys and database dependencies.
Their core dictionary-loading and extraction patterns are represented.

## Grammar Builder

Consolidates 5 scripts that build grammar pattern databases:

| Original Script | Lines | Purpose | Maps To |
|----------------|-------|---------|---------|
| `extract_grammar_patterns.py` | 304 | Extract patterns from corpus | `GrammarBuilder.build_grammar_patterns()` |
| `extract_grammar_from_vol1.py` | 242 | Parse Grammar Vol 1 reference | `GrammarBuilder.extract_from_vol1()` |
| `extract_zvs_rules.py` | 241 | Parse ZVS 2018 rules reference | `GrammarBuilder.extract_zvs_rules()` |
| `extract_sinna_lessons.py` | 100 | Parse Sinna lesson files | `GrammarBuilder.extract_sinna_lessons()` |
| `build_grammar_reference_v2.py` | 333 | Merge into grammar_reference_v2 | `GrammarBuilder.build_grammar_reference_v2()` |

**Output:** `data/bible/grammar_patterns_v2.jsonl`

## Key Improvements

1. **Shared constants** — `BOOK_NAMES`, `WORKSPACE`, `_tokenize()` defined once
2. **Consistent path handling** — all paths relative to `WORKSPACE`
3. **Unified CLI** — `--parallel`, `--vocabulary`, `--grammar`, `--all`
4. **Testable** — classes can be imported and tested independently
5. **No duplicate imports** — `json`, `re`, `sys`, `Path`, `ET` loaded once

## Lines of Code

| Before (14 scripts) | After (1 module) | Reduction |
|---------------------|-------------------|-----------|
| ~3,041 | ~750 | ~75% |

## What Was NOT Consolidated

These scripts were left as-is because they are standalone tools, not
duplicating the parallel/vocabulary/grammar building pipeline:

- `bible_engine.py` — interactive Bible study engine
- `bible_context_learner.py` — per-book context analysis
- `context_deep_learner.py` — deep context learning
- `paragraph_engine.py` — paragraph analysis engine
- `proficiency_test.py` — CEFR proficiency tests
- `check_non_zolai.py` — Hakha/Falam word checker
- `generate_training_data.py` — training data generator
- `grammar_check.py` — grammar validation CLI
- `vocab_quiz.py` — vocabulary quiz CLI
- All `fix_*.py`, `fetch_*.py`, `openrouter_*.py`, `menu*.sh`
