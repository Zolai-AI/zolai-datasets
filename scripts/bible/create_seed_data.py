#!/usr/bin/env python3
"""
Create seed data for synthetic Zolai-EN generation.
Extracts 500 high-quality translation pairs from existing data.
"""

import json
import random
from pathlib import Path

def load_jsonl(filepath):
    """Load JSONL file."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def extract_bible_pairs(parallel_corpus, n=200):
    """Extract high-quality Bible translation pairs."""
    pairs = []
    for verse in parallel_corpus[:n]:
        zo = verse.get('zo_tdb77', verse.get('zo_tedim2010', ''))
        en = verse.get('en_kJV', verse.get('en', ''))
        if zo and en and len(zo) > 10 and len(en) > 10:
            pairs.append({
                'zolai': zo.strip(),
                'english': en.strip(),
                'source': 'bible_tdb77',
                'type': 'translation',
                'quality': 'high'
            })
    return pairs

def extract_dictionary_pairs(zo_en_dict, n=150):
    """Extract dictionary translation pairs."""
    pairs = []
    for entry in zo_en_dict[:n]:
        zolai = entry.get('zolai', entry.get('word', ''))
        english = entry.get('english', entry.get('translation', ''))
        if zolai and english:
            # Handle list or string
            if isinstance(english, list):
                english = english[0] if english else ''
            if isinstance(zolai, list):
                zolai = zolai[0] if zolai else ''
            if zolai and english:
                pairs.append({
                    'zolai': zolai.strip(),
                    'english': english.strip(),
                    'source': 'dictionary',
                    'type': 'word',
                    'quality': 'high'
                })
    return pairs

def extract_conversational_pairs(conversational, n=100):
    """Extract conversational pairs."""
    pairs = []
    for entry in conversational[:n]:
        zo = entry.get('zolai', entry.get('zo', ''))
        en = entry.get('english', entry.get('en', ''))
        if zo and en:
            pairs.append({
                'zolai': zo.strip(),
                'english': en.strip(),
                'source': 'conversational',
                'type': 'sentence',
                'quality': 'medium'
            })
    return pairs

def extract_grammar_examples(grammar_patterns, n=50):
    """Extract grammar example sentences."""
    pairs = []
    for pattern in grammar_patterns[:n]:
        example_zo = pattern.get('example_zo', pattern.get('zolai', ''))
        example_en = pattern.get('example_en', pattern.get('english', ''))
        if example_zo and example_en:
            pairs.append({
                'zolai': example_zo.strip(),
                'english': example_en.strip(),
                'source': 'grammar',
                'type': 'example',
                'quality': 'high'
            })
    return pairs

def main():
    # Paths
    data_dir = Path('/home/peter/Documents/Projects/zolai-ai/data')
    output_dir = data_dir / 'training'
    output_dir.mkdir(exist_ok=True)
    
    print("Loading data sources...")
    
    # Load Bible parallel corpus
    bible_path = data_dir / 'bible' / 'parallel_corpus_v1.jsonl'
    if bible_path.exists():
        bible = load_jsonl(bible_path)
        print(f"  Bible: {len(bible)} verses")
    else:
        bible = []
        print("  Bible: NOT FOUND")
    
    # Load dictionary
    dict_path = data_dir / 'dictionary' / 'processed' / 'dict_zo_en_clean.jsonl'
    if dict_path.exists():
        dictionary = load_jsonl(dict_path)
        print(f"  Dictionary: {len(dictionary)} entries")
    else:
        dictionary = []
        print("  Dictionary: NOT FOUND")
    
    # Load conversational
    conv_path = data_dir / 'bible' / 'language_learning' / 'conversational.jsonl'
    if conv_path.exists():
        conversational = load_jsonl(conv_path)
        print(f"  Conversational: {len(conversational)} entries")
    else:
        conversational = []
        print("  Conversational: NOT FOUND")
    
    # Load grammar patterns
    grammar_path = data_dir / 'bible' / 'grammar_patterns_text.jsonl'
    if grammar_path.exists():
        grammar = load_jsonl(grammar_path)
        print(f"  Grammar: {len(grammar)} patterns")
    else:
        grammar = []
        print("  Grammar: NOT FOUND")
    
    print("\nExtracting seed pairs...")
    
    all_pairs = []
    
    # Extract from each source
    bible_pairs = extract_bible_pairs(bible, n=200)
    all_pairs.extend(bible_pairs)
    print(f"  Bible: {len(bible_pairs)} pairs")
    
    dict_pairs = extract_dictionary_pairs(dictionary, n=150)
    all_pairs.extend(dict_pairs)
    print(f"  Dictionary: {len(dict_pairs)} pairs")
    
    conv_pairs = extract_conversational_pairs(conversational, n=100)
    all_pairs.extend(conv_pairs)
    print(f"  Conversational: {len(conv_pairs)} pairs")
    
    grammar_pairs = extract_grammar_examples(grammar, n=50)
    all_pairs.extend(grammar_pairs)
    print(f"  Grammar: {len(grammar_pairs)} pairs")
    
    # Remove duplicates
    seen = set()
    unique_pairs = []
    for pair in all_pairs:
        key = (pair['zolai'], pair['english'])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)
    
    print(f"\nTotal unique pairs: {len(unique_pairs)}")
    
    # Shuffle and take 500
    random.seed(42)
    random.shuffle(unique_pairs)
    seed_data = unique_pairs[:500]
    
    # Save seed data
    output_file = output_dir / 'seed_data_500.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f:
        for pair in seed_data:
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')
    
    print(f"\nSaved {len(seed_data)} seed pairs to {output_file}")
    
    # Print sample
    print("\n=== Sample Pairs ===")
    for i, pair in enumerate(seed_data[:5]):
        print(f"{i+1}. Zolai: {pair['zolai'][:80]}...")
        print(f"   English: {pair['english'][:80]}...")
        print(f"   Source: {pair['source']}")
        print()

if __name__ == '__main__':
    main()
