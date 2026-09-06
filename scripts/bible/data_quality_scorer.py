#!/usr/bin/env python3
"""
8-Feature Data Quality Scorer for Zolai Text

Based on research from:
- FineWeb2 (HuggingFace, 2025)
- DCAD-2000 (NeurIPS 2025)
- HPLT v2 (2025)

Features:
1. Word count (document length)
2. Character repetition ratio
3. Word repetition ratio
4. Special characters ratio
5. Stopwords ratio
6. Language identification score
7. Perplexity score
8. Flagged words ratio

Usage:
    python data_quality_scorer.py input.jsonl output.jsonl --threshold 0.5
    python data_quality_scorer.py input.jsonl output.jsonl --stats
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# Zolai stopwords (common function words)
ZOLOI_STOPWORDS = set([
    "a", "ah", "ahin", "hi", "hin", "i", "in", "na", "nae", "nei",
    "ning", "ni", "nu", "nung", "pe", "pen", "pi", "pin", "po",
    "sak", "si", "sin", "su", "te", "thei", "ti", "tu", "tua",
    "un", "unga", "ungah", "vei", "veh", "vnge", "zong", "zonga"
])

# Zolai special characters (Myanmar script, Zolai-specific)
SPECIAL_CHARS = set([
    '\u1000-\u109f',  # Myanmar script
    '\uaa00-\uaaff',  # Myanmar Extension-A
    '\u10a0-\u10ff',  # Georgian (for comparison)
    ' sdf', ' ', '\t', '\n', '\r'
])


def char_repetition_ratio(text: str) -> float:
    """Calculate character repetition ratio."""
    if len(text) < 4:
        return 0.0
    
    # Count repeated character sequences (3+ chars)
    repeats = len(re.findall(r'(.)\1{2,}', text))
    return min(repeats / max(len(text) / 10, 1), 1.0)


def word_repetition_ratio(text: str) -> float:
    """Calculate word repetition ratio."""
    words = text.split()
    if len(words) < 3:
        return 0.0
    
    # Count repeated words
    word_counts = Counter(words)
    repeated = sum(1 for w in word_counts if word_counts[w] > 1)
    return repeated / len(word_counts)


def special_chars_ratio(text: str) -> float:
    """Calculate special characters ratio."""
    if not text:
        return 0.0
    
    special = sum(1 for c in text if not c.isalnum() and not c.isspace())
    return special / len(text)


def stopwords_ratio(text: str) -> float:
    """Calculate stopwords ratio."""
    words = text.lower().split()
    if not words:
        return 0.0
    
    stop_count = sum(1 for w in words if w in ZOLOI_STOPWORDS)
    return stop_count / len(words)


def language_id_score(text: str) -> float:
    """
    Simple language identification score.
    Higher score = more likely Zolai.
    
    Features:
    - Myanmar script presence
    - Zolai-specific character patterns
    - Word patterns
    """
    if not text:
        return 0.0
    
    score = 0.0
    total = len(text)
    
    # Myanmar script characters
    myanmar_chars = sum(1 for c in text if '\u1000' <= c <= '\u109f')
    score += (myanmar_chars / total) * 0.4
    
    # Zolai-specific patterns (romanized)
    zolai_patterns = ['hiam', 'pasian', 'topa', 'vantung', 'tui', 'mi']
    pattern_matches = sum(1 for p in zolai_patterns if p in text.lower())
    score += (pattern_matches / len(zolai_patterns)) * 0.3
    
    # Word length distribution (Zolai tends to have medium-length words)
    words = text.split()
    if words:
        avg_len = sum(len(w) for w in words) / len(words)
        if 3 <= avg_len <= 8:
            score += 0.3
    
    return min(score, 1.0)


def perplexity_score(text: str) -> float:
    """
    Simplified perplexity score.
    Lower perplexity = more fluent text.
    
    Uses character-level entropy as proxy.
    """
    if len(text) < 10:
        return 1.0  # High perplexity for short text
    
    # Character frequency analysis
    char_freq = Counter(text.lower())
    total = len(text)
    
    # Calculate entropy
    entropy = 0.0
    for count in char_freq.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    
    # Normalize to 0-1 scale (lower is better)
    # Typical entropy for natural text is 4-6 bits per character
    return min(entropy / 6.0, 1.0)


def flagged_words_ratio(text: str) -> float:
    """
    Calculate ratio of flagged/inappropriate words.
    For Zolai, this includes:
    - Hakha/Falam intrusions
    - Deprecated ZVS forms
    - Common errors
    """
    # ZVS 2018 forbidden forms
    forbidden = ['pathian', 'ram', 'fapa', 'bawipa', 'siangpahrang', 'cu', 'cun']
    
    words = text.lower().split()
    if not words:
        return 0.0
    
    flagged = sum(1 for w in words if w in forbidden)
    return flagged / len(words)


def compute_quality_features(text: str) -> Dict[str, float]:
    """Compute all 8 quality features for a document."""
    return {
        'word_count': len(text.split()),
        'char_repetition': char_repetition_ratio(text),
        'word_repetition': word_repetition_ratio(text),
        'special_chars': special_chars_ratio(text),
        'stopwords': stopwords_ratio(text),
        'language_id': language_id_score(text),
        'perplexity': perplexity_score(text),
        'flagged_words': flagged_words_ratio(text)
    }


def compute_quality_score(features: Dict[str, float]) -> float:
    """
    Compute overall quality score from features.
    
    Weights based on research findings:
    - Language ID (0.25): Most important for low-resource
    - Perplexity (0.20): Fluency indicator
    - Word count (0.15): Document completeness
    - Stopwords (0.10): Natural language indicator
    - Repetition (0.10): Noise indicator
    - Special chars (0.10): Formatting quality
    - Flagged words (0.10): Error indicator
    """
    weights = {
        'word_count': 0.15,
        'char_repetition': 0.05,
        'word_repetition': 0.05,
        'special_chars': 0.10,
        'stopwords': 0.10,
        'language_id': 0.25,
        'perplexity': 0.20,
        'flagged_words': 0.10
    }
    
    # Normalize word_count to 0-1 scale (50-500 words is good)
    word_count_norm = min(max((features['word_count'] - 10) / 490, 0), 1)
    
    score = 0.0
    score += weights['word_count'] * word_count_norm
    score += weights['char_repetition'] * (1 - features['char_repetition'])
    score += weights['word_repetition'] * (1 - features['word_repetition'])
    score += weights['special_chars'] * (1 - features['special_chars'])
    score += weights['stopwords'] * features['stopwords']
    score += weights['language_id'] * features['language_id']
    score += weights['perplexity'] * (1 - features['perplexity'])
    score += weights['flagged_words'] * (1 - features['flagged_words'])
    
    return score


def process_file(input_path: str, output_path: str, threshold: float = 0.5, stats_only: bool = False):
    """Process a JSONL file and compute quality scores."""
    results = []
    total = 0
    passed = 0
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            text = entry.get('text', '') or entry.get('zo', '') or entry.get('zo_tdb77', '') or entry.get('zo_tedim2010', '') or entry.get('zolai', '') or entry.get('en', '') or entry.get('en_kJV', '') or entry.get('english_clean', '') or str(entry.get('english', ''))
            
            if not text:
                continue
            
            features = compute_quality_features(text)
            score = compute_quality_score(features)
            
            total += 1
            
            if stats_only:
                results.append({
                    'text': text[:100] + '...' if len(text) > 100 else text,
                    'score': round(score, 4),
                    'features': {k: round(v, 4) for k, v in features.items()}
                })
            elif score >= threshold:
                entry['quality_score'] = round(score, 4)
                entry['quality_features'] = {k: round(v, 4) for k, v in features.items()}
                results.append(entry)
                passed += 1
    
    if stats_only:
        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n=== Quality Score Statistics ===")
        print(f"Total documents: {total}")
        
        if results:
            scores = [r['score'] for r in results]
            print(f"Mean score: {sum(scores)/len(scores):.4f}")
            print(f"Min score: {min(scores):.4f}")
            print(f"Max score: {max(scores):.4f}")
            
            # Distribution
            bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
            for i in range(len(bins)-1):
                count = sum(1 for s in scores if bins[i] <= s < bins[i+1])
                print(f"  {bins[i]:.1f}-{bins[i+1]:.1f}: {count} ({count/len(scores)*100:.1f}%)")
        
        print(f"\n=== Top 10 Highest Quality ===")
        for i, r in enumerate(results[:10]):
            print(f"{i+1}. Score: {r['score']:.4f}")
            print(f"   Text: {r['text'][:80]}...")
    else:
        # Write filtered output
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in results:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        print(f"\n=== Quality Filtering Results ===")
        print(f"Input: {input_path}")
        print(f"Output: {output_path}")
        print(f"Total: {total}")
        print(f"Passed (threshold={threshold}): {passed}")
        print(f"Removed: {total - passed}")
        print(f"Pass rate: {passed/total*100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Zolai Data Quality Scorer')
    parser.add_argument('input', help='Input JSONL file')
    parser.add_argument('output', nargs='?', help='Output JSONL file (filtered)')
    parser.add_argument('--threshold', type=float, default=0.5, help='Quality threshold (0-1)')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    if not args.stats and not args.output:
        parser.error("Output file required unless --stats is used")
    
    process_file(args.input, args.output, args.threshold, args.stats)


if __name__ == '__main__':
    main()
