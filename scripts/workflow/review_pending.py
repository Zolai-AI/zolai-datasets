#!/usr/bin/env python3
"""
import asyncio
Interactive Human Review Workflow for Gemini-Generated Dictionary Updates.

Reviews entries with zvs_compliance_status='pending' from the database.
User can: 'a'pprove, 'r'eject, 's'kip, 'q'uit.
All actions update the database with version, remarks, and status.
After review, regenerates JSONL files from approved entries only.
"""

import sqlite3
import json
import sys
import os

# Add bible dir
SCRIPT_DIR = os.path.dirname(os.path.abspath('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai.py'))
BIBLE_DIR = os.path.join('/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts', 'bible')
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

import readline  # for better input handling


def get_pending_entries(limit=50):
    """Get entries pending human review."""
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    cur.execute(
        "SELECT id, headword, entry_version, update_remarks, update_description, zvs_compliance_status FROM entries WHERE zvs_compliance_status='pending' LIMIT ?",
        (limit,)
    )
    entries = cur.fetchall()
    conn.close()
    return entries


def update_entry_status(entry_id, new_status, remarks=None, description=None):
    """Update entry status in database."""
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    
    # Get current version and bump it
    cur.execute("SELECT entry_version FROM entries WHERE id=?", (entry_id,))
    row = cur.fetchone()
    current_version = row[0] if row else "v1.0"
    
    # Parse version and increment
    try:
        major = int(current_version.replace('v', ''))
        new_version = f"v{major + 1}.0"
    except:
        new_version = "v2.0"
    
    if remarks is None:
        remarks = ""
    if description is None:
        description = ""
    
    cur.execute(
        "UPDATE entries SET entry_version=?, update_remarks=?, update_description=?, zvs_compliance_status=? WHERE id=?",
        (new_version, remarks, description, new_status, entry_id)
    )
    conn.commit()
    conn.close()
    return new_version


def regenerate_jsonl_from_approved():
    """Regenerate JSONL files from entries with status='approved'."""
    conn = sqlite3.connect('data/dictionary/db/master_unified_dictionary.db')
    cur = conn.cursor()
    
    # Get all approved entries
    cur.execute("SELECT id, headword, pos, english, sources, raw_json, entry_version, update_remarks, update_description, zvs_compliance_status FROM entries WHERE zvs_compliance_status='approved'")
    approved = cur.fetchall()
    
    total = len(approved)
    print(f"Regenerating JSONL from {total} approved entries...")
    
    # Regenerate verified dict
    verified_entries = []
    for entry in approved:
        eid, headword, pos, english, sources, raw_json, version, remarks, description, zvs_status = entry
        
        headword_clean = headword.strip().strip('"').strip("'").strip()
        if not headword_clean:
            continue
        
        english_clean = english if english else []
        sources_clean = sources if sources else ''
        version_clean = version if version else 'v1.0'
        remarks_clean = remarks if remarks else ''
        description_clean = description if description else ''
        zvs_status_clean = zvs_status if zvs_status else 'pending'
        
        entry_dict = {
            'zolai': headword_clean,
            'english': english_clean,
            'source': sources_clean[:200] if isinstance(sources_clean, str) else str(sources_clean)[:200],
            'pos': pos.strip() if pos else '',
            'entry_version': version_clean,
            'update_remarks': remarks_clean,
            'update_description': description_clean,
            'zvs_compliance_status': zvs_status_clean
        }
        
        # Add raw_json if available
        if raw_json:
            try:
                rj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                if isinstance(rj, dict):
                    entry_dict['raw_json'] = rj
            except:
                pass
        
        verified_entries.append(json.dumps(entry_dict, ensure_ascii=False))
    
    # Write output
    verified_path = 'data/dictionary/processed/dict_zo_en_verified_v1.jsonl'
    with open(verified_path, 'w', encoding='utf-8') as f:
        for line in verified_entries:
            f.write(line + '\n')
    
    # Regenerate master dict (includes id and raw_json)
    master_entries = []
    for entry in approved:
        eid, headword, pos, english, sources, raw_json, version, remarks, description, zvs_status = entry
        headword_clean = headword.strip().strip('"').strip("'").strip()
        if not headword_clean:
            continue
        
        english_clean = english if english else []
        sources_clean = sources if sources else ''
        version_clean = version if version else 'v1.0'
        remarks_clean = remarks if remarks else ''
        description_clean = description if description else ''
        zvs_status_clean = zvs_status if zvs_status else 'pending'
        
        entry_dict = {
            'zolai': headword_clean,
            'english': english_clean,
            'source': sources_clean if isinstance(sources_clean, str) else str(sources_clean),
            'pos': pos.strip() if pos else '',
            'entry_version': version_clean,
            'update_remarks': remarks_clean,
            'update_description': description_clean,
            'zvs_compliance_status': zvs_status_clean,
            'id': eid,
        }
        
        if raw_json:
            try:
                rj = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                if isinstance(rj, dict):
                    entry_dict['raw_json'] = rj
            except:
                pass
        
        master_entries.append(json.dumps(entry_dict, ensure_ascii=False))
    
    master_path = 'data/dictionary/processed/dict_zo_en_master_v1.jsonl'
    with open(master_path, 'w', encoding='utf-8') as f:
        for line in master_entries:
            f.write(line + '\n')
    
    print(f"Regenerated: {verified_path} ({len(verified_entries)} entries)")
    print(f"Regenerated: {master_path} ({len(master_entries)} entries)")
    conn.close()


async def main():
    print("="*70)
    print("HUMAN REVIEW WORKFLOW: Gemini-Generated Dictionary Updates")
    print("="*70)
    print("\nDatabase tracks:")
    print("  - entry_version: v1.0, v2.0, v3.0, etc.")
    print("  - update_remarks: Why this entry was changed")
    print("  - update_description: Detailed change description")  
    print("  - zvs_compliance_status: pending/approved/rejected")
    print()
    
    # Load pending entries
    entries = get_pending_entries(limit=100)
    
    if not entries:
        print("No pending entries found in database.")
        print("Running regenerate_jsonl_from_approved()...")
        regenerate_jsonl_from_approved()
        return
    
    print(f"Found {len(entries)} pending entries for review.")
    print("\nReview each entry:")
    print("  'a' = Approve (update status to 'approved', bump version)")
    print("  'r' = Reject (update status to 'rejected', keep version)")
    print("  's' = Skip (leave as pending)")
    print("  'q' = Quit (save progress, exit)")
    print()
    
    idx = 0
    while idx < len(entries):
        entry_id, headword, version, current_remarks, current_description, current_status = entries[idx]
        
        headword_clean = headword.strip().strip('"').strip("'").strip()
        if not headword_clean:
            idx += 1
            continue
        
        print(f"\n{'='*60}")
        print(f"Entry {idx+1}/{len(entries)}")
        print(f"  ID: {entry_id}")
        print(f"  Headword: '{headword_clean}'")
        print(f"  Current version: {version}")
        print(f"  Current status: {current_status}")
        if current_remarks:
            print(f"  Remarks: {current_remarks[:80]}")
        if current_description:
            print(f"  Description: {current_description[:80]}")
        
        print("\n  Your action: a (approve), r (reject), s (skip), q (quit)")
        action = input("  > ").strip().lower()
        
        if action == 'q':
            print("Saving progress and quitting...")
            break
        
        elif action == 'a':
            # Approve - bump version, set status to approved
            new_version = update_entry_status(entry_id, 'approved', 
                                              remarks="Human-approved via review workflow",
                              description=f"Entry approved by human reviewer at entry {idx+1}")
            print(f"  ✅ APPROVED → version bumped to {new_version}")
            idx += 1
        
        elif action == 'r':
            # Reject - set status to rejected, bump version
            new_version = update_entry_status(entry_id, 'rejected',
                                              remarks="Human-rejected via review workflow",
                                              description=f"Entry rejected by human reviewer at entry {idx+1}")
            print(f"  ❌ REJECTED → version bumped to {new_version}")
            idx += 1
        
        elif action == 's':
            # Skip - leave as pending, just move to next
            print(f"  ⏭️  SKIPPED → remains pending")
            idx += 1
        
        else:
            print("  ❌ Invalid action. Please enter a, r, s, or q.")
            # Don't increment idx - show same entry again
    
    print(f"\n{'='*60}")
    print(f"Review complete. Processed {idx} of {len(entries)} entries.")
    
    # Ask if user wants to regenerate JSONL
    print("\nRegenerate JSONL files from approved entries? (y/n)")
    regen = input("> ").strip().lower()
    if regen == 'y':
        regenerate_jsonl_from_approved()
    else:
        print("JSONL files not regenerated.")


if __name__ == "__main__":
    asyncio.run(main())
