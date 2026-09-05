#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZOLAI BIBLE STUDY — Master Menu
#  AI-assisted glossing with OpenCode free models
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
  echo -e "${C}║${NC}  ${M}ZOLAI BIBLE STUDY${NC} — AI-Assisted Context-Aware Glossing  ${C}║${NC}"
  echo -e "${C}║${NC}  ${B}OpenCode Free Models • Dictionary-First • AI Disambig  ${C}║${NC}"
  echo -e "${C}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

# ── Model selection ─────────────────────────────────────────
select_model() {
  echo -e "${Y}Available free models:${NC}"
  echo -e "  ${G}1${NC}) mimo-v2.5-free              ${C}(~15s, tested ✅)${NC}"
  echo -e "  ${G}2${NC}) nemotron-3.5-lightning-free  ${C}(~15s, tested ✅)${NC}"
  echo -e "  ${G}3${NC}) No AI — dictionary only"
  echo ""
  read -p "  Select model [1]: " choice
  case "$choice" in
    2)  MODEL="opencode/nemotron-3.5-lightning-free"; AI_FLAG="" ;;
    3)  MODEL=""; AI_FLAG="--no-ai" ;;
    *)  MODEL="opencode/mimo-v2.5-free"; AI_FLAG="" ;;
  esac
  echo -e "  → Using: ${G}${MODEL:-dict-only}${NC}"
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
  echo -e "  ${G}7${NC}) Single book (type code)"
  echo -e "  ${G}8${NC}) Custom list (comma-separated)"
  echo ""
  read -p "  Select [1]: " choice
  case "$choice" in
    2)  BOOKS="" ; BOOK_FLAG="" ;;
    3)  BOOKS="MAT,MRK,LUK,JHN,ACT,ROM,1CO,2CO,GAL,EPH,PHP,COL,1TH,2TH,1TI,2TI,TIT,PHM,HEB,JAS,1PE,2PE,1JN,2JN,3JN,JUD,REV"
        BOOK_FLAG="--book $BOOKS" ;;
    4)  BOOK_FLAG="--book GEN,EXO,LEV,NUM,DEU" ;;
    5)  BOOK_FLAG="--book PSA,PRO" ;;
    6)  BOOK_FLAG="--book MAT,MRK,LUK,JHN" ;;
    7)  read -p "  Book code: " bc; BOOK_FLAG="--book ${bc^^}" ;;
    8)  read -p "  Books (comma-sep): " bs; BOOK_FLAG="--book ${bs^^}" ;;
    *)  BOOK_FLAG="" ;;
  esac
}

# ── Commands ────────────────────────────────────────────────

cmd_study() {
  banner
  select_model
  select_books
  echo -e "${G}Starting study...${NC}"
  echo ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG $BOOK_FLAG "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_resume() {
  banner
  select_model
  echo -e "${G}Resuming (skipping completed books)...${NC}"
  echo ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG --resume "$@"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_test_one() {
  banner
  select_model
  echo -e "${G}Testing with Genesis (1 book)...${NC}"
  echo ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" $AI_FLAG --book GEN "$@"
  echo ""
  echo -e "${Y}Spot-check results:${NC}"
  head -5 "$DATA/dictionary/bible_study/01_GEN_study.jsonl" | $PYTHON -c "
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if d.get('type') == 'vocab' and d.get('word') in ('ci','tapa','kiangah','ahi','lei','leitung'):
        print(f\"  {d['word']:12s} → {d['gloss']:20s}  [{d.get('source','?')}]\")" 2>/dev/null || true
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_stats() {
  banner
  echo -e "${Y}Bible Study Statistics:${NC}"
  echo ""
  $PYTHON "$SCRIPT_DIR/study_bible_books.py" --stats
  echo ""
  if [ -f "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl" ]; then
    local count=$(wc -l < "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl")
    echo -e "  ${C}AI cache: ${count} entries${NC}"
  fi
  if [ -f "$DATA/dictionary/bible_study/bible_study_log.jsonl" ]; then
    local count=$(wc -l < "$DATA/dictionary/bible_study/bible_study_log.jsonl")
    echo -e "  ${C}Log events: ${count}${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_check_dict() {
  banner
  echo -e "${Y}Checking dictionary for key words:${NC}"
  echo ""
  $PYTHON -c "
import json
words = ['ci','tapa','kiangah','ahi','lei','leitung','topa','pasian','hong','kei','om','lo']
path = '$DATA/dictionary/processed/dict_unified_v1.jsonl'
found = {}
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip().lower()
        if hw in words and hw not in found:
            trans = [t.split(chr(10))[0][:30] for t in d.get('translations',[]) if isinstance(t,str)][:3]
            found[hw] = trans
for w in words:
    if w in found:
        ts = ' | '.join(found[w])
        print(f'  {w:12s} → {ts}')
    else:
        print(f'  {w:12s} → NOT FOUND')
"
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_fix_paths() {
  banner
  echo -e "${Y}Checking/fixing script paths...${NC}"
  echo ""
  # Check study_bible_books.py has correct WORKSPACE
  if grep -q 'Path(__file__).resolve().parent.parent.parent' "$SCRIPT_DIR/study_bible_books.py" 2>/dev/null; then
    echo -e "  ${G}✅ study_bible_books.py — paths OK${NC}"
  else
    echo -e "  ${R}❌ study_bible_books.py — needs path fix${NC}"
  fi
  # Check for FCL/HCL06 references in data
  local fcl_count=$(find "$DATA/corpus/bible/usx" -name "FCL" -o -name "HCL06" 2>/dev/null | wc -l)
  if [ "$fcl_count" -eq 0 ]; then
    echo -e "  ${G}✅ FCL/HCL06 removed${NC}"
  else
    echo -e "  ${R}❌ FCL/HCL06 still present${NC}"
  fi
  # Check bible study files exist
  local study_count=$(ls "$DATA/dictionary/bible_study/"*_study.jsonl 2>/dev/null | wc -l)
  echo -e "  ${C}Bible study files: ${study_count}/66${NC}"
  # Check ai cache
  if [ -f "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl" ]; then
    local cache_count=$(wc -l < "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl")
    echo -e "  ${C}AI cache: ${cache_count} entries${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_view_log() {
  banner
  echo -e "${Y}Recent log events (last 30):${NC}"
  echo ""
  if [ -f "$DATA/dictionary/bible_study/bible_study_log.jsonl" ]; then
    tail -30 "$DATA/dictionary/bible_study/bible_study_log.jsonl" | $PYTHON -c "
import sys, json
for l in sys.stdin:
    try:
        d = json.loads(l)
        ev = d.get('event','?')
        ts = d.get('ts','?')[-8:]
        if ev == 'gloss':
            print(f'  {ts} 📝 {d.get(\"word\",\"?\")} → {d.get(\"meaning\",\"?\")}  [{d.get(\"source\",\"?\")}]')
        elif ev == 'ai_result':
            print(f'  {ts} ✅ AI: {d.get(\"word\",\"?\")} → {d.get(\"chosen\",\"?\")}')
        elif ev == 'book_done':
            print(f'  {ts} 📊 {d.get(\"book\",\"?\")} dict={d.get(\"dict_rate\",\"?\")} ai={d.get(\"ai_rate\",\"?\")}')
        else:
            print(f'  {ts} {ev}')
    except: pass" 2>/dev/null
  else
    echo -e "  ${C}No log file yet — run a study first${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_clean_data() {
  banner
  echo -e "${Y}Data cleanup status:${NC}"
  echo ""
  echo -e "  ${C}FCL Bible (Falam):${NC}"
  if [ -d "$DATA/corpus/bible/usx/FCL" ]; then echo -e "    ${R}❌ Present${NC}"; else echo -e "    ${G}✅ Removed${NC}"; fi
  echo -e "  ${C}HCL06 Bible (Hakha):${NC}"
  if [ -d "$DATA/corpus/bible/usx/HCL06" ]; then echo -e "    ${R}❌ Present${NC}"; else echo -e "    ${G}✅ Removed${NC}"; fi
  echo -e "  ${C}Archive manifest:${NC}"
  if grep -q "bible_fcl_hcl06_removal" "$DATA/ARCHIVE_MANIFEST.json" 2>/dev/null; then
    echo -e "    ${G}✅ FCL/HCL06 removal recorded${NC}"
  else
    echo -e "    ${R}❌ Not recorded${NC}"
  fi
  echo -e "  ${C}Zokam as Zolai:${NC}"
  if grep 'skip_texts = set()' "$SCRIPT_DIR/../data_pipeline/gather_all_sources.py" >/dev/null 2>&1; then
    echo -e "    ${G}✅ Included${NC}"
  else
    echo -e "    ${C}⚠️  Check gather_all_sources.py${NC}"
  fi
  echo ""
  read -p "Press Enter to return to menu..."
}

# ── Main menu ───────────────────────────────────────────────
while true; do
  banner
  echo -e "${G}Main Menu:${NC}"
  echo ""
  echo -e "  ${G}1${NC}) 📖 Study Bible (full/selected books + AI)"
  echo -e "  ${G}2${NC}) 🔄 Resume interrupted study"
  echo -e "  ${G}3${NC}) 🧪 Test with Genesis only"
  echo -e "  ${G}4${NC}) 📊 Show statistics"
  echo -e "  ${G}5${NC}) 🔍 Check dictionary words"
  echo -e "  ${G}6${NC}) 🛠  Check/fix paths & data status"
  echo -e "  ${G}7${NC}) 📜 View recent AI log"
  echo -e "  ${G}8${NC}) 🧹 Data cleanup status"
  echo -e "  ${G}0${NC}) 🚪 Exit"
  echo ""
  read -p "  Select [1]: " main_choice
  case "$main_choice" in
    1) cmd_study ;;
    2) cmd_resume ;;
    3) cmd_test_one ;;
    4) cmd_stats ;;
    5) cmd_check_dict ;;
    6) cmd_fix_paths ;;
    7) cmd_view_log ;;
    8) cmd_clean_data ;;
    0|q|Q) echo -e "${G}Goodbye!${NC}"; exit 0 ;;
    *) echo -e "${R}Invalid choice${NC}"; sleep 1 ;;
  esac
done
