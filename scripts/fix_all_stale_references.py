#!/usr/bin/env python3
"""
Fix ALL stale table references across ALL scripts.
Auto-fixes: vocab→vocabulary, bible_context→bible_analysis, 
jsonl_import_log→import_log, zolai_songs→songs
"""
import os
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

# Table name mappings (old → new canonical)
TABLE_MAP = {
    'vocabulary': 'vocabulary',
    'bible_analysis': 'bible_analysis',
    'import_log': 'import_log',
    'songs': 'songs',
    'tone_sandhi': 'tone_sandhi',
    'proverbs': 'proverbs',
    'grammar_patterns': 'grammar_patterns',
    'vocabulary': 'vocabulary',
    'word_usage': 'word_usage',
    'bible_analysis': 'bible_analysis',
}

# SQL table name patterns (word boundary aware)
SQL_PATTERNS = [
    (r'\bFROM\s+vocab\b', 'FROM vocabulary'),
    (r'\bINTO\s+vocab\b', 'INTO vocabulary'),
    (r'\bUPDATE\s+vocab\b', 'UPDATE vocabulary'),
    (r'\bJOIN\s+vocab\b', 'JOIN vocabulary'),
    (r'\bTABLE\s+vocab\b', 'TABLE vocabulary'),
    (r'\bEXISTS\s*\(\s*SELECT.*FROM\s+vocab\b', None),  # complex, skip
    
    (r'\bFROM\s+bible_context\b', 'FROM bible_analysis'),
    (r'\bINTO\s+bible_context\b', 'INTO bible_analysis'),
    (r'\bUPDATE\s+bible_context\b', 'UPDATE bible_analysis'),
    (r'\bJOIN\s+bible_context\b', 'JOIN bible_analysis'),
    
    (r'\bFROM\s+jsonl_import_log\b', 'FROM import_log'),
    (r'\bINTO\s+jsonl_import_log\b', 'INTO import_log'),
    
    (r'\bFROM\s+zolai_songs\b', 'FROM songs'),
    (r'\bINTO\s+zolai_songs\b', 'INTO songs'),
    
    (r'\bFROM\s+zolai_tone_sandhi\b', 'FROM tone_sandhi'),
    (r'\bFROM\s+zolai_proverbs_idioms\b', 'FROM proverbs'),
    (r'\bFROM\s+zolai_grammar_patterns\b', 'FROM grammar_patterns'),
    (r'\bFROM\s+zolai_vocabulary\b', 'FROM vocabulary'),
    (r'\bFROM\s+zolai_word_usage\b', 'FROM word_usage'),
    (r'\bFROM\s+zolai_bible_analysis\b', 'FROM bible_analysis'),
]

# String literal patterns
STRING_PATTERNS = [
    (r'"vocabulary"', '"vocabulary"'),
    (r"'vocabulary'", "'vocabulary'"),
    (r'"bible_analysis"', '"bible_analysis"'),
    (r"'bible_analysis'", "'bible_analysis'"),
    (r'"import_log"', '"import_log"'),
    (r"'import_log'", "'import_log'"),
    (r'"songs"', '"songs"'),
    (r"'songs'", "'songs'"),
    (r'"tone_sandhi"', '"tone_sandhi"'),
    (r"'tone_sandhi'", "'tone_sandhi'"),
    (r'"proverbs"', '"proverbs"'),
    (r"'proverbs'", "'proverbs'"),
    (r'"grammar_patterns"', '"grammar_patterns"'),
    (r"'grammar_patterns'", "'grammar_patterns'"),
    (r'"vocabulary"', '"vocabulary"'),
    (r"'vocabulary'", "'vocabulary'"),
    (r'"word_usage"', '"word_usage"'),
    (r"'word_usage'", "'word_usage'"),
    (r'"bible_analysis"', '"bible_analysis"'),
    (r"'bible_analysis'", "'bible_analysis'"),
]

def fix_file(filepath: Path) -> int:
    """Fix stale references in a single file. Returns number of changes."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return 0
    
    original = content
    changes = 0
    
    # Apply SQL patterns (only in .py files)
    if filepath.suffix == '.py':
        for pattern, replacement in SQL_PATTERNS:
            if replacement:
                new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                if new_content != content:
                    changes += content.count(re.search(pattern, content, re.IGNORECASE).group()) if re.search(pattern, content, re.IGNORECASE) else 0
                    content = new_content
    
    # Apply string patterns
    for pattern, replacement in STRING_PATTERNS:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            changes += 1
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return changes
    return 0

def main():
    """Fix all scripts in the workspace."""
    total_changes = 0
    fixed_files = []
    
    for py_file in SCRIPTS_DIR.rglob("*.py"):
        changes = fix_file(py_file)
        if changes > 0:
            total_changes += changes
            fixed_files.append((str(py_file.relative_to(SCRIPTS_DIR)), changes))
    
    print(f"Fixed {len(fixed_files)} files with {total_changes} changes:")
    for f, c in sorted(fixed_files):
        print(f"  {f}: {c} changes")

if __name__ == "__main__":
    main()
