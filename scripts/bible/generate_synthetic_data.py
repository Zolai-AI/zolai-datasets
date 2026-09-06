#!/usr/bin/env python3
"""
Synthetic Data Generation Pipeline for Zolai

Based on research from:
- SynthLLM (LREC 2026)
- UPDESH (ACL 2026)
- NüshuRescue (COLING 2025)

This pipeline generates synthetic Zolai-English training data using LLMs.

Usage:
    python generate_synthetic_data.py --seed data/seed_pairs.jsonl --output data/synthetic_pairs.jsonl --count 1000
    python generate_synthetic_data.py --validate data/synthetic_pairs.jsonl
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Seed data (high-quality Zolai-English pairs)
SEED_DATA = [
    {
        "zolai": "Pasian in vantung leh lebung a piangsak hi.",
        "english": "God created the heavens and the earth.",
        "context": "Genesis 1:1 - Creation narrative"
    },
    {
        "zolai": "Mi khat in laibu a sim hi.",
        "english": "A person reads a book.",
        "context": "Basic SOV sentence"
    },
    {
        "zolai": "Namte in tui a nek hi.",
        "english": "The children drink water.",
        "context": "Basic sentence with ergative marker"
    },
    {
        "zolai": "Topa in a mite kiangah a gen hi: 'Na tate uh, na khang thei uh hiam?'",
        "english": "The Lord said to his people: 'Can you hear me?'",
        "context": "Quotative speech pattern"
    },
    {
        "zolai": "Zingsangah kha a sung a om hi.",
        "english": "In the morning, he was inside the house.",
        "context": "Temporal + locative construction"
    },
]


def load_seed_data(seed_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load seed data from file or use built-in seeds."""
    if seed_path and Path(seed_path).exists():
        with open(seed_path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f]
    return SEED_DATA


def generate_prompt(seed_pairs: List[Dict[str, Any]], task: str = "translation") -> str:
    """Generate prompt for LLM-based synthetic data generation."""
    
    seed_examples = "\n".join([
        f"Zolai: {p['zolai']}\nEnglish: {p['english']}"
        for p in seed_pairs[:5]
    ])
    
    if task == "translation":
        prompt = f"""You are an expert in Tedim Zolai (ZVS 2018 orthography) and English translation.

Here are high-quality translation examples:
{seed_examples}

Generate {len(seed_pairs)} new Zolai-English translation pairs following these rules:
1. Use ZVS 2018 orthography (pasian NOT pathian, topa NOT bawipa)
2. Follow SOV word order
3. Use ergative marker 'in' correctly
4. Include cultural context
5. Vary sentence complexity (simple, compound, complex)
6. Cover different topics: family, nature, daily life, community, spirituality

Output format (JSONL):
{{"zolai": "...", "english": "...", "context": "..."}}

Generate 10 pairs now:"""
    
    elif task == "grammar":
        prompt = f"""You are an expert in Zolai grammar and linguistics.

Here are grammar examples:
{seed_examples}

Generate {len(seed_pairs)} grammar exercise pairs:
1. Fill-in-the-blank exercises
2. Sentence transformation (active/passive)
3. Tense conversion exercises
4. Negation exercises
5. Question formation exercises

Output format (JSONL):
{{"exercise_type": "...", "zolai": "...", "english": "...", "answer": "..."}}

Generate 10 exercises now:"""
    
    elif task == "vocabulary":
        prompt = f"""You are an expert in Zolai vocabulary and semantics.

Here are vocabulary examples:
{seed_examples}

Generate {len(seed_pairs)} vocabulary learning items:
1. Word + definition + example sentence
2. Synonyms and antonyms
3. Collocations (word combinations)
4. Idiomatic expressions
5. Cultural vocabulary

Output format (JSONL):
{{"word": "...", "definition": "...", "example_zolai": "...", "example_english": "...", "category": "..."}}

Generate 10 items now:"""
    
    return prompt


def generate_synthetic_data(
    seed_data: List[Dict[str, Any]],
    count: int = 10,
    task: str = "translation",
    output_path: str = "synthetic_data.jsonl"
):
    """Generate synthetic data using LLM (placeholder for actual API call)."""
    
    # This is a placeholder - in production, you would call:
    # - OpenAI API (GPT-4o)
    # - HuggingFace API (Llama 3.1 405B)
    # - Local model (Ollama)
    
    print(f"\n=== Synthetic Data Generation ===")
    print(f"Task: {task}")
    print(f"Seed pairs: {len(seed_data)}")
    print(f"Target count: {count}")
    
    # For now, generate augmented versions of seed data
    synthetic = []
    
    for i in range(count):
        seed = random.choice(seed_data)
        
        # Simple augmentation (in production, use LLM)
        augmented = {
            "zolai": seed["zolai"],  # Would be LLM-generated
            "english": seed["english"],  # Would be LLM-generated
            "context": f"Synthetic from: {seed['context']}",
            "metadata": {
                "source": "synthetic",
                "seed": seed["context"],
                "generation_time": time.time()
            }
        }
        
        synthetic.append(augmented)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in synthetic:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print(f"✅ Generated {len(synthetic)} synthetic pairs")
    print(f"Output: {output_path}")
    
    return synthetic


def validate_synthetic_data(file_path: str):
    """Validate synthetic data quality."""
    print(f"\n=== Validating Synthetic Data ===")
    
    issues = []
    total = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            entry = json.loads(line)
            total += 1
            
            # Check required fields
            if 'zolai' not in entry or 'english' not in entry:
                issues.append(f"Line {i+1}: Missing required fields")
            
            # Check for ZVS violations
            zolai = entry.get('zolai', '').lower()
            forbidden = ['pathian', 'bawipa', 'siangpahrang']
            for word in forbidden:
                if word in zolai:
                    issues.append(f"Line {i+1}: ZVS violation - '{word}' should be modern form")
            
            # Check for empty content
            if not entry.get('zolai', '').strip():
                issues.append(f"Line {i+1}: Empty Zolai text")
            if not entry.get('english', '').strip():
                issues.append(f"Line {i+1}: Empty English text")
    
    print(f"Total entries: {total}")
    print(f"Issues found: {len(issues)}")
    
    if issues:
        print("\nIssues:")
        for issue in issues[:10]:  # Show first 10
            print(f"  - {issue}")
    else:
        print("✅ All entries valid")


def main():
    parser = argparse.ArgumentParser(description='Zolai Synthetic Data Generator')
    parser.add_argument('--seed', type=str, help='Seed data file (JSONL)')
    parser.add_argument('--output', type=str, default='synthetic_data.jsonl', help='Output file')
    parser.add_argument('--count', type=int, default=10, help='Number of synthetic pairs')
    parser.add_argument('--task', type=str, choices=['translation', 'grammar', 'vocabulary'],
                       default='translation', help='Generation task type')
    parser.add_argument('--validate', type=str, help='Validate existing synthetic data')
    
    args = parser.parse_args()
    
    if args.validate:
        validate_synthetic_data(args.validate)
    else:
        seed_data = load_seed_data(args.seed)
        generate_synthetic_data(seed_data, args.count, args.task, args.output)


if __name__ == '__main__':
    main()
