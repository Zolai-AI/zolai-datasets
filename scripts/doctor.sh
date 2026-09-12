#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZOLAI-AI DOCTOR — Auto-fix broken links, files & data
#  Run: zolai-ai --cli doctor
# ═══════════════════════════════════════════════════════════════
set -uo pipefail

# Resolve workspace
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA="$WORKSPACE/data"
PYTHON="python3"

# Colors
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' M='\033[0;35m' NC='\033[0m'

FIXED=0
WARNINGS=0
ERRORS=0

fix_ok()   { echo -e "  ${G}✅ FIXED:${NC} $1"; ((FIXED++)); }
fix_warn() { echo -e "  ${Y}⚠️  WARN:${NC} $1"; ((WARNINGS++)); }
fix_err()  { echo -e "  ${R}❌ ERROR:${NC} $1"; ((ERRORS++)); }
fix_skip() { echo -e "  ${C}⏭️  SKIP:${NC} $1"; }
fix_ok_msg() { echo -e "  ${G}✅ OK:${NC} $1"; }

echo -e "${C}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${C}║${NC}  ${M}ZOLAI-AI DOCTOR${NC} — Auto-fix broken links & data       ${C}║${NC}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# 1. CHECK WORKSPACE STRUCTURE
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 1. Workspace Structure ───────────────────────${NC}"
echo ""

for dir in \
  "$WORKSPACE/zolai-datasets" \
  "$WORKSPACE/zolai-core" \
  "$WORKSPACE/zolai-wiki" \
  "$WORKSPACE/data" \
  "$WORKSPACE/data/dictionary" \
  "$WORKSPACE/data/dictionary/db" \
  "$WORKSPACE/data/dictionary/processed" \
  "$WORKSPACE/data/bible" \
  "$WORKSPACE/zolai-datasets/scripts" \
  "$WORKSPACE/zolai-datasets/scripts/bible" \
  "$WORKSPACE/zolai-datasets/scripts/gemini" \
  "$WORKSPACE/zolai-datasets/scripts/fixes" \
  "$WORKSPACE/zolai-datasets/scripts/zvs" \
  "$WORKSPACE/zolai-datasets/scripts/database" \
  "$WORKSPACE/zolai-datasets/scripts/workflow"
do
  if [ -d "$dir" ]; then
    fix_ok_msg "$dir"
  else
    fix_warn "Missing directory: $dir"
    mkdir -p "$dir" 2>/dev/null && fix_ok "Created: $dir" || fix_err "Cannot create: $dir"
  fi
done
echo ""

# ═══════════════════════════════════════════════════════════════
# 2. CHECK KEY SCRIPTS
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 2. Key Scripts ───────────────────────────────${NC}"
echo ""

for script in \
  "$WORKSPACE/zolai_menu.sh" \
  "$WORKSPACE/zolai-datasets/scripts/bible/study_bible_books.py" \
  "$WORKSPACE/zolai-datasets/scripts/bible/bible_engine.py" \
  "$WORKSPACE/zolai-datasets/scripts/bible/check_non_zolai.py" \
  "$WORKSPACE/zolai-datasets/scripts/gemini/gemini_data_learning.py" \
  "$WORKSPACE/zolai-datasets/scripts/zvs/zvs_compliance_check.py" \
  "$WORKSPACE/zolai-datasets/scripts/database/regenerate_jsonl.py" \
  "$WORKSPACE/zolai-datasets/scripts/workflow/review_pending.py"
do
  if [ -f "$script" ]; then
    fix_ok_msg "$(basename "$script")"
  else
    fix_warn "Missing script: $script"
  fi
done
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. CHECK DATA FILES
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 3. Data Files ────────────────────────────────${NC}"
echo ""

check_data() {
  local file="$1"
  local name="$2"
  local min_size="${3:-1000}"
  
  if [ -f "$file" ]; then
    local size=$(wc -c < "$file" 2>/dev/null || echo "0")
    local lines=$(wc -l < "$file" 2>/dev/null || echo "0")
    if [ "$size" -gt "$min_size" ]; then
      fix_ok_msg "$name: ${lines} lines, $(( size / 1024 ))KB"
    else
      fix_warn "$name: File too small (${size} bytes)"
    fi
  else
    fix_warn "Missing: $name"
  fi
}

check_data "$DATA/dictionary/db/master_unified_dictionary.db" "Dictionary DB" 100000
check_data "$DATA/dictionary/processed/dict_zo_en_verified_v1.jsonl" "Verified dict (ZO→EN)" 1000000
check_data "$DATA/dictionary/processed/dict_zo_en_master_v1.jsonl" "Master dict (ZO→EN)" 1000000
check_data "$DATA/dictionary/processed/dict_canonical_clean.jsonl" "Canonical dict (EN→ZO)" 1000000
check_data "$DATA/bible/parallel_corpus_v1.jsonl" "Parallel corpus" 1000000
check_data "$DATA/bible/grammar_patterns_v2.jsonl" "Grammar patterns" 10000
check_data "$DATA/bible/vocabulary_db_v1.jsonl" "Vocabulary DB" 100000
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. CHECK SYMLINKS
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 4. Symlinks & Commands ───────────────────────${NC}"
echo ""

# Check zolai-ai command
if command -v zolai-ai &>/dev/null; then
  target=$(readlink -f "$(which zolai-ai)" 2>/dev/null || echo "unknown")
  if [ -f "$target" ]; then
    fix_ok_msg "zolai-ai command → $target"
  else
    fix_warn "zolai-ai symlink points to missing file: $target"
  fi
else
  fix_warn "zolai-ai command not found in PATH"
fi

# Check for broken symlinks in workspace
broken_links=$(find "$WORKSPACE" -maxdepth 3 -type l ! -exec test -e {} \; -print 2>/dev/null | head -10)
if [ -n "$broken_links" ]; then
  while IFS= read -r link; do
    fix_warn "Broken symlink: $link"
    rm -f "$link" 2>/dev/null && fix_ok "Removed broken symlink: $link"
  done <<< "$broken_links"
else
  fix_ok_msg "No broken symlinks found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 5. CHECK & FIX MENU PATHS
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 5. Menu Path Validation ──────────────────────${NC}"
echo ""

MENU="$WORKSPACE/zolai_menu.sh"
if [ -f "$MENU" ]; then
  # Check if BIBLE_DIR is set correctly
  if grep -q 'BIBLE_DIR=.*zolai-datasets/scripts/bible' "$MENU"; then
    fix_ok_msg "BIBLE_DIR path correct"
  else
    fix_warn "BIBLE_DIR path may be incorrect in menu"
  fi
  
  # Check if DATA is set correctly
  if grep -q 'DATA=.*data' "$MENU"; then
    fix_ok_msg "DATA path correct"
  else
    fix_warn "DATA path may be incorrect in menu"
  fi
  
  # Check for common broken references
  if grep -q 'dict_zo_en_clean.jsonl' "$MENU"; then
    fix_warn "Menu references old filename dict_zo_en_clean.jsonl"
    sed -i 's|dict_zo_en_clean.jsonl|dict_zo_en_verified_v1.jsonl|g' "$MENU"
    fix_ok "Fixed: dict_zo_en_clean.jsonl → dict_zo_en_verified_v1.jsonl"
  fi
else
  fix_err "Menu file not found: $MENU"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 6. CHECK DATABASE INTEGRITY
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 6. Database Integrity ────────────────────────${NC}"
echo ""

DB="$DATA/dictionary/db/master_unified_dictionary.db"
if [ -f "$DB" ] && command -v sqlite3 &>/dev/null; then
  # Check table exists
  table_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='entries';" 2>/dev/null || echo "0")
  if [ "$table_count" -gt 0 ]; then
    fix_ok_msg "Database has 'entries' table"
    
    # Check entry count
    entry_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "0")
    fix_ok_msg "Database has ${entry_count} entries"
    
    # Check for NULL headwords
    null_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM entries WHERE headword IS NULL OR TRIM(headword)='';" 2>/dev/null || echo "0")
    if [ "$null_count" -gt 0 ]; then
      fix_warn "Database has ${null_count} entries with NULL/empty headwords"
      sqlite3 "$DB" "DELETE FROM entries WHERE headword IS NULL OR TRIM(headword)='';" 2>/dev/null
      fix_ok "Removed ${null_count} entries with NULL headwords"
    else
      fix_ok_msg "No NULL headwords"
    fi
    
    # Check for duplicates
    dup_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM (SELECT headword FROM entries GROUP BY headword HAVING COUNT(*)>1);" 2>/dev/null || echo "0")
    if [ "$dup_count" -gt 0 ]; then
      fix_warn "Database has ${dup_count} duplicate headwords"
    else
      fix_ok_msg "No duplicate headwords"
    fi
    
    # Check zvs_compliance_status values
    sqlite3 "$DB" "SELECT zvs_compliance_status, COUNT(*) FROM entries GROUP BY zvs_compliance_status;" 2>/dev/null | while IFS='|' read -r status count; do
      echo -e "    ${C}  $status: $count${NC}"
    done
    
  else
    fix_warn "Database missing 'entries' table"
  fi
else
  fix_warn "Database not found or sqlite3 not available"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 7. CHECK GIT STATUS
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 7. Git Status ────────────────────────────────${NC}"
echo ""

for repo in zolai-datasets zolai-core zolai-wiki; do
  repo_dir="$WORKSPACE/$repo"
  if [ -d "$repo_dir/.git" ]; then
    cd "$repo_dir"
    dirty=$(git status --porcelain 2>/dev/null | wc -l)
    branch=$(git branch --show-current 2>/dev/null || echo "unknown")
    if [ "$dirty" -eq 0 ]; then
      fix_ok_msg "$repo: clean ($branch)"
    else
      fix_warn "$repo: ${dirty} uncommitted changes ($branch)"
    fi
    cd "$WORKSPACE"
  else
    fix_skip "$repo: not a git repo"
  fi
done
echo ""

# ═══════════════════════════════════════════════════════════════
# 8. CHECK PYTHON DEPENDENCIES
# ═══════════════════════════════════════════════════════════════
echo -e "${M}── 8. Python Dependencies ───────────────────────${NC}"
echo ""

for module in json sqlite3 sys os asyncio re; do
  if python3 -c "import $module" 2>/dev/null; then
    fix_ok_msg "python3: $module"
  else
    fix_warn "python3: $module not available"
  fi
done

# Check gemini_webapi
if python3 -c "import gemini_webapi" 2>/dev/null; then
  fix_ok_msg "gemini_webapi installed"
else
  fix_warn "gemini_webapi not installed (needed for Gemini tools)"
  echo -e "    ${C}  Install: pip install gemini-webapi${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
echo -e "${C}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${C}║${NC}  ${M}DOCTOR REPORT${NC}                                          ${C}║${NC}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${G}✅ Fixed:    ${FIXED}${NC}"
echo -e "  ${Y}⚠️  Warnings: ${WARNINGS}${NC}"
echo -e "  ${R}❌ Errors:   ${ERRORS}${NC}"
echo ""

if [ "$ERRORS" -eq 0 ]; then
  echo -e "  ${G}System is healthy!${NC}"
else
  echo -e "  ${Y}Please fix the errors above before using the system.${NC}"
fi
echo ""
