#!/usr/bin/env python3
"""Fix too-long Myanmar Bible translations by truncating to reasonable length."""
import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parents[3] / "data" / "zolai.db")

def fix_myanmar_length(max_length=200):
    """Truncate Myanmar text to max_length characters, trying to end at sentence boundary."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get all verses with Myanmar text longer than max_length
    cur.execute("""
        SELECT ref, myanmar FROM bible_verses 
        WHERE myanmar IS NOT NULL AND LENGTH(myanmar) > ?
    """, (max_length,))
    
    rows = cur.fetchall()
    print(f"Found {len(rows)} verses with Myanmar text > {max_length} chars")
    
    updated = 0
    for ref, myanmar in rows:
        original = myanmar
        if len(myanmar) > max_length:
            # Try to truncate at sentence boundary (Myanmar uses ။ or .)
            truncated = myanmar[:max_length]
            # Find last sentence ending
            last_period = max(truncated.rfind('။'), truncated.rfind('.'))
            if last_period > max_length // 2:  # Only use if we keep at least half
                truncated = truncated[:last_period + 1]
            
            cur.execute(
                "UPDATE bible_verses SET myanmar = ? WHERE ref = ?",
                (truncated, ref)
            )
            updated += 1
            if updated <= 5:
                print(f"  {ref}: {len(original)} -> {len(truncated)} chars")
    
    conn.commit()
    conn.close()
    print(f"✅ Updated {updated} verses")

if __name__ == "__main__":
    import sys
    max_len = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    fix_myanmar_length(max_len)
