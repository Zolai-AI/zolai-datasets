#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZOLAI LANGUAGE LEARNING — Menu V2
#  Bible Tools + AI Learning + Training + Data Integration
#  31,102 sentences • 93,931 dictionary entries • 8 tools
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DATA="$WORKSPACE/data"
PYTHON="python3"

# Colors
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[0;34m' C='\033[0;36m' M='\033[0;35m' NC='\033[0m'

banner() {
  clear
  echo -e "${C}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${C}║${NC}  ${M}ZOLAI LANGUAGE LEARNING${NC} — Bible Tools Menu V2        ${C}║${NC}"
  echo -e "${C}║${NC}  ${B}31,102 Sentences • 93,931 Dict Entries • AI Tools   ${C}║${NC}"
  echo -e "${C}║${NC}  ${B}ZVS 2018 • SOV • Ergative 'in' • 'hiam' = question  ${C}║${NC}"
  echo -e "${C}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

# ── Logging ─────────────────────────────────────────────────
LOG_DIR="$DATA/dictionary/bible_study"
LOG_FILE="$LOG_DIR/menu_log.jsonl"
mkdir -p "$LOG_DIR"

log_event() {
  local event="$1" detail="$2"
  echo "{\"ts\":\"$(date -Iseconds)\",\"event\":\"$event\",\"detail\":\"$detail\"}" >> "$LOG_FILE"
}

# ── Model selection ─────────────────────────────────────────
select_model() {
  echo -e "${Y}Available free models:${NC}"
  echo -e "  ${G}1${NC}) auto (best available)       ${C}(recommended, fast ✅)${NC}"
  echo -e "  ${G}2${NC}) mimo-v2.5-free              ${C}(good, ~7s ✅)${NC}"
  echo -e "  ${G}3${NC}) No AI — dictionary only"
  echo ""
  read -p "  Select model [1]: " choice
  case "$choice" in
    2)  MODEL="opencode/mimo-v2.5-free"; AI_FLAG="" ;;
    3)  MODEL=""; AI_FLAG="--no-ai" ;;
    *)  MODEL="auto"; AI_FLAG="" ;;
  esac
  echo -e "  → Using: ${G}${MODEL:-dict-only}${NC}"
  log_event "model_select" "${MODEL:-dict-only}"
  echo ""
}

# ── Book selection ──────────────────────────────────────────
select_books() {
  echo -e "${Y}Book selection:${NC}"
  echo -e "  ${G}1${NC}) All 66 books (full Bible)"
  echo -e "  ${G}2${NC}) Old Testament only (39 books)"
  echo -e "  ${G}3${NC}) New Testament only (27 books)"
  echo -e "  ${G}4${NC}) Pentateuch (GEN,EXO,LEV,NUM,DEU)"
  echo -e "  ${G}5${NC}) Psalms + Proverbs"
  echo -e "  ${G}6${NC}) Gospels (MAT,MRK,LUK,JHN)"
  echo -e "  ${G}7${NC}) Historical narrative (JOS-EST)"
  echo -e "  ${G}8${NC}) Poetic (JOB,PSA,PRO,ECC,SNG)"
  echo -e "  ${G}9${NC}) Prophetic (ISA-MAL)"
  echo -e "  ${G}A${NC}) Single book (type code)"
  echo -e "  ${G}B${NC}) Custom list (comma-separated)"
  echo ""
  read -p "  Select [1]: " choice
  case "$choice" in
    2)  BOOK_FLAG="--book GEN,EXO,LEV,NUM,DEU,JOS,JUG,RUT,1SA,2SA,1KI,2KI,1CH,2CH,EZR,NEH,EST" ;;
    3)  BOOK_FLAG="--book MAT,MRK,LUK,JHN,ACT,ROM,1CO,2CO,GAL,EPH,PHP,COL,1TH,2TH,1TI,2TI,TIT,PHM,HEB,JAS,1PE,2PE,1JN,2JN,3JN,JUD,REV" ;;
    4)  BOOK_FLAG="--book GEN,EXO,LEV,NUM,DEU" ;;
    5)  BOOK_FLAG="--book PSA,PRO" ;;
    6)  BOOK_FLAG="--book MAT,MRK,LUK,JHN" ;;
    7)  BOOK_FLAG="--book JOS,JUG,RUT,1SA,2SA,1KI,2KI,1CH,2CH,EZR,NEH,EST" ;;
    8)  BOOK_FLAG="--book JOB,PSA,PRO,ECC,SNG" ;;
    9)  BOOK_FLAG="--book ISA,JER,LAM,EZK,DAN,HOS,JOE,AMO,OBA,JON,MIC,NAM,HAB,ZEP,HAG,ZEC,MAL" ;;
    A|a)  read -p "  Book code: " bc; BOOK_FLAG="--book ${bc^^}" ;;
    B|b)  read -p "  Books (comma-sep): " bs; BOOK_FLAG="--book ${bs^^}" ;;
    *)  BOOK_FLAG="" ;;
  esac
}

# ── Core Bible commands ────────────────────────────────────

cmd_study() {
  banner
  select_model
  select_books
  echo -e "${G}Starting study...${NC}"
  echo ""
  log_event "study_start" "${MODEL:-dict-only} $BOOK_FLAG"
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG $BOOK_FLAG "$@"
  log_event "study_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_resume() {
  banner
  select_model
  echo -e "${G}Resuming (skipping completed books)...${NC}"
  echo ""
  log_event "resume_start" ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG --resume "$@"
  log_event "resume_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_test_one() {
  banner
  select_model
  echo -e "${G}Testing with Genesis (1 book)...${NC}"
  echo ""
  log_event "test_start" "GEN"
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG --book GEN "$@"
  echo ""
  echo -e "${Y}Spot-check results:${NC}"
  head -10 "$DATA/dictionary/bible_study/01_GEN_study.jsonl" | $PYTHON -c "
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if d.get('type') == 'vocab':
        print(f\"  {d.get('word','?'):12s} → {d.get('gloss','?'):30s}  [{d.get('source','?')}]\")" 2>/dev/null || true
  log_event "test_done" "GEN"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_stats() {
  banner
  echo -e "${Y}Bible Study Statistics:${NC}"
  echo ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" --stats
  echo ""
  # Count study files
  local study_count
  study_count=$(ls "$DATA/dictionary/bible_study/"*_study.jsonl 2>/dev/null | wc -l)
  echo -e "  ${C}Bible study files: ${study_count}/66${NC}"
  # AI cache
  if [ -f "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl" ]; then
    local cache_count
    cache_count=$(wc -l < "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl")
    echo -e "  ${C}AI cache: ${cache_count} entries${NC}"
  fi
  # Knowledge base files
  echo -e "  ${Y}Knowledge Base:${NC}"
  for f in grammar_patterns vocabulary_db translation_pairs phrases verb_database particle_database book_summaries version_comparison; do
    local fp="$DATA/bible/${f}_v1.jsonl"
    if [ -f "$fp" ]; then
      local cnt
      cnt=$(wc -l < "$fp")
      echo -e "    ${G}✅ ${f}_v1.jsonl: ${cnt} entries${NC}"
    else
      echo -e "    ${R}❌ ${f}_v1.jsonl: missing${NC}"
    fi
  done
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Dictionary commands ────────────────────────────────────

cmd_check_dict() {
  while true; do
    banner
    echo -e "${Y}📖 Dictionary Search (ZO↔EN)${NC}"
    echo ""
    echo -e "  ${G}1${NC}) Search Zolai → English"
    echo -e "  ${G}2${NC}) Search English → Zolai"
    echo -e "  ${G}3${NC}) Browse common Zolai words (top 50)"
    echo -e "  ${G}4${NC}) Browse common English words (top 50)"
    echo -e "  ${G}5${NC}) Word info (both directions)"
    echo -e "  ${G}0${NC}) Back to main menu"
    echo ""
    read -p "  Select [1]: " choice
    case "$choice" in
      2) cmd_dict_en_zo ;;
      3) cmd_dict_browse_zo ;;
      4) cmd_dict_browse_en ;;
      5) cmd_dict_both ;;
      0|q) return ;;
      *) cmd_dict_zo_en ;;
    esac
  done
}

cmd_dict_zo_en() {
  echo ""
  read -p "  Enter Zolai word (or part): " query
  if [ -z "$query" ]; then return; fi
  echo ""
  $PYTHON -c "
import json, sys
q = sys.argv[1].strip().lower()
path = sys.argv[2]
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('zolai','').strip().lower()
        if q in hw:
            eng = d.get('english','')
            if isinstance(eng, list):
                eng_str = ' | '.join(str(e) for e in eng[:3])
            else:
                eng_str = str(eng)
            freq = d.get('frequency', 0)
            if q == hw: score = 3
            elif hw.startswith(q): score = 2
            else: score = 1
            found.append((score, freq, hw, eng_str))
found.sort(key=lambda x: (-x[0], -x[1]))
if found:
    print(f'  Found {len(found)} matches:\n')
    for score, freq, hw, eng in found[:30]:
        marker = ' ← exact' if score == 3 else ''
        print(f'  {hw:30s} → {eng}{marker}')
else:
    print(f'  No matches for \"{q}\"')
" "$query" "$DATA/dictionary/processed/dict_zo_en_clean.jsonl"
  echo ""
  read -p "  Press Enter..."
}

cmd_dict_en_zo() {
  echo ""
  read -p "  Enter English word (or part): " query
  if [ -z "$query" ]; then return; fi
  echo ""
  $PYTHON -c "
import json, sys
q = sys.argv[1].strip().lower()
path = sys.argv[2]
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip().lower()
        if q in hw:
            trans = d.get('translations',[])
            if isinstance(trans, list):
                good = []
                seen = set()
                for t in trans:
                    t = str(t).strip()
                    tl = t.lower()
                    if len(good) >= 3: break
                    if not t or tl in ('', '1', '2', '3'): continue
                    if tl == hw or tl == q: continue
                    if tl == hw + 's' or tl == hw + 'es': continue
                    if all(c.isascii() and (c.isalpha() or c in ' ,.()-=:\"') for c in t): continue
                    if '1.' in t[:10] or 'n. 1.' in t[:10]: continue
                    if tl in seen: continue
                    seen.add(tl)
                    good.append(t[:100])
                trans_str = ' | '.join(good) if good else '(no Zolai translation)'
            else:
                trans_str = str(trans)[:100]
            if q == hw: score = 3
            elif hw.startswith(q): score = 2
            else: score = 1
            found.append((score, hw, trans_str))
found.sort(key=lambda x: (-x[0], x[1]))
if found:
    print(f'  Found {len(found)} matches:\n')
    for score, hw, trans in found[:25]:
        marker = ' ← exact' if score == 3 else ''
        print(f'  {hw:30s} → {trans}{marker}')
else:
    print(f'  No matches for \"{q}\"')
" "$query" "$DATA/dictionary/processed/dict_canonical_clean.jsonl"
  echo ""
  read -p "  Press Enter..."
}

cmd_dict_both() {
  echo ""
  read -p "  Enter any word: " query
  if [ -z "$query" ]; then return; fi
  echo ""
  echo -e "  ${Y}Zolai → English:${NC}"
  $PYTHON -c "
import json, sys
q = sys.argv[1].strip().lower()
path = sys.argv[2]
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('zolai','').strip().lower()
        if q == hw or q in hw:
            eng = d.get('english','')
            if isinstance(eng, list):
                eng_str = ' | '.join(str(e)[:40] for e in eng[:3])
            else:
                eng_str = str(eng)[:80]
            found.append((hw, eng_str))
            if len(found) >= 5: break
if found:
    for hw, eng in found:
        print(f'    {hw:25s} → {eng}')
else:
    print(f'    (none found)')
" "$query" "$DATA/dictionary/processed/dict_zo_en_clean.jsonl"
  echo ""
  echo -e "  ${Y}English → Zolai:${NC}"
  $PYTHON -c "
import json, sys
q = sys.argv[1].strip().lower()
path = sys.argv[2]
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip().lower()
        if q == hw or q in hw:
            trans = d.get('translations',[])
            if isinstance(trans, list):
                trans_str = ' | '.join(str(t)[:40] for t in trans[:3] if isinstance(t,str))
            else:
                trans_str = str(trans)[:80]
            found.append((hw, trans_str))
            if len(found) >= 5: break
if found:
    for hw, trans in found:
        print(f'    {hw:25s} → {trans}')
else:
    print(f'    (none found)')
" "$query" "$DATA/dictionary/processed/dict_canonical_clean.jsonl"
  echo ""
  read -p "  Press Enter..."
}

cmd_dict_browse_zo() {
  echo ""
  echo -e "  ${Y}Top 50 Zolai words by frequency:${NC}"
  echo ""
  $PYTHON -c "
import json, sys
path = sys.argv[1]
entries = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('zolai','').strip().lower()
        eng = d.get('english','')
        if isinstance(eng, list):
            eng_str = str(eng[0])[:30] if eng else '?'
        else:
            eng_str = str(eng)[:30]
        entries.append((hw, eng_str))
for hw, eng in entries[:50]:
    print(f'  {hw:25s} → {eng}')
" "$DATA/dictionary/processed/dict_zo_en_clean.jsonl"
  echo ""
  read -p "  Press Enter..."
}

cmd_dict_browse_en() {
  echo ""
  echo -e "  ${Y}Top 50 English words:${NC}"
  echo ""
  $PYTHON -c "
import json, sys
path = sys.argv[1]
entries = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip()
        trans = d.get('translations',[])
        if isinstance(trans, list):
            trans_str = str(trans[0])[:30] if trans else '?'
        else:
            trans_str = str(trans)[:30]
        entries.append((hw, trans_str))
for hw, trans in entries[:50]:
    print(f'  {hw:25s} → {trans}')
" "$DATA/dictionary/processed/dict_canonical_clean.jsonl"
  echo ""
  read -p "  Press Enter..."
}

# ── Bible Engine commands ──────────────────────────────────

cmd_engine_study() {
  banner
  echo -e "${Y}📖 Bible Engine — Full Verse Analysis (Study Mode)${NC}"
  echo ""
  echo -e "  ${G}1${NC}) Single book (type code)"
  echo -e "  ${G}2${NC}) All 66 books (full Bible)"
  echo -e "  ${G}3${NC}) Pentateuch (GEN,EXO,LEV,NUM,DEU)"
  echo -e "  ${G}4${NC}) Gospels (MAT,MRK,LUK,JHN)"
  echo ""
  read -p "  Select [1]: " choice
  case "$choice" in
    2)  BOOK_FLAG="--all" ;;
    3)  BOOK_FLAG="--book GEN,EXO,LEV,NUM,DEU" ;;
    4)  BOOK_FLAG="--book MAT,MRK,LUK,JHN" ;;
    A|a)  read -p "  Book code: " bc; BOOK_FLAG="--book ${bc^^}" ;;
    *)  read -p "  Book code [GEN]: " bc; BOOK_FLAG="--book $(echo "${bc:-GEN}" | tr '[:lower:]' '[:upper:]')" ;;
  esac
  echo ""
  echo -e "${G}Starting Bible Engine analysis...${NC}"
  echo ""
  log_event "engine_study_start" "$BOOK_FLAG"
  $PYTHON "$SCRIPT_DIR/bible_engine.py" --study $BOOK_FLAG
  log_event "engine_study_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_engine_learn() {
  banner
  echo -e "${Y}🎓 Progressive Learning (8 Levels)${NC}"
  echo ""
  echo -e "  ${G}1${NC}) Beginner — Common words (top 100)"
  echo -e "  ${G}2${NC}) Elementary — Basic phrases (200 words)"
  echo -e "  ${G}3${NC}) Intermediate — Sentence patterns (500 words)"
  echo -e "  ${G}4${NC}) Upper-Intermediate — Grammar structures (1000 words)"
  echo -e "  ${G}5${NC}) Advanced — Complex sentences (2000 words)"
  echo -e "  ${G}6${NC}) Proficient — Idiomatic usage (3500 words)"
  echo -e "  ${G}7${NC}) Fluent — Literary analysis (5000 words)"
  echo -e "  ${G}8${NC}) Mastery — Full Bible vocabulary"
  echo ""
  read -p "  Select level [1]: " level_choice
  LEVEL="${level_choice:-1}"
  echo ""
  echo -e "${G}Generating exercise for Level ${LEVEL}...${NC}"
  echo ""
  log_event "engine_learn" "level=$LEVEL"
  $PYTHON "$SCRIPT_DIR/bible_engine.py" --learn --level "$LEVEL"
  log_event "engine_learn_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_engine_review() {
  banner
  echo -e "${Y}📝 Review Due Items (Spaced Repetition)${NC}"
  echo ""
  echo -e "  ${G}1${NC}) Show due items"
  echo -e "  ${G}2${NC}) Review a specific word"
  echo ""
  read -p "  Select [1]: " review_choice
  case "$review_choice" in
    2)
      read -p "  Word to review: " review_word
      if [ -n "$review_word" ]; then
        log_event "engine_review_word" "$review_word"
        $PYTHON "$SCRIPT_DIR/bible_engine.py" --review --word "$review_word"
      else
        echo -e "${R}No word entered${NC}"
      fi
      ;;
    *)
      log_event "engine_review_due" ""
      $PYTHON "$SCRIPT_DIR/bible_engine.py" --review --due
      ;;
  esac
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_engine_search() {
  banner
  echo -e "${Y}🔍 Corpus Search (Patterns + Words)${NC}"
  echo ""
  echo -e "  ${G}1${NC}) Full-text search (ZO or EN)"
  echo -e "  ${G}2${NC}) Pattern search (SOV, negation, etc.)"
  echo -e "  ${G}3${NC}) Word search"
  echo ""
  read -p "  Select [1]: " search_choice
  case "$search_choice" in
    2)
      echo -e "  ${C}Available patterns: SOV, negation, question_hiam, conjunction_leh, ergative_in, declarative_hi, future_ding${NC}"
      read -p "  Pattern: " search_pattern
      if [ -n "$search_pattern" ]; then
        log_event "engine_search_pattern" "$search_pattern"
        $PYTHON "$SCRIPT_DIR/bible_engine.py" --search-pattern "$search_pattern"
      fi
      ;;
    3)
      read -p "  Word: " search_word
      if [ -n "$search_word" ]; then
        log_event "engine_search_word" "$search_word"
        $PYTHON "$SCRIPT_DIR/bible_engine.py" --search "$search_word"
      fi
      ;;
    *)
      read -p "  Search query: " search_query
      if [ -n "$search_query" ]; then
        log_event "engine_search_text" "$search_query"
        $PYTHON "$SCRIPT_DIR/bible_engine.py" --search "$search_query"
      fi
      ;;
  esac
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_engine_export() {
  banner
  echo -e "${Y}📦 Export Training Datasets${NC}"
  echo ""
  echo -e "  ${G}1${NC}) Translation pairs (ZO↔EN)"
  echo -e "  ${G}2${NC}) Grammar exercises"
  echo -e "  ${G}3${NC}) Vocabulary list"
  echo -e "  ${G}4${NC}) QA pairs"
  echo ""
  read -p "  Select type [1]: " export_choice
  case "$export_choice" in
    2)  EXPORT_TYPE="grammar" ;;
    3)  EXPORT_TYPE="vocab" ;;
    4)  EXPORT_TYPE="qa" ;;
    *)  EXPORT_TYPE="translation" ;;
  esac
  echo ""
  read -p "  Book (or leave empty for all): " export_book
  BOOK_FLAG=""
  if [ -n "$export_book" ]; then
    BOOK_FLAG="--book ${export_book^^}"
  fi
  echo ""
  echo -e "${G}Exporting ${EXPORT_TYPE}...${NC}"
  log_event "engine_export" "type=$EXPORT_TYPE book=${export_book:-all}"
  $PYTHON "$SCRIPT_DIR/bible_engine.py" --export --type "$EXPORT_TYPE" $BOOK_FLAG
  log_event "engine_export_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Knowledge Vectors ──────────────────────────────────────

cmd_knowledge_vectors() {
  banner
  echo -e "${Y}🧠 Knowledge Vectors (RAG Index)${NC}"
  echo ""
  local knowledge_file="$DATA/knowledge/knowledge_vectors.jsonl"
  if [ ! -f "$knowledge_file" ]; then
    echo -e "  ${R}❌ Knowledge vectors file not found${NC}"
    echo -e "  Expected: $knowledge_file"
    echo ""
    read -p "Press Enter to return to menu..."
    return
  fi

  echo -e "  ${G}✅ Knowledge vectors file present${NC}"
  echo -e "  Size: $(wc -c < "$knowledge_file") bytes"
  echo -e "  Rows: $(wc -l < "$knowledge_file")"
  echo ""
  echo -e "  ${G}1${NC}) 🔎 Run a retrieval query"
  echo -e "  ${G}0${NC}) Back to main menu"
  echo ""
  read -p "  Select [1]: " kv_choice
  case "$kv_choice" in
    0|q|Q) return ;;
    *) ;;
  esac

  read -p "  Query: " kv_query
  if [ -z "$kv_query" ]; then
    echo -e "  ${R}No query entered.${NC}"
    echo ""
    read -p "Press Enter to return to menu..."
    return
  fi
  read -p "  Top-k results [3]: " kv_topk
  kv_topk="${kv_topk:-3}"
  echo ""
  echo -e "  ${C}Loading index + embedding query...${NC}"
  echo ""
  log_event "kv_query" "query=$kv_query topk=$kv_topk"
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
import sys
from zolai.knowledge.retrieve import load_index, retrieve
idx = load_index()
if idx.vectors is None or len(idx.vectors) == 0:
    print('  No vectors in index. Run build_knowledge_index first.')
    sys.exit(0)
q = sys.argv[1]
hits = retrieve(q, index=idx, top_k=int(sys.argv[2]))
if not hits:
    print('  (no results above similarity threshold 0.85)')
else:
    for i, h in enumerate(hits, 1):
        src = h.get('metadata', {}).get('source', '?')
        print(f'  [{i}] (score {h.get(\"score\", \"?\")}) src={src}')
        print('      ' + h.get('text', '').replace(chr(10), ' ')[:300])
        print()
" "$kv_query" "$kv_topk"
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Paragraph Engine commands ──────────────────────────────

cmd_para_analyze() {
  echo -e "${C}═══ Paragraph Analysis ═══${NC}"
  echo ""
  echo -e "  Enter a Zo paragraph (or provide a file):"
  echo -e "  ${Y}Tip: Paste multiple lines, then press Ctrl+D when done${NC}"
  echo ""
  local tmpfile
  tmpfile=$(mktemp /tmp/para_input_XXXXXX.txt)
  cat > "$tmpfile"
  local text
  text=$(tr '\n' ' ' < "$tmpfile")
  rm -f "$tmpfile"

  if [ -z "$text" ]; then
    echo -e "${R}No text provided.${NC}"
    return
  fi

  $PYTHON "$SCRIPT_DIR/paragraph_engine.py" --analyze --text "$text"
}

cmd_para_paraphrase() {
  echo -e "${C}═══ Paraphrase & Style Transfer ═══${NC}"
  echo ""
  echo -e "  Enter a Zo paragraph:"
  echo ""
  local tmpfile
  tmpfile=$(mktemp /tmp/para_input_XXXXXX.txt)
  cat > "$tmpfile"
  local text
  text=$(tr '\n' ' ' < "$tmpfile")
  rm -f "$tmpfile"

  if [ -z "$text" ]; then
    echo -e "${R}No text provided.${NC}"
    return
  fi

  echo ""
  echo -e "  Paraphrase level:"
  echo -e "    ${G}1${NC}) Minimal (change few words)"
  echo -e "    ${G}2${NC}) Moderate (change vocab + structure)"
  echo -e "    ${G}3${NC}) Strong (substantial rewrite)"
  echo -e "    ${G}4${NC}) Structural (reorganize)"
  echo -e "    ${G}5${NC}) Style (transform style)"
  echo ""
  read -p "  Select level [2]: " level_choice
  level_choice="${level_choice:-2}"

  echo ""
  echo -e "  Output style:"
  echo -e "    ${G}1${NC}) Simple Zo"
  echo -e "    ${G}2${NC}) Natural Zo"
  echo -e "    ${G}3${NC}) Formal Zo"
  echo -e "    ${G}4${NC}) Professional Zo"
  echo -e "    ${G}5${NC}) Literary Zo"
  echo -e "    ${G}6${NC}) Conversational Zo"
  echo -e "    ${G}7${NC}) All styles"
  echo ""
  read -p "  Select style [2]: " style_choice
  style_choice="${style_choice:-2}"

  local style_flag=""
  case "$style_choice" in
    1) style_flag="--style SIMPLE" ;;
    2) style_flag="--style SIMPLE" ;;
    3) style_flag="--style FORMAL" ;;
    4) style_flag="--style FORMAL" ;;
    5) style_flag="--style LITERARY" ;;
    6) style_flag="--style CONVERSATIONAL" ;;
    7) style_flag="--multi-style" ;;
    *) style_flag="--style SIMPLE" ;;
  esac

  $PYTHON "$SCRIPT_DIR/paragraph_engine.py" --paraphrase --level "$level_choice" $style_flag --text "$text"
}

cmd_para_knowledge() {
  echo -e "${C}═══ Paragraph Knowledge Base ═══${NC}"
  $PYTHON "$SCRIPT_DIR/paragraph_engine.py" --stats
}

# ── AI Learning Tools commands ─────────────────────────────

cmd_sentence_validator() {
  banner
  echo -e "${C}═══ Sentence Validator ═══${NC}"
  echo ""
  echo -e "  Check if a Zolai sentence is real/attested (Bible + corpus)."
  echo ""
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
from zolai.learning.sentence_validator import get_sentence_validator
v = get_sentence_validator()
stats = v.get_stats()
print(f'  Bible sentences: {stats[\"bible_sentences\"]}')
print(f'  Corpus sentences: {stats[\"corpus_sentences\"]}')
print()
sent = input('  Enter Zolai sentence to validate: ')
if not sent.strip():
    print('  No input.')
else:
    result = v.validate(sent)
    print()
    print(f'  Confidence: {result[\"confidence\"]}')
    print(f'  In Bible: {result[\"in_bible\"]}')
    print(f'  In Corpus: {result[\"in_corpus\"]}')
    print(f'  Word score: {result[\"word_score\"]:.2%}')
    if result['bible_words_found']:
        print(f'  Bible words: {\" \".join(result[\"bible_words_found\"])}')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_dict_cleaner() {
  banner
  echo -e "${C}═══ Dictionary Cleaner ═══${NC}"
  echo ""
  echo -e "  Fix data quality issues in Zolai dictionaries."
  echo ""
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
from zolai.cleaner.dict_cleaner import get_dict_cleaner
cleaner = get_dict_cleaner()
result = cleaner.clean_zo_en_dict()
print(f'  Cleaned: {result[\"stats\"][\"cleaned\"]}')
print(f'  Fixed: {result[\"stats\"][\"fixed\"]}')
print(f'  Removed: {result[\"stats\"][\"removed\"]}')
print(f'  Output: {result[\"output\"]}')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_training_builder() {
  banner
  echo -e "${C}═══ Training Dataset Builder ═══${NC}"
  echo ""
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
from zolai.trainer.training_dataset_builder import get_training_builder
builder = get_training_builder()
stats = builder.get_stats()
print(f'  Bible pairs: {stats[\"bible_pairs\"]}')
print(f'  Parallel pairs: {stats[\"parallel_pairs\"]}')
print(f'  Total: {stats[\"total_pairs\"]}')
print()
print('  Building translation dataset...')
dataset = builder.build_translation_dataset(max_pairs=10000)
output = builder.export_to_jsonl(dataset, '$DATA/training/translation_pairs_v2.jsonl')
print(f'  Exported {len(dataset)} pairs to {output}')
print()
print('  Building grammar exercises...')
grammar = builder.build_grammar_dataset(max_pairs=2000)
goutput = builder.export_to_jsonl(grammar, '$DATA/training/grammar_exercises_v2.jsonl')
print(f'  Exported {len(grammar)} exercises to {goutput}')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_pattern_learner() {
  banner
  echo -e "${C}═══ Pattern Learner ═══${NC}"
  echo ""
  echo -e "  Extract real Zolai sentence patterns from Bible."
  echo ""
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
from zolai.learning.bible_pattern_learner import get_bible_learner
learner = get_bible_learner()
stats = learner.get_pattern_stats()
print(f'  Total verses: {stats[\"total_verses\"]}')
print(f'  Pattern counts: {stats[\"pattern_counts\"]}')
print()
print('  Top 10 words:')
for word, count in stats['top_words'][:10]:
    print(f'    {word}: {count}')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_full_analysis() {
  banner
  echo -e "${C}═══ Full Analysis — All Systems ═══${NC}"
  echo ""
  PYTHONPATH="$WORKSPACE/zolai-core${PYTHONPATH:+:$PYTHONPATH}" $PYTHON -c "
from zolai.learning.bible_pattern_learner import get_bible_learner
from zolai.learning.sentence_validator import get_sentence_validator
from zolai.trainer.training_dataset_builder import get_training_builder

learner = get_bible_learner()
validator = get_sentence_validator()
builder = get_training_builder()

print(f'  Bible verses: {len(learner.verses)}')
print(f'  Bible sentences: {validator.get_stats()[\"bible_sentences\"]}')
print(f'  Dictionary pairs: {builder.get_stats()[\"total_pairs\"]}')
print()
print('  All systems ready!')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Online Data Integration commands ───────────────────────

cmd_integrate_dalsuum() {
  banner
  echo -e "${G}Integrating Dalsuum dictionary (7,861 words)...${NC}"
  $PYTHON "$SCRIPT_DIR/integrate_dalsuum.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_extract_corpus_vocab() {
  banner
  echo -e "${G}Extracting vocabulary from paumkim corpus (208MB)...${NC}"
  $PYTHON "$SCRIPT_DIR/extract_corpus_vocab.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_extract_proverbs() {
  banner
  echo -e "${G}Extracting proverbs from Bible...${NC}"
  $PYTHON "$SCRIPT_DIR/extract_proverbs.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_integrate_conversational() {
  banner
  echo -e "${G}Integrating conversational data...${NC}"
  $PYTHON "$SCRIPT_DIR/integrate_conversational.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_build_cross_language() {
  banner
  echo -e "${G}Building cross-language comparison (Tedim/Hakha/Falam/Paite)...${NC}"
  $PYTHON "$SCRIPT_DIR/build_cross_language.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_build_comprehensive_vocab() {
  banner
  echo -e "${G}Building comprehensive vocabulary master list...${NC}"
  $PYTHON "$SCRIPT_DIR/build_comprehensive_vocab.py" "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Training Tools commands ────────────────────────────────

cmd_create_seed() {
  banner
  echo -e "${C}═══ Create Seed Data ═══${NC}"
  echo ""
  echo -e "  Extracts 500 high-quality ZO↔EN pairs from Bible + dictionary."
  echo -e "  Output: $DATA/training/seed_data_500.jsonl"
  echo ""
  $PYTHON "$SCRIPT_DIR/create_seed_data.py"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_generate_synthetic() {
  banner
  echo -e "${C}═══ Generate Synthetic Training Data ═══${NC}"
  echo ""
  read -p "  Count [1000]: " count
  count="${count:-1000}"
  echo -e "  Generating $count pairs..."
  echo ""
  $PYTHON "$SCRIPT_DIR/generate_synthetic_data.py" \
    --seed "$DATA/training/seed_data_500_fixed.jsonl" \
    --output "$DATA/training/synthetic_${count}.jsonl" \
    --count "$count" \
    --task translation 2>&1 || echo -e "${R}Generation failed — check seed data${NC}"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_kaggle_guide() {
  banner
  echo -e "${C}═══ Kaggle Setup Guide ═══${NC}"
  echo ""
  echo -e "  ${Y}Full guide:${NC} context/KAGGLE_SETUP.md"
  echo ""
  echo -e "  ${Y}Quick Steps:${NC}"
  echo -e "    1. Create account at kaggle.com"
  echo -e "    2. New Notebook → Settings → GPU T4 x2"
  echo -e "    3. Add Data → Search 'zolai'"
  echo -e "    4. Copy cells from KAGGLE_SETUP.md"
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Path check ─────────────────────────────────────────────

cmd_fix_paths() {
  banner
  echo -e "${Y}Checking/fixing script paths...${NC}"
  echo ""
  if grep -q 'WORKSPACE = SCRIPT_DIR.parent.parent.parent' "$SCRIPT_DIR/study_bible_books.py" 2>/dev/null; then
    echo -e "  ${G}✅ study_bible_books.py — paths OK${NC}"
  else
    echo -e "  ${R}❌ study_bible_books.py — needs path fix${NC}"
  fi
  if grep -q 'WORKSPACE = SCRIPT_DIR.parent.parent.parent' "$SCRIPT_DIR/bible_engine.py" 2>/dev/null; then
    echo -e "  ${G}✅ bible_engine.py — paths OK${NC}"
  else
    echo -e "  ${R}❌ bible_engine.py — needs path fix${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_view_log() {
  banner
  echo -e "${Y}Recent log events (last 30):${NC}"
  echo ""
  if [ -f "$LOG_FILE" ]; then
    tail -30 "$LOG_FILE" | $PYTHON -c "
import sys, json
for l in sys.stdin:
    try:
        d = json.loads(l)
        ev = d.get('event','?')
        ts = d.get('ts','?')[-8:]
        detail = d.get('detail','')[:40]
        if ev == 'gloss':
            print(f'  {ts} 📝 {d.get(\"word\",\"?\")} → {d.get(\"meaning\",\"?\")}  [{d.get(\"source\",\"?\")}]')
        elif ev == 'ai_result':
            print(f'  {ts} ✅ AI: {d.get(\"word\",\"?\")} → {d.get(\"chosen\",\"?\")}')
        elif ev == 'book_done':
            print(f'  {ts} 📊 {d.get(\"book\",\"?\")} dict={d.get(\"dict_rate\",\"?\")} ai={d.get(\"ai_rate\",\"?\")}')
        else:
            print(f'  {ts} {ev}: {detail}')
    except: pass" 2>/dev/null
  else
    echo -e "  ${C}No log file yet — run a study first${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

# ═══════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════
while true; do
  banner
  echo -e "${G}Main Menu:${NC}"
  echo ""
  echo -e "  ${M}── Bible Study ────────────────────────${NC}"
  echo -e "  ${G}1${NC}) 📖 Study Bible (full/selected books + AI)"
  echo -e "  ${G}2${NC}) 🔄 Resume interrupted study"
  echo -e "  ${G}3${NC}) 🧪 Test with Genesis only"
  echo -e "  ${G}4${NC}) 📊 Show statistics"
  echo -e "  ${G}5${NC}) 🔍 Check dictionary (ZO→EN + EN→ZO)"
  echo ""
  echo -e "  ${M}── Bible Engine ────────────────────────${NC}"
  echo -e "  ${G}C${NC}) 📖 Bible Engine — Full verse analysis"
  echo -e "  ${G}D${NC}) 🎓 Progressive learning (8 levels)"
  echo -e "  ${G}E${NC}) 📝 Review due items (spaced repetition)"
  echo -e "  ${G}F${NC}) 🔍 Corpus search (patterns + words)"
  echo -e "  ${G}G${NC}) 📦 Export training datasets"
  echo ""
  echo -e "  ${M}── Paragraph Engine ───────────────────${NC}"
  echo -e "  ${G}H${NC}) 🧠 Knowledge Vectors (RAG index status)"
  echo -e "  ${G}I${NC}) 📝 Paragraph Analysis"
  echo -e "  ${G}J${NC}) ✍️  Paraphrase & Style Transfer"
  echo -e "  ${G}K${NC}) 📚 Paragraph Knowledge Base"
  echo ""
  echo -e "  ${M}── AI Learning Tools ──────────────────${NC}"
  echo -e "  ${G}L${NC}) ✅ Sentence Validator — Check if real"
  echo -e "  ${G}M${NC}) 🧹 Dictionary Cleaner — Fix quality"
  echo -e "  ${G}N${NC}) 🌐 Training Dataset Builder — Export pairs"
  echo -e "  ${G}O${NC}) 🔬 Pattern Learner — Extract patterns"
  echo -e "  ${G}P${NC}) 📊 Full Analysis — All tools combined"
  echo ""
  echo -e "  ${M}── Online Data Tools ──────────────────${NC}"
  echo -e "  ${G}Q${NC}) 🔗 Integrate Dalsuum dictionary"
  echo -e "  ${G}R${NC}) 📊 Extract corpus vocabulary"
  echo -e "  ${G}S${NC}) 📜 Extract proverbs & wise sayings"
  echo -e "  ${G}T${NC}) 💬 Integrate conversational data"
  echo -e "  ${G}U${NC}) 🌐 Build cross-language comparison"
  echo -e "  ${G}V${NC}) 📦 Build master vocabulary"
  echo ""
  echo -e "  ${M}── Training ──────────────────────────${NC}"
  echo -e "  ${G}W${NC}) 🌱 Create seed data (500 pairs)"
  echo -e "  ${G}X${NC}) 🤖 Generate synthetic training data"
  echo -e "  ${G}Y${NC}) 📊 Kaggle setup guide"
  echo ""
  echo -e "  ${G}6${NC}) 🛠  Check/fix paths"
  echo -e "  ${G}7${NC}) 📜 View recent AI log"
  echo ""
  echo -e "  ${G}0${NC}) 🚪 Exit"
  echo ""
  read -p "  Select: " main_choice
  case "$main_choice" in
    1) cmd_study ;;
    2) cmd_resume ;;
    3) cmd_test_one ;;
    4) cmd_stats ;;
    5) cmd_check_dict ;;
    6) cmd_fix_paths ;;
    7) cmd_view_log ;;
    C|c) cmd_engine_study ;;
    D|d) cmd_engine_learn ;;
    E|e) cmd_engine_review ;;
    F|f) cmd_engine_search ;;
    G|g) cmd_engine_export ;;
    H|h) cmd_knowledge_vectors ;;
    I|i) cmd_para_analyze ;;
    J|j) cmd_para_paraphrase ;;
    K|k) cmd_para_knowledge ;;
    L|l) cmd_sentence_validator ;;
    M|m) cmd_dict_cleaner ;;
    N|n) cmd_training_builder ;;
    O|o) cmd_pattern_learner ;;
    P|p) cmd_full_analysis ;;
    Q|q) cmd_integrate_dalsuum ;;
    R|r) cmd_extract_corpus_vocab ;;
    S|s) cmd_extract_proverbs ;;
    T|t) cmd_integrate_conversational ;;
    U|u) cmd_build_cross_language ;;
    V|v) cmd_build_comprehensive_vocab ;;
    W|w) cmd_create_seed ;;
    X|x) cmd_generate_synthetic ;;
    Y|y) cmd_kaggle_guide ;;
    0) echo -e "${G}Goodbye!${NC}"; exit 0 ;;
    *) echo -e "${R}Invalid choice${NC}"; sleep 1 ;;
  esac
done
