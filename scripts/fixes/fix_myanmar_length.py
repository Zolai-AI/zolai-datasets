#!/usr/bin/env python3
"""Truncate Myanmar Bible translations to 200 chars at sentence boundary."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "data" / "zolai.db"

def fix_myanmar(max_len=200):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # Check current max length
    cur.execute("SELECT MAX(LENGTH(myanmar)) FROM bible_verses WHERE myanmar IS NOT NULL")
    print(f"Before: max length = {cur.fetchone()[0]}")
    
    # Find verses needing fix
    cur.execute("SELECT ref, myanmar FROM bible_verses WHERE myanmar IS NOT NULL AND LENGTH(myanmar) > ?", (max_len,))
    rows = cur.fetchall()
    print(f"Found {len(rows)} verses > {max_len} chars")
    
    updated = 0
    for ref, myanmar in rows:
        if len(myanmar) > max_len:
            truncated = myanmar[:max_len]
            # Find last sentence ending (Myanmar ။ or .)
            last_end = max(truncated.rfind('။'), truncated.rfind('.'))
            if last_end > max_len // 2:
                truncated = truncated[:last_end + 1]
            
            cur.execute("UPDATE bible_verses SET myanmar = ? WHERE ref = ?", (truncated, ref))
            updated += 1
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT MAX(LENGTH(myanmar)) FROM bible_verses WHERE myanmar IS NOT NULL")
    print(f"After: max length = {cur.fetchone()[0]}")
    print(f"✅ Updated {updated} verses")
    conn.close()

if __name__ == "__main__":
    fix_myanmar()