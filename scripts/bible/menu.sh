#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZOLAI BIBLE STUDY — Master Menu v2.0
#  AI-assisted glossing with OpenCode free models
#  All 66 books • Full knowledge base • Version comparison
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
  echo -e "${C}║${NC}  ${B}66 Books • Full Knowledge Base • Version Comparison    ${C}║${NC}"
  echo -e "${C}║${NC}  ${B}OpenCode Free Models • Dictionary-First • AI Disambig  ${C}║${NC}"
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
  echo -e "  ${G}7${NC}) Historical (GEN-EST)"
  echo -e "  ${G}8${NC}) Poetic (JOB,PSA,PRO,ECC,SNG)"
  echo -e "  ${G}9${NC}) Prophetic (ISA-DAN, HOS-REV)"
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
    7)  BOOK_FLAG="--book JOB,PSA,PRO,ECC,SNG" ;;
    8)  BOOK_FLAG="--book ISA,JER,LAM,EZK,DAN,HOS,JOE,AMO,OBA,JON,MIC,NAM,HAB,ZEP,HAG,ZEC,MAL" ;;
    A|a)  read -p "  Book code: " bc; BOOK_FLAG="--book ${bc^^}" ;;
    B|b)  read -p "  Books (comma-sep): " bs; BOOK_FLAG="--book ${bs^^}" ;;
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
  local study_count=$(ls "$DATA/dictionary/bible_study/"*_study.jsonl 2>/dev/null | wc -l)
  echo -e "  ${C}Bible study files: ${study_count}/66${NC}"
  # AI cache
  if [ -f "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl" ]; then
    local cache_count=$(wc -l < "$DATA/dictionary/bible_study/ai_gloss_cache.jsonl")
    echo -e "  ${C}AI cache: ${cache_count} entries${NC}"
  fi
  # Knowledge base files
  echo -e "  ${Y}Knowledge Base:${NC}"
  for f in grammar_patterns vocabulary_db translation_pairs phrases verb_database particle_database book_summaries version_comparison; do
    local fp="$DATA/bible/${f}_v1.jsonl"
    if [ -f "$fp" ]; then
      local cnt=$(wc -l < "$fp")
      echo -e "    ${G}✅ ${f}_v1.jsonl: ${cnt} entries${NC}"
    else
      echo -e "    ${R}❌ ${f}_v1.jsonl: missing${NC}"
    fi
  done
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_check_dict() {
  banner
  echo -e "${Y}Checking Zolai→English dictionary:${NC}"
  echo ""
  $PYTHON -c "
import json
words = ['ci','tapa','kiangah','ahi','lei','leitung','topa','pasian','hong','kei','om','lo']
# Use ZO→EN master dictionary (correct direction!)
path = '$DATA/dictionary/processed/dict_zo_en_master_v1.jsonl'
found = {}
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('zolai','').strip().lower()
        if hw in words and hw not in found:
            eng = d.get('english','')
            if isinstance(eng, list):
                found[hw] = [e[:30] for e in eng[:3]]
            else:
                found[hw] = [str(eng)[:30]]
for w in words:
    if w in found:
        ts = ' | '.join(found[w])
        print(f'  {w:12s} → {ts}')
    else:
        print(f'  {w:12s} → NOT FOUND')
"
  echo ""
  echo -e "${Y}Checking English→Zolai dictionary:${NC}"
  echo ""
  $PYTHON -c "
import json
words = ['God','Lord','say','go','come','see','know','give','take','eat']
path = '$DATA/dictionary/processed/dict_canonical_v1.jsonl'
found = {}
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip().lower()
        if hw in words and hw not in found:
            trans = d.get('translations',[])[:3]
            found[hw] = [t[:30] for t in trans if isinstance(t,str)]
for w in words:
    if w in found:
        ts = ' | '.join(found[w])
        print(f'  {w:12s} → {ts}')
    else:
        print(f'  {w:12s} → NOT FOUND')
"
  log_event "dict_check" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_build_kb() {
  banner
  echo -e "${Y}Building Full Knowledge Base (all 66 books)...${NC}"
  echo ""
  log_event "kb_build_start" ""
  $PYTHON "$SCRIPT_DIR/build_full_knowledge_base.py" 2>&1 | tee "$LOG_DIR/kb_build.log"
  log_event "kb_build_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}

cmd_version_compare() {
  banner
  echo -e "${Y}Version Comparison: TDB77 vs Tedim2010${NC}"
  echo ""
  log_event "version_compare_start" ""
  $PYTHON "$SCRIPT_DIR/build_full_knowledge_base.py" --version-only 2>&1 | tee "$LOG_DIR/version_compare.log"
  log_event "version_compare_done" ""
  echo ""
  read -p "Press Enter to return to menu..."
}



cmd_check_non_zolai() {
  banner
  echo -e "${Y}Checking for non-Zolai words in dictionaries:${NC}"
  echo ""
  WORKSPACE="$WORKSPACE" $PYTHON "$SCRIPT_DIR/check_non_zolai.py"
  log_event "check_non_zolai" ""
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
  # Check dictionary files
  echo -e "  ${Y}Dictionary files:${NC}"
  for f in dict_zo_en_master_v1.jsonl dict_canonical_v1.jsonl; do
    if [ -f "$DATA/dictionary/processed/$f" ]; then
      local cnt=$(wc -l < "$DATA/dictionary/processed/$f")
      echo -e "    ${G}✅ $f: $cnt entries${NC}"
    else
      echo -e "    ${R}❌ $f: missing${NC}"
    fi
  done
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
  echo -e "  ${G}5${NC}) 🔍 Check dictionary (ZO→EN + EN→ZO)"
  echo -e "  ${G}6${NC}) 🛠  Check/fix paths & data status"
  echo -e "  ${G}7${NC}) 📜 View recent AI log"
  echo -e "  ${G}8${NC}) 🧹 Data cleanup status"
  echo -e "  ${G}9${NC}) 🔨 Build full knowledge base (66 books)"
  echo -e "  ${G}A${NC}) 📊 Version comparison (TDB77 vs Tedim2010)"
  echo -e "  ${G}B${NC}) 🔍 Check for non-Zolai words"
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
    9) cmd_build_kb ;;
    A|a) cmd_version_compare ;;
    B|b) cmd_check_non_zolai ;;
    0|q|Q) echo -e "${G}Goodbye!${NC}"; exit 0 ;;
    *) echo -e "${R}Invalid choice${NC}"; sleep 1 ;;
  esac
done
