# Zolai-AI Master Plan — Everything Tracker

**Created:** 2026-09-07
**Last Updated:** 2026-09-07 (Session: Master Plan Update)
**Status:** ACTIVE

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [What Needs Updating](#2-what-needs-updating)
3. [Script Consolidation Plan](#3-script-consolidation-plan)
4. [Online Resources to Integrate](#4-online-resources-to-integrate)
5. [Menu Update Plan](#5-menu-update-plan)
6. [Wiki Update Plan](#6-wiki-update-plan)
7. [Data Pipeline](#7-data-pipeline)
8. [Task Tracker](#8-task-tracker)
9. [Daily/Weekly/Monthly Plan](#9-dailyweeklymonthly-plan)
10. [Git Workflow](#10-git-workflow)
11. [Data Sources & Attribution](#11-data-sources--attribution)
12. [Usage Guide](#12-usage-guide)
13. [Coverage Gaps & Roadmap](#13-coverage-gaps--roadmap)
14. [Documentation Updates](#14-documentation-updates)
15. [Sustainable Maintenance System](#15-sustainable-maintenance-system)
16. [Training Pipeline](#16-training-pipeline)

---

## 1. Current State Audit

### Scripts (40 total, 15,240 lines)

| Script | Lines | Status | Purpose | Keep? |
|--------|-------|--------|---------|-------|
| paragraph_engine.py | 2,818 | ✅ Working | Paragraph analysis + style | YES (core) |
| bible_engine.py | 1,876 | ✅ Working | Bible analysis engine | YES (core) |
| build_linguistic_pipeline.py | 976 | ✅ Working | 8-step pipeline | YES (core) |
| menu.sh | 885 | ⚠️ Needs update | Interactive CLI | YES (update) |
| build_full_knowledge_base.py | 557 | ✅ Working | Knowledge base builder | MERGE |
| bible_vocab_pipeline.py | 471 | ✅ Working | Vocab pipeline | MERGE |
| study_bible_books.py | 457 | ✅ Working | Bible study (pcore-brain) | YES (core) |
| build_polysemy_from_references.py | 370 | ✅ NEW | Polysemy builder | YES |
| build_bible_dictionary.py | 369 | ✅ Working | Dict builder | MERGE |
| crossref_bible_vocab.py | 362 | ✅ Working | Vocab cross-ref | MERGE |
| build_grammar_reference_v2.py | 332 | ✅ NEW | Grammar ref builder | YES |
| fill_bible_vocab_local.py | 329 | ✅ Working | Vocab gap fill | MERGE |
| extract_grammar_patterns.py | 304 | ✅ Working | Grammar patterns | MERGE |
| build_comprehensive_vocab.py | 297 | ✅ NEW | Vocab merger | YES |
| fill_bible_vocab_gaps.py | 295 | ✅ Working | Vocab gap fill | MERGE |
| generate_training_data.py | 286 | ✅ Working | Training data gen | YES |
| zolai_learn.py | 280 | ✅ Working | Learning tool | YES (core) |
| build_reference_index.py | 244 | ✅ NEW | AI context index | YES |
| extract_grammar_from_vol1.py | 241 | ✅ NEW | Grammar extractor | YES |
| extract_zvs_rules.py | 240 | ✅ NEW | ZVS rule extractor | YES |
| bible_corpus_analyzer.py | 238 | ✅ Working | Corpus analysis | MERGE |
| check_non_zolai.py | 231 | ✅ Working | Non-Zolai checker | YES |
| fetch_bible_versions.py | 223 | ✅ Working | Bible version fetcher | YES |
| build_exercises_from_stories.py | 220 | ✅ NEW | Exercise generator | YES |
| align_words.py | 216 | ✅ Working | Word alignment | MERGE |
| learn_bible_vocab.py | 202 | ✅ Working | Vocab learning | MERGE |
| fix_bible_nahum_and_rebuild.py | 189 | ✅ Working | Nahum fix | DELETE |
| build_vocabulary_db.py | 187 | ✅ Working | Vocab DB builder | MERGE |
| build_parallel_corpus.py | 172 | ✅ Working | Parallel corpus | MERGE |
| build_parallel_bible.py | ~170 | ✅ Working | Parallel Bible | MERGE |
| build_bible_pairs.py | ~170 | ✅ Working | Bible pairs | MERGE |
| extract_bible_vocab.py | ~170 | ✅ Working | Vocab extraction | MERGE |
| rebuild_bible_parallel.py | ~170 | ✅ Working | Rebuild parallel | MERGE |
| fix_bible_data.py | ~170 | ✅ Working | Data fixes | DELETE |
| fix_bible_violations.py | ~170 | ✅ Working | Violation fixes | DELETE |
| fetch_tbr17_full.py | ~170 | ✅ Working | TBR17 fetcher | YES |
| parse_tbr17_html.py | ~170 | ✅ Working | TBR17 parser | YES |
| test_bible_vocab.py | ~170 | ✅ Working | Vocab tests | YES |
| extract_sinna_lessons.py | ~200 | ✅ NEW | Lesson extractor | YES |

### Data Files

| File | Size | Status | Notes |
|------|------|--------|-------|
| vocab_comprehensive.jsonl | 13MB | ✅ Active | 23,383 words |
| vocab_by_frequency.jsonl | 12MB | ✅ Active | Frequency-ranked |
| dict_canonical_clean.jsonl | 56MB | ✅ Active | 112K EN→ZO |
| dict_zo_en_clean.jsonl | 11MB | ✅ Active | 94K ZO→EN |
| parallel_corpus_v1.jsonl | 16MB | ✅ Active | 31K verses |
| word_alignments_v1.jsonl | 52MB | ✅ Active | 385K alignments |
| sinna_lessons.json | 195KB | ✅ NEW | 69 lessons |
| exercises_from_references.jsonl | 153KB | ✅ NEW | 451 exercises |
| grammar_comprehensive.json | 39KB | ✅ NEW | Grammar rules |
| polysemy_database.json | 21KB | ✅ NEW | 77 polysemous words |
| grammar_reference_v2.json | 7KB | ✅ NEW | 12 grammar sections |
| zvs_rules.json | 7KB | ✅ NEW | ZVS 2018 rules |
| reference_index.json | 8KB | ✅ NEW | AI context index |
| duolingo_course.json | 29KB | ✅ Active | 30-week course |
| curriculum.json | 2KB | ✅ Active | 17 levels |
| exercises.jsonl | 58KB | ✅ Active | 201 exercises |

### Reference Materials

| Material | Lines | Status | Source |
|----------|-------|--------|--------|
| Zolai_Grammar_Vol1.md | 17,196 | ✅ Converted | PDF |
| Zolai_Sinna.md | 6,259 | ✅ Converted | PDF |
| ZVS_PDF.md | 2,021 | ✅ Converted | PDF |
| Gentehna stories | 1,209 | ✅ Converted | TXT |
| Literature (14 files) | ~70K | ✅ Converted | PDFs |
| Genealogy (3 files) | ~10K | ✅ Converted | PDFs |
| Corpus (2 files) | ~8K | ✅ Active | JSONL |
| Tongdot terms | 102 | ✅ Active | MD |

---

## 2. What Needs Updating

### 🔴 HIGH PRIORITY (Do First)

| # | Task | Why | Est. Time | Status |
|---|------|-----|-----------|--------|
| H1 | **Git commit 8 NEW scripts** | They exist but are uncommitted | 10 min | ✅ DONE — commit `42e3f2b` (2026-09-07) |
| H2 | **Fix vocab_comprehensive_v2.py** | Only 167 entries (target 25K+) | 30 min | ✅ SUPERSEDED — `vocab_master.jsonl` (98K words) |
| H3 | **Update menu.sh** | Add new script options, fix model list | 30 min | ✅ DONE — commit `30a7c61` (2026-09-07) |
| H4 | **Update pcore-brain context** | Add polysemy rules + comprehensive grammar | 1 hr | ✅ DONE (2026-09-06) |
| H5 | **Combine duplicate vocab scripts** | 5 scripts do similar things → 1 script | 2 hr | ⏳ QUEUED |
| H6 | **Combine duplicate Bible scripts** | 8 scripts do similar things → 2 scripts | 2 hr | ⏳ QUEUED |
| H7 | **Generate 10K synthetic training pairs** | Seed data ready (`seed_data_500_fixed.jsonl`) | 4 hr | ⏳ QUEUED |
| H8 | **Set up Kaggle notebook** | Guide written (`KAGGLE_SETUP.md`) | 1 hr | ⏳ QUEUED |
| H9 | **Fine-tune Qwen2.5-3B on Kaggle T4** | 30 hrs/week free GPU | 1 day | ⏳ QUEUED |
| H10 | **Build custom Zolai tokenizer** | Improve F1 by 5-15 points | 2 hr | ⏳ QUEUED |
| H11 | **Deploy Argilla annotation server** | Community validation platform | 2 hr | ⏳ QUEUED |
| H12 | **Create evaluation benchmark suite** | BLEU + F1 + native speaker review | 3 hr | ⏳ QUEUED |

### 🟡 MEDIUM PRIORITY (Do Next)

| # | Task | Why | Est. Time | Status |
|---|------|-----|-----------|--------|
| M1 | **Download paumkim/zomi-dataset** | 3M+ sentences, 36K+ words, 130K+ dict | 1 hr | ✅ DONE — 207MB in `data/online/` |
| M2 | **Integrate dalsuum/zolai-dictionary** | 7,861 headwords, trilingual | 2 hr | ✅ DONE — 7,841 entries in `dict_dalsuum_merged.jsonl` |
| M3 | **Download zomi-tedim-ai Bible corpus** | Tedim-Burmese parallel verses | 1 hr | ✅ DONE (in `data/online/`) |
| M4 | **Build comprehensive polysemy DB** | Currently 77, target 200+ | 3 hr | ⏳ QUEUED |
| M5 | **Fix Sinna lesson parsing** | 69 "lessons" found, should be 34 | 1 hr | ⏳ QUEUED |
| M6 | **Update wiki grammar section** | Use Grammar Vol 1 as source | 2 hr | ⏳ QUEUED |
| M7 | **Update wiki vocabulary section** | Use comprehensive vocab | 2 hr | ⏳ QUEUED |

### 🟢 LOW PRIORITY (Do When Ready)

| # | Task | Why | Est. Time | Status |
|---|------|-----|-----------|--------|
| L1 | **Download TongDot dictionary** | 27,755 English words | 30 min | ✅ DONE — 5,004 entries in `data/online/` |
| L2 | **Download Glosbe examples** | Tedim-English sentence pairs | 1 hr | ✅ DONE — 21 JSONs in `data/online/` |
| L3 | **Download Zolai Grammar (Zomi Nam)** | Lia Cingsen's 30 lessons | 30 min | ✅ DONE — converted to markdown |
| L4 | **Download Zolai Sim Bu Tan Khat** | Cope's original reader | 30 min | ✅ DONE — converted to markdown |
| L5 | **Build audio pronunciation DB** | No audio data yet | 1 day | ⏳ QUEUED |
| L6 | **Build tone/sandhi system** | Zolai is tonal | 1 week | ⏳ QUEUED |
| L7 | **Create interactive web app** | zolai-web integration | 1 week | ⏳ QUEUED |

---

## 3. Script Consolidation Plan

### Current: 40 scripts → Target: 15 scripts

#### MERGE GROUP A: Vocab Scripts (5 → 1)

**Current scripts:**
- `build_comprehensive_vocab.py` (297 lines) — NEW
- `build_vocabulary_db.py` (187 lines)
- `extract_bible_vocab.py` (~170 lines)
- `crossref_bible_vocab.py` (362 lines)
- `fill_bible_vocab_gaps.py` (295 lines)
- `fill_bible_vocab_local.py` (329 lines)
- `bible_vocab_pipeline.py` (471 lines)
- `learn_bible_vocab.py` (202 lines)

**Merged into:** `vocab_builder.py` (~600 lines)
- All vocab extraction, merging, gap-filling, cross-referencing
- Input: Bible corpus + reference materials + online dictionaries
- Output: `vocab_comprehensive.jsonl` (single source of truth)

#### MERGE GROUP B: Bible Scripts (8 → 2)

**Current scripts:**
- `build_parallel_corpus.py` (172 lines)
- `build_parallel_bible.py` (~170 lines)
- `build_bible_pairs.py` (~170 lines)
- `rebuild_bible_parallel.py` (~170 lines)
- `build_bible_dictionary.py` (369 lines)
- `bible_corpus_analyzer.py` (238 lines)
- `align_words.py` (216 lines)
- `extract_grammar_patterns.py` (304 lines)

**Merged into:**
- `bible_data_builder.py` (~500 lines) — corpus, alignment, dictionary
- `bible_analysis.py` (~400 lines) — grammar patterns, corpus analysis

#### MERGE GROUP C: Grammar Scripts (3 → 1)

**Current scripts:**
- `extract_grammar_from_vol1.py` (241 lines) — NEW
- `extract_zvs_rules.py` (240 lines) — NEW
- `build_grammar_reference_v2.py` (332 lines) — NEW

**Merged into:** `grammar_builder.py` (~500 lines)

#### MERGE GROUP D: Fix/Debug Scripts (4 → DELETE)

**Delete:**
- `fix_bible_data.py` — one-time fix
- `fix_bible_violations.py` — one-time fix
- `fix_bible_nahum_and_rebuild.py` — one-time fix
- `test_bible_vocab.py` — move tests to tests/

#### KEEP AS-IS (Core Scripts)

| Script | Purpose |
|--------|---------|
| `bible_engine.py` | Core Bible analysis engine (1,876 lines) |
| `paragraph_engine.py` | Paragraph analysis + style (2,818 lines) |
| `study_bible_books.py` | Bible study with pcore-brain API |
| `zolai_learn.py` | Interactive learning tool |
| `check_non_zolai.py` | Non-Zolai word checker |
| `menu.sh` | Interactive CLI |
| `build_full_knowledge_base.py` | Knowledge base builder |
| `generate_training_data.py` | Training data generator |
| `fetch_tbr17_full.py` | TBR17 fetcher |
| `parse_tbr17_html.py` | TBR17 parser |

#### NEW SCRIPTS (From This Session)

| Script | Purpose | Keep? |
|--------|---------|-------|
| `build_polysemy_from_references.py` | Polysemy builder (77 words) | YES |
| `build_exercises_from_stories.py` | Exercise generator (451 exercises) | YES |
| `build_reference_index.py` | AI context index | YES |
| `extract_sinna_lessons.py` | Lesson extractor | MERGE into grammar_builder |

### Final Script Count: 15

| # | Script | Purpose |
|---|--------|---------|
| 1 | `bible_engine.py` | Core Bible analysis |
| 2 | `paragraph_engine.py` | Paragraph analysis + style |
| 3 | `study_bible_books.py` | Bible study (pcore-brain) |
| 4 | `zolai_learn.py` | Interactive learning |
| 5 | `menu.sh` | Interactive CLI |
| 6 | `vocab_builder.py` | Vocab extraction + merging |
| 7 | `bible_data_builder.py` | Corpus, alignment, dictionary |
| 8 | `bible_analysis.py` | Grammar patterns, analysis |
| 9 | `grammar_builder.py` | Grammar rules from references |
| 10 | `polysemy_builder.py` | Polysemy database |
| 11 | `exercise_builder.py` | Exercise generation |
| 12 | `reference_builder.py` | AI context index |
| 13 | `check_non_zolai.py` | Non-Zolai checker |
| 14 | `knowledge_builder.py` | Knowledge base builder |
| 15 | `data_fetcher.py` | Bible versions + online data |

---

## 4. Online Resources to Integrate

### HIGH VALUE (Download Now)

| Resource | URL | Content | Size | Action |
|----------|-----|---------|------|--------|
| **paumkim/zomi-dataset** | github.com/paumkim/zomi-dataset | 3M+ sentences, 36K+ words, 130K+ dict | 3.6GB | Download + merge vocab |
| **dalsuum/zolai-dictionary** | github.com/dalsuum/zolai-dictionary | 7,861 headwords, trilingual | ~5MB | Download words.json |
| **zomi-tedim-ai** | huggingface.co/zomi-tedim-ai | Tedim-Burmese Bible parallel | ~10MB | Download corpus |
| **Zolai Grammar (Zomi Nam)** | kupdf.net/download/... | Lia Cingsen, 30 lessons | 343KB | Download PDF → MD |
| **Zolai Sim Bu Tan Khat** | scribd.com/document/... | Cope's reader, copyedited | Unknown | Download if free |

### MEDIUM VALUE (Download Later)

| Resource | URL | Content | Size |
|----------|-----|---------|------|
| **TongDot** | tongdot.com | 27,755 English words | Unknown |
| **Glosbe** | glosbe.com/ctd/en | Tedim-English examples | Unknown |
| **Joshua Project** | test.joshuaproject.net/languages/ctd | Audio Bible, resources | Unknown |
| **Zomi eLibrary** | zomielibrary.com | Zolai Grammar PDF | 343KB |
| **Tedim-English-Burmese Handbook** | leanpub.com/tedim-english-burmese-handbook | Handbook | Paid |

### DATA CORRECTION NEEDED

| Issue | Source | Fix |
|-------|--------|-----|
| `pathian` vs `pasian` | Multiple sources | ZVS 2018: always `pasian` |
| `ram` vs `gam` | Multiple sources | ZVS 2018: always `gam` |
| `fapa` vs `tapa` | Multiple sources | ZVS 2018: always `tapa` |
| `bawipa` vs `topa` | Multiple sources | ZVS 2018: always `topa` |
| `siangpahrang` vs `kumpipa` | Multiple sources | ZVS 2018: always `kumpipa` |
| `cu/cun` vs `tua` | Multiple sources | ZVS 2018: always `tua` |
| `ze` as question marker | Multiple sources | WRONG: `hiam` is question marker |
| `suah` vs `suahtakna` | Multiple sources | Context-dependent |
| `nunnak` vs `nuntakna` | Multiple sources | Context-dependent |

---

## 5. Menu Update Plan

### Current Menu (menu.sh)

```
A) Bible Study (study_bible_books.py)
B) Non-Zolai Word Check
C) Bible Engine (bible_engine.py)
D) Progressive Learning
E) Review Due Items
F) Corpus Search
G) Export Training Data
H) Knowledge Vectors
I) Paragraph Analysis
J) Paraphrase & Style Transfer
K) Paragraph Knowledge Base
```

### New Menu (Target)

```
=== CORE ===
A) Bible Study (AI-powered)           → study_bible_books.py
B) Bible Engine (Full Analysis)       → bible_engine.py
C) Interactive Learning (Duolingo)    → zolai_learn.py
D) Paragraph Analysis & Style         → paragraph_engine.py

=== DATA BUILD ===
E) Build Vocabulary (All Sources)     → vocab_builder.py
F) Build Bible Data (Corpus+Align)    → bible_data_builder.py
G) Build Grammar Rules                → grammar_builder.py
H) Build Polysemy Database            → polysemy_builder.py
I) Build Exercises                    → exercise_builder.py
J) Build Reference Index              → reference_builder.py
K) Build Knowledge Base               → knowledge_builder.py

=== CHECK ===
L) Check Non-Zolai Words             → check_non_zolai.py
M) ZVS 2018 Compliance Check         → (new script)

=== TOOLS ===
N) Fetch Bible Versions               → data_fetcher.py
O) Export Training Data               → generate_training_data.py
P) Search Dictionary                  → (built into zolai_learn.py)

=== SETTINGS ===
S) Select Model (auto/mimo/dict)
M) Model Info
Q) Quit
```

### Banner Update

```
╔══════════════════════════════════════════════════════════╗
║  ZOLAI LANGUAGE LEARNING — Master Menu v4.0             ║
║  25,000+ Words • 34 Lessons • 30+ Grammar Rules        ║
║  77 Polysemous Words • 451 Exercises • AI Help          ║
║  ZVS 2018 • SOV • Ergative 'in' • 'hiam' = question   ║
╚══════════════════════════════════════════════════════════╝
```

---

## 6. Wiki Update Plan

### zolai-wiki Structure

```
wiki/
├── grammar/
│   ├── phonology.md          ← UPDATE from Grammar Vol 1
│   ├── morphology.md         ← UPDATE from Grammar Vol 1
│   ├── syntax.md             ← UPDATE from Grammar Vol 1
│   ├── punctuation.md        ← UPDATE from ZVS 2018
│   ├── tones.md              ← NEW from Grammar Vol 1
│   └── zvs2018.md            ← NEW from ZVS rules
├── vocabulary/
│   ├── core-vocab.md         ← UPDATE from comprehensive vocab
│   ├── polysemy.md           ← UPDATE from polysemy DB (77→200+)
│   ├── loanwords.md          ← UPDATE from ZVS adopted words
│   └── wordlist.md           ← UPDATE from freq-ranked vocab
├── curriculum/
│   ├── level-01-basics.md    ← UPDATE from Sinna lessons
│   ├── level-02-intermediate.md
│   ├── level-03-advanced.md
│   └── exercises.md          ← UPDATE from exercises DB
├── culture/
│   ├── zomi-customs.md       ← UPDATE from literature
│   ├── zomi-history.md       ← UPDATE from genealogy
│   └── zomi-proverbs.md     ← NEW from Gentehna stories
├── biblical/
│   ├── bible-study.md        ← UPDATE from study output
│   └── translation-notes.md  ← UPDATE from version comparison
├── concepts/
│   ├── sov-word-order.md     ← UPDATE
│   ├── ergative-in.md        ← UPDATE
│   ├── hiam-question.md      ← UPDATE
│   └── context-meaning.md   ← NEW (polysemy concept)
└── docs/
    ├── getting-started.md    ← UPDATE
    ├── dictionary-usage.md   ← UPDATE
    └── ai-integration.md    ← NEW
```

---

## 7. Data Pipeline

### Source of Truth Hierarchy

```
1. ZVS 2018 Standard (orthography)     → zvs_rules.json
2. Grammar Vol 1 (rules)               → grammar_comprehensive.json
3. Zolai Sinna (lessons)               → sinna_lessons.json
4. Bible Corpus (examples)             → parallel_corpus_v1.jsonl
5. Dictionary (translations)           → dict_zo_en_clean.jsonl
6. Reference Materials (context)       → data/reference/
7. Online Sources (validation)         → paumkim, dalsuum, etc.
```

### Build Order

```
Step 1: Fetch online data (paumkim, dalsuum, tongdot)
Step 2: Merge dictionaries (local + online)
Step 3: Build comprehensive vocab (25K+ words)
Step 4: Build grammar rules (30+ patterns)
Step 5: Build polysemy database (200+ words)
Step 6: Build exercises (1000+ exercises)
Step 7: Build reference index (AI context)
Step 8: Update wiki with all new content
Step 9: Update pcore-brain context
Step 10: Update menu with all new scripts
```

---

## 8. Task Tracker

### 🔴 IN PROGRESS

| Task | Owner | Status | Started | Est. Done |
|------|-------|--------|---------|-----------|
| Combine duplicate vocab scripts | conductor | BLOCKED | — | — |
| Combine duplicate Bible scripts | conductor | BLOCKED | — | — |

### ⏳ QUEUED (High Priority)

| Task | Owner | Status | Depends On |
|------|-------|--------|------------|
| Generate 10K synthetic training pairs | — | QUEUED | Seed data (ready) |
| Set up Kaggle notebook | — | QUEUED | KAGGLE_SETUP.md (ready) |
| Fine-tune Qwen2.5-3B on Kaggle T4 | — | QUEUED | Kaggle setup |
| Build custom Zolai tokenizer | — | QUEUED | — |
| Deploy Argilla annotation server | — | QUEUED | — |
| Create evaluation benchmark suite | — | QUEUED | — |
| Build polysemy DB (77→200+) | — | QUEUED | — |
| Fix Sinna lesson parsing | — | QUEUED | — |

### ✅ COMPLETED

| Task | Date | Commit |
|------|------|--------|
| Convert all PDFs to markdown | 2026-09-07 | — |
| Copy reference materials to workspace | 2026-09-07 | — |
| Build 8 integration scripts | 2026-09-07 | `42e3f2b` |
| Run all 8 scripts | 2026-09-07 | — |
| Fix exercise script regex | 2026-09-07 | — |
| Pass ruff + py_compile on all scripts | 2026-09-07 | — |
| Git commit 8 NEW scripts | 2026-09-07 | `42e3f2b` |
| Update menu.sh (model list + options) | 2026-09-07 | `30a7c61` |
| Download paumkim/zomi-dataset | 2026-09-07 | — |
| Integrate dalsuum dictionary | 2026-09-07 | `42e3f2b` |
| Download TongDot + Glosbe + zomi-tedim-ai | 2026-09-07 | — |
| Update pcore-brain context | 2026-09-06 | — |
| Create seed data (500 pairs) | 2026-09-07 | `42e3f2b` |
| Update menu.sh with training options | 2026-09-07 | `30a7c61` |

---

## 9. Daily/Weekly/Monthly Plan

### Daily Tasks (15-30 min)

| Task | Time | Description |
|------|------|-------------|
| Check git status | 2 min | Ensure clean tree |
| Run ruff on changed scripts | 5 min | Lint check |
| Run py_compile on new scripts | 5 min | Syntax check |
| Update progress-tracker.md | 5 min | Log what was done |
| Search for new Zolai resources | 10 min | Web search for new data |

### Weekly Tasks (2-4 hr)

| Task | Day | Description |
|------|-----|-------------|
| Merge duplicate scripts | Monday | Combine 2-3 scripts |
| Download new data source | Tuesday | Fetch online resource |
| Update wiki section | Wednesday | Update grammar/vocab/culture |
| Build/fix vocab pipeline | Thursday | Improve vocab extraction |
| Test AI integration | Friday | Verify pcore-brain works |
| Git commit + push | Friday | Clean tree, push all |
| Review & plan next week | Sunday | Update master plan |

### Monthly Tasks (1-2 days)

| Task | When | Description |
|------|------|-------------|
| Full ecosystem audit | 1st of month | Check all 10 repos |
| Update context/*.md | 1st of month | Refresh 6-file set |
| Update progress-tracker.md | 1st of month | Full progress review |
| Download new datasets | 15th of month | Check for new online data |
| Regenerate Bible study files | 15th of month | Re-run with latest data |
| Update pcore-brain context | 15th of month | Sync AI context |
| Review polysemy DB | 15th of month | Add new context-dependent words |

### Quarterly Tasks (1 week)

| Task | When | Description |
|------|------|-------------|
| Full data rebuild | Every 3 months | Rebuild all data from scratch |
| Script consolidation review | Every 3 months | Check if scripts can be merged |
| Online resource check | Every 3 months | Find new Zolai resources |
| Wiki content audit | Every 3 months | Verify all wiki pages current |
| Model evaluation | Every 3 months | Test AI models on Zolai tasks |

---

## 10. Git Workflow

### Commit Strategy

```
feat(bible): <description>     — new feature
fix(bible): <description>      — bug fix
refactor(bible): <description> — code restructuring
docs(bible): <description>     — documentation only
chore(bible): <description>    — maintenance
test(bible): <description>     — test additions
```

### Commit Order (This Session)

```
1. feat(bible): add reference material integration scripts
   Files: 8 new .py files in scripts/bible/
   
2. feat(bible): consolidate vocab scripts into vocab_builder.py
   Files: Replace 5 scripts with 1
   
3. feat(bible): consolidate Bible scripts into bible_data_builder.py
   Files: Replace 8 scripts with 2
   
4. feat(bible): update menu.sh with all new script options
   Files: menu.sh
   
5. feat(bible): add online data fetcher for paumkim/dalsuum/tongdot
   Files: data_fetcher.py
   
6. fix(bible): correct vocab extraction to produce 25K+ entries
   Files: vocab_builder.py
   
7. docs(bible): add master plan and progress tracker updates
   Files: MASTER_PLAN.md, progress-tracker.md
```

### Pre-commit Checklist

```
[ ] All new scripts pass ruff check
[ ] All new scripts pass py_compile
[ ] No hardcoded data paths (use Path(__file__).resolve().parents[3])
[ ] No secrets or API keys in code
[ ] Data files are gitignored (data/)
[ ] Only scripts/ committed, not data/
[ ] Commit message follows conventional commits
[ ] Tree is clean (git status shows 0 changes)
```

---

## Appendix A: File Sizes Summary

| Category | Files | Total Size |
|----------|-------|------------|
| Scripts | 40 | 15,240 lines |
| Learning Data | 20 | 25 MB |
| Dictionary Data | 6 | 126 MB |
| Bible Data | 19 | 999 MB |
| Reference Data | 23 | 6.5 MB |
| **Total** | **108** | **~1.2 GB** |

## Appendix B: Online Resource URLs

| Resource | URL |
|----------|-----|
| paumkim/zomi-dataset | https://github.com/paumkim/zomi-dataset |
| dalsuum/zolai-dictionary | https://github.com/dalsuum/zolai-dictionary |
| zolai-dictionary (live) | https://zolai-dictionary.web.app |
| zomi-tedim-ai (HuggingFace) | https://huggingface.co/zomi-tedim-ai |
| TongDot | https://www.tongdot.com |
| Glosbe Tedim-English | https://glosbe.com/ctd/en |
| Zomi eLibrary | https://zomielibrary.com |
| Zolai Grammar PDF | https://zomielibrary.com/wp-content/uploads/2025/08/Zolai-Grammar.pdf |
| Joshua Project | https://test.joshuaproject.net/languages/ctd |
| Zomi Spelling Guide | https://paumkim.github.io/zomi-website/ |
| Tedim-English-Burmese Handbook | https://leanpub.com/tedim-english-burmese-handbook |
| Zolai Grammar (KuPDF) | https://kupdf.net/download/zolai-grammar-zomi-nam_59b9462008bbc5e906894cd3_pdf |
| Zolai Sinna (KuPDF) | https://kupdf.net/download/laibu-zolai-sinna_58a867d46454a7ec3eb1e90e_pdf |
| Zolai Sim Bu (Scribd) | https://www.scribd.com/document/15908808/Zolai-Sim-Bu-Tan-Khat-Laibu-Etdikna |

---

## 11. Data Sources & Attribution

**Full credits:** See `data/CREDITS.md`

### Why We Use the Bible

The Bible is our **primary training corpus** because it is the **only complete, trusted, EN/ZO parallel corpus** available for Tedim Zolai:

- **31,102 parallel verses** (EN↔ZO) — no other source comes close
- **Complete text** — all 66 books, covering all registers (poetry, narrative, dialogue, law)
- **Multiple versions** — TDB77, Tedim2010, Hakha, Falam, Paite for cross-linguistic comparison
- **Community-validated** — decades of translation work by native speakers
- **Publicly available** — open access for language preservation
- **Rich grammar coverage** — all patterns (SOV, tense markers, aspect, negation, questions)

**Note:** We use the Bible as a *language learning corpus*, not for religious purposes.
The Bible provides the most comprehensive, well-structured text in Tedim Zolai.

### Data Inventory (Current)

| Category | Source | Size | Entries | Status |
|----------|--------|------|---------|--------|
| Bible | dalsuum/bible-master | 67 JSON files | 31,102 verses | ✅ Integrated |
| Dictionary (ZO→EN) | ZomiLanguage/dictionary | 11MB | 93,931 entries | ✅ Integrated |
| Dictionary (EN→ZO) | ZomiLanguage/dictionary | 56MB | 112,220 entries | ✅ Integrated |
| Dictionary (trilingual) | dalsuum/zolai-dictionary | 6.1MB | 7,861 headwords | ✅ Downloaded |
| Dictionary (merged) | dalsuum + local | 6.1MB | 7,841 entries | ✅ Built |
| Dictionary (TongDot) | paumkim/zomi-dataset | 681KB | 5,004 entries | ✅ Downloaded |
| Corpus (clean) | paumkim/zomi-dataset | 208MB | 3M+ sentences | ✅ Downloaded |
| Reference (grammar) | Local PDFs | 6.5MB | 23 files | ✅ Converted |
| Language learning | Generated | 25MB | 13 files | ✅ Built |
| Vocabulary | Generated | 1.2MB | 23,383 words | ✅ Built |
| Vocabulary (master) | Generated | 12MB | 98,976 words | ✅ Built |
| Vocabulary (online) | Generated | 12MB | 533,444 words | ✅ Built |
| Grammar patterns | Generated | 1.2MB | 1,188 patterns | ✅ Built |
| Phrases | Generated | 2.3MB | 5,000 pairs | ✅ Built |
| Polysemy | Generated | 20KB | 77 words | ✅ Built |
| Proverbs | Bible + worship songs | 1.5MB | 7,736 entries | ✅ Built |
| Conversational | paumkim | 1.6MB | 8,913 entries | ✅ Built |
| Cross-language | Bible JSONs | 2.1MB | 90,255 entries | ✅ Built |
| Training seed | Generated | 50KB | 500 pairs | ✅ Built |
| Training seed (fixed) | Generated | 50KB | 500 pairs | ✅ Built |
| Training test | Generated | 2KB | 10 pairs | ✅ Built |

### Data Flow Diagram

```
                    ┌─────────────────────────────────────┐
                    │         DATA SOURCES                │
                    ├─────────────────────────────────────┤
                    │ Bible (dalsuum/bible-master)        │
                    │ Dictionary (ZomiLanguage, dalsuum)  │
                    │ Corpus (paumkim/zomi-dataset)       │
                    │ Reference (local PDFs)              │
                    │ Online (Glosbe, Joshua Project)     │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       INTEGRATION SCRIPTS           │
                    ├─────────────────────────────────────┤
                    │ integrate_dalsuum.py                │
                    │ extract_corpus_vocab.py             │
                    │ extract_proverbs.py                 │
                    │ integrate_conversational.py         │
                    │ build_cross_language.py             │
                    │ build_comprehensive_vocab.py        │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       PROCESSED DATA                │
                    ├─────────────────────────────────────┤
                    │ dict_zo_en_clean.jsonl (93K)        │
                    │ dict_canonical_clean.jsonl (112K)   │
                    │ vocab_master.jsonl (98K)           │
                    │ proverbs.jsonl                      │
                    │ conversational.jsonl                │
                    │ cross_language.jsonl                 │
                    │ grammar_patterns.jsonl (1,188)      │
                    │ phrases.jsonl (5,000)               │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
    │   zolai-core      │ │   zolai-web   │ │  zolai-tauri      │
    │   (RAG + ngram)   │ │   (online)    │ │  (offline)        │
    └───────────────────┘ └───────────────┘ └───────────────────┘
```

---

## 12. Usage Guide

### How to Use Each Data Source

| Data File | Format | How to Use |
|-----------|--------|------------|
| `dict_zo_en_clean.jsonl` | JSONL | Zolai→English lookup: `{"headword": "pasian", "translation": "God"}` |
| `dict_canonical_clean.jsonl` | JSONL | English→Zolai lookup: `{"headword": "God", "translation": "pasian"}` |
| `vocab_master.jsonl` | JSONL | Vocabulary list: `{"word": "pasian", "frequency": 1234, "pos": "noun"}` |
| `grammar_patterns.jsonl` | JSONL | Grammar rules: `{"pattern": "SOV", "example": "Mi in nek hi"}` |
| `phrases.jsonl` | JSONL | Multi-word expressions: `{"phrase": "Pasian in", "translation": "God (ergative)"}` |
| `parallel_corpus_v1.jsonl` | JSONL | Parallel verses: `{"zo": "...", "en": "...", "ref": "GEN 1:1"}` |
| `proverbs.jsonl` | JSONL | Proverbs/sayings: `{"zo": "...", "en": "...", "type": "proverb"}` |
| `conversational.jsonl` | JSONL | Spoken language: `{"zo": "...", "en": "...", "context": "casual"}` |
| `cross_language.jsonl` | JSONL | Comparative: `{"concept": "God", "tedim": "pasian", "hakha": "pathian"}` |

### For AI Training (RAG)

1. Load `dict_zo_en_clean.jsonl` for word lookups
2. Load `vocab_master.jsonl` for vocabulary context
3. Load `grammar_patterns.jsonl` for grammar rules
4. Load `phrases.jsonl` for multi-word expressions
5. Load `parallel_corpus_v1.jsonl` for example sentences
6. Inject relevant context into AI prompts

### For Language Learning

1. Start with `vocab_master.jsonl` (sorted by frequency)
2. Use `grammar_patterns.jsonl` for progressive lessons
3. Practice with `parallel_corpus_v1.jsonl` examples
4. Learn idioms from `proverbs.jsonl`
5. Study real usage from `conversational.jsonl`

### For Cross-Linguistic Research

1. Use `cross_language.jsonl` for vocabulary comparison
2. Compare Bible versions across Chin languages
3. Analyze grammar patterns across dialects

---

## 13. Coverage Gaps & Roadmap

### What We Have ✅

- [x] Bible parallel corpus (31,102 verses)
- [x] Dictionary (93K ZO→EN + 112K EN→ZO)
- [x] Vocabulary (23,383 words)
- [x] Grammar patterns (1,188)
- [x] Phrases (5,000)
- [x] Polysemy (77 context-dependent words)
- [x] Reference materials (23 files)
- [x] Online corpus (208MB)

### What We're Missing ❌

| Gap | Priority | Source | Status |
|-----|----------|--------|--------|
| Audio/pronunciation | HIGH | Joshua Project audio Bible | 🔲 Need to download |
| Proverbs/idioms | HIGH | Bible + worship songs | ✅ DONE — 7,736 proverbs |
| Conversational data | HIGH | paumkim (1.6MB) | ✅ DONE — 8,913 entries |
| Cross-language comparison | HIGH | 4 Bible versions | ✅ DONE — 90,255 entries |
| Technical vocabulary | MEDIUM | zomipedia + TongDot | 🔲 Can extract now |
| Dialect variations | MEDIUM | paumkim articles | 🔲 Can extract now |
| Proficiency tests | MEDIUM | Need to create | 🔲 Framework needed |
| CEFR alignment | LOW | Need to map levels | 🔲 Research needed |
| Writing system samples | LOW | Need handwriting data | 🔲 Search needed |
| Sign language | LOW | No data available | ❌ Not available |

### Improvement Roadmap

**Phase 1: Data Integration (Current)**
- [x] Download all online data sources
- [x] Create integration scripts
- [x] Merge dictionaries
- [x] Extract vocabulary from corpus
- [x] Build cross-language comparison

**Phase 2: Content Enrichment**
- [x] Extract proverbs from Bible
- [x] Build conversational database
- [ ] Create proficiency test framework
- [ ] Add technical vocabulary

**Phase 3: AI Enhancement**
- [x] Update pcore-brain context with new data
- [ ] Improve RAG context injection
- [ ] Add polysemy rules to AI prompts
- [ ] Test AI glossing accuracy

**Phase 4: Learning System**
- [ ] Update curriculum with new data
- [ ] Add audio pronunciation support
- [ ] Create interactive exercises
- [ ] Build spaced repetition system

**Phase 5: Community**
- [ ] Publish datasets on HuggingFace/Kaggle
- [ ] Create contributor guidelines
- [ ] Add data correction feedback loop
- [ ] Build community validation system

---

## 14. Documentation Updates

### Files Updated (2026-09-07)

| File | Changes |
|------|---------|
| `context/MASTER_PLAN.md` | Added sections 11-14: Data Sources, Usage Guide, Gaps, Docs |
| `data/CREDITS.md` | NEW: Comprehensive attribution for all data sources |
| `context/architecture.md` | Added data flow diagram + data sources |
| `context/project-overview.md` | Added data sources + Bible justification |
| `context/progress-tracker.md` | Added session 2026-09-07 work |
| `.github/README.md` | Added credits + data sources section |
| `zolai-landing/src/components/Credits.tsx` | NEW: Credits component |
| `zolai-wiki/README.md` | Added data sources section |

### What Each Doc Covers

- **MASTER_PLAN.md** — Everything tracker: scripts, data, tasks, pipeline, gaps
- **CREDITS.md** — All data sources with attribution and license info
- **architecture.md** — System design, data flow, boundaries
- **project-overview.md** — Org scope, repos, mission
- **progress-tracker.md** — Session-by-session work log
- **AGENTS.md** (per repo) — Agent guidance for each repo

---

## 15. Sustainable Maintenance System

### Weekly 30-min Review (Sunday)
- Check git status all repos
- Run ruff on changed Python files
- Update progress-tracker.md
- Search for new Zolai resources

### Monthly 2-hour Audit (1st of Month)
- Full ecosystem check (all 10 repos)
- Refresh context/*.md files
- Download new datasets
- Review MASTER_PLAN.md

### Quarterly 1-day Rebuild (Every 3 Months)
- Rebuild all data from scratch
- Review scripts for consolidation
- Update wiki content
- Test AI integration

### File Tracking System
| Tool | Purpose | Location |
|------|---------|----------|
| progress-tracker.md | Session work log | context/ |
| MASTER_PLAN.md | Everything tracker | zolai-datasets/docs/ |
| Git commits | Version control | All repos |
| git log --oneline | Change history | All repos |

---

## 16. Training Pipeline

### Seed Data
- `data/training/seed_data_500_fixed.jsonl` — 500 Zolai-EN pairs
- 389 from Bible, 111 from dictionary
- Ready for synthetic generation

### Synthetic Data Generation
- Script: `scripts/bible/generate_synthetic_data.py`
- Target: 10,000 pairs
- Method: LLM-based (pcore-brain API)
- Quality scoring: 8-feature pipeline

### Kaggle Setup
- Guide: `context/KAGGLE_SETUP.md` (238 lines)
- GPU: T4 (30 hrs/week free)
- Model: Qwen2.5-3B

### Training Config
- Model: Qwen2.5-3B (3B params)
- Method: LoRA SFT (r=16, alpha=32)
- Optimizer: AdamW 8-bit, lr 1e-4
- Schedule: cosine
- Batch: 16×2 effective 32
- Epochs: 1-3
- Context: 2048 tokens

### Evaluation
- BLEU for translation
- F1 for classification
- Native speaker review for quality
