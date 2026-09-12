# Zolai Database — Full Integrity Report
**Generated:** 2026-09-12 18:29
**Database:** 277.9 MB

## 1. Language Coverage (ZO / EN / MY)

| Table | Zolai | English | Myanmar | Total |
|-------|-------|---------|---------|-------|
| dictionary | 93,931 (100%) | 93,931 (100%) | 6,097 (6.5%) | 93,931 |
| bible_verses | 29,689 (97.1%) | 29,151 (95.4%) | 28,785 (94.2%) | 30,569 |
| dictionary_en_zo | — | 129,853 (100%) | 2 (0.0%) | 129,853 |
| translations | — | — | — | 212,754 |
| word_alignments | — | — | — | 385,120 |

**⚠️ CRITICAL GAPS:**
- Dictionary Myanmar: only **6.5%** have Myanmar translations (87,834 entries missing)
- Bible Myanmar: **94.2%** — good coverage
- Dictionary EN→ZO Myanmar: **0.0%** — nearly empty

## 2. Version Tracking

| Version | Count |
|---------|-------|
| v1.0 | 93,693 |
| verified_v1 | 238 |

## 3. ZVS 2018 Compliance

| Status | Count |
|--------|-------|
| pending | 92,931 |
| passed | 1,000 |

## 4. Dictionary Sources

| Source | Count | % |
|--------|-------|---|
| zo_en_wordlist | 36,459 | 38.8% |
| combined | 25,066 | 26.7% |
| bible_zo_en | 17,180 | 18.3% |
| zomidictionary | 8,012 | 8.5% |
| zvs_master | 4,179 | 4.4% |
| bible_learned | 2,411 | 2.6% |
| supplement | 556 | 0.6% |
| singlewords | 67 | 0.1% |
| test_verify | 1 | 0.0% |

## 5. Dictionary Quality — Wrong Examples & Usage Issues

### English field has JSON artifacts:
- ` embed coreldraw` → `["swastika"]` [zomidictionary]
- `& adv` → `["nearby"]` [combined]
- `& n` → `["convoy"]` [zomidictionary]
- `'dawn` → `["say"]` [bible_learned]
- `'en` → `["make"]` [bible_learned]
- `'laban'` → `["thus"]` [bible_learned]
- `'na` → `["draw"]` [bible_learned]
- `'tu` → `["came"]` [bible_learned]
- `(")` → `["ditto mark"]` [combined]
- `(a aw)a thel` → `["raucous"]` [combined]

### Bracket artifacts in English:
- ` embed coreldraw` → `["swastika"]`
- `& adv` → `["nearby"]`
- `& n` → `["convoy"]`
- `'dawn` → `["say"]`
- `'en` → `["make"]`
- `'laban'` → `["thus"]`
- `'na` → `["draw"]`
- `'tu` → `["came"]`
- `(")` → `["ditto mark"]`
- `(a aw)a thel` → `["raucous"]`

## 6. Data Not Yet in Database

| Data | Status |
|------|--------|
| Dictionary (ZO→EN) | ✅ 93,931 entries |
| Dictionary (EN→ZO) | ✅ 129,853 entries |
| Bible verses | ✅ 30,569 verses |
| Word alignments | ✅ 385,120 alignments |
| Translations | ✅ 212,754 pairs |
| Phrases | ✅ 5,000 phrases |
| Grammar patterns | ✅ 5,547 patterns |
| Vocabulary | ✅ 94,458 words |
| Training exercises | ✅ 81,805 exercises |
| Proverbs | ✅ 7,736 proverbs |
| Word usage | ✅ 60,365 profiles |
| Word collocations | ✅ 5,000 pairs |
| Bible context | ✅ 1,228 analyses |
| Audit findings | ✅ 713 findings |
| Wiki lessons | ⚠️ 0 rows (needs population) |

## 7. Recommendations

### P0 — Critical
1. **Myanmar translations**: Only 6.5% of dictionary has Myanmar. Use Gemini to fill ~88K missing entries
2. **Fix bracket artifacts**: ~90K entries have `["..."]` format in English field — clean them

### P1 — Important
3. **ZVS compliance**: 92,931 entries still `pending` — run full ZVS check
4. **Wiki lessons**: Empty table — import from zolai-wiki grammar files
5. **Wrong examples**: Fix entries where English field contains JSON artifacts or Bible verse references instead of translations

### P2 — Nice to have
6. **Archive JSONL files**: DB is 278MB vs JSONL's ~4.7GB — archive old JSONL to save space
7. **Duplicate entries**: Some Zolai words appear multiple times — deduplicate with priority rules