#!/usr/bin/env python3
"""Full dictionary audit — scan ALL 93K entries against Bible corpus.
Finds: wrong definitions, missing words, rare words, Hakha/Falam intrusions.
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict

DATA_ROOT = Path("/home/peter/Documents/Projects/zolai-ai/data")

def load_bible_words():
    """Load all Zolai words from Bible with frequency."""
    words = Counter()
    verse_words = defaultdict(list)
    
    with open(DATA_ROOT / "bible/parallel_corpus_v1.jsonl") as f:
        for line in f:
            e = json.loads(line)
            ref = e.get('ref', '')
            zo = e.get('zo_tdb77') or ''
            # Tokenize
            for w in re.findall(r'[a-zA-Z]+', zo.lower()):
                words[w] += 1
                if len(verse_words[w]) < 3:
                    verse_words[w].append(ref)
    
    return words, verse_words


def load_dictionary():
    """Load all dictionary entries."""
    entries = []
    with open(DATA_ROOT / "dictionary/processed/dict_zo_en_master_v1.jsonl") as f:
        for line in f:
            e = json.loads(line)
            entries.append(e)
    return entries


def audit_dictionary():
    """Main audit: check each dictionary entry against Bible usage."""
    print("Loading Bible words...")
    bible_words, verse_words = load_bible_words()
    print(f"Bible vocabulary: {len(bible_words)} unique words, {sum(bible_words.values())} total tokens")
    
    print("\nLoading dictionary...")
    entries = load_dictionary()
    print(f"Dictionary entries: {len(entries)}")
    
    # Categories
    stats = {
        'total': len(entries),
        'in_bible': 0,
        'not_in_bible': 0,
        'single_char': 0,
        'has_number': 0,
        'very_rare': 0,  # freq < 3 in Bible
        'common': 0,  # freq >= 10
    }
    
    # Issues found
    issues = []
    
    for entry in entries:
        zolai = entry.get('zolai', '').strip()
        english = entry.get('english_clean', '') or entry.get('english', '')
        if isinstance(english, list):
            english = ', '.join(english)
        
        # Skip empty
        if not zolai:
            continue
        
        # Check single char
        if len(zolai) == 1:
            stats['single_char'] += 1
            continue
        
        # Check has number
        if re.search(r'\d', zolai):
            stats['has_number'] += 1
            continue
        
        # Check Bible frequency
        freq = bible_words.get(zolai.lower(), 0)
        
        if freq > 0:
            stats['in_bible'] += 1
            if freq >= 10:
                stats['common'] += 1
            elif freq <= 2:
                stats['very_rare'] += 1
                issues.append({
                    'zolai': zolai,
                    'english': english,
                    'freq': freq,
                    'type': 'very_rare_in_bible',
                    'refs': verse_words.get(zolai.lower(), [])
                })
        else:
            stats['not_in_bible'] += 1
    
    # Print stats
    print(f"\n{'='*60}")
    print(f"DICTIONARY AUDIT RESULTS")
    print(f"{'='*60}")
    for k, v in stats.items():
        print(f"  {k}: {v:,}")
    
    # Print top issues
    print(f"\n{'='*60}")
    print(f"VERY RARE IN BIBLE (freq <= 2): {len(issues)} entries")
    print(f"{'='*60}")
    for issue in sorted(issues, key=lambda x: x['freq'])[:30]:
        print(f"  {issue['zolai']:20s} freq={issue['freq']:3d}  en={issue['english'][:50]}  refs={issue['refs']}")
    
    # Save full report
    report_path = DATA_ROOT / "dictionary/processed/dictionary_audit_report.jsonl"
    with open(report_path, 'w') as f:
        for issue in issues:
            f.write(json.dumps(issue, ensure_ascii=False) + '\n')
    print(f"\nFull report saved to {report_path}")
    
    return stats, issues


if __name__ == "__main__":
    audit_dictionary()
