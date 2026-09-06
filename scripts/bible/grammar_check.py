#!/usr/bin/env python3
"""
ZOLAI GRAMMAR CHECKER — Verify sentence correctness
Checks negation patterns, question forms, and verb usage
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from bible_engine import GrammarMatcher, load_jsonl

# Colors
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
C = "\033[0;36m"
NC = "\033[0m"

# Load grammar patterns
GRAMMAR_PATTERNS = Path("/home/peter/Documents/Projects/zolai-ai/data/bible/grammar_patterns_text.jsonl")
patterns_db = load_jsonl(GRAMMAR_PATTERNS)
matcher = GrammarMatcher(patterns_db)

def check_grammar(sentence: str) -> dict:
    """Check grammar of a Zolai sentence."""
    results = {
        "sentence": sentence,
        "negation": None,
        "question": None,
        "verb": None,
        "patterns": [],
        "errors": [],
        "suggestions": [],
    }
    
    # Check negation
    neg_result = matcher.check_negation(sentence)
    results["negation"] = neg_result
    if neg_result.get("correct") is False:
        results["errors"].append({
            "type": "negation",
            "message": neg_result.get("reason", ""),
            "suggestion": f"Use '{neg_result.get('negation', '')}' instead",
        })
    
    # Check question
    q_result = matcher.check_question(sentence)
    results["question"] = q_result
    
    # Check verb conjugation
    v_result = matcher.check_verb_conjugation(sentence)
    results["verb"] = v_result
    if v_result.get("correct") is False:
        results["errors"].append({
            "type": "verb",
            "message": v_result.get("reason", ""),
            "suggestion": v_result.get("suggestion", ""),
        })
    
    # Match patterns
    patterns = matcher.match_all(sentence)
    results["patterns"] = patterns
    
    return results

def print_results(results: dict):
    """Print grammar check results."""
    print(f"\n{C}═══ Grammar Check Results ═══{NC}\n")
    print(f"  Sentence: {Y}{results['sentence']}{NC}\n")
    
    # Print negation result
    neg = results["negation"]
    if neg and neg.get("person"):
        if neg.get("correct"):
            print(f"  {G}✅ Negation: Correct{NC}")
            print(f"     Person: {neg['person']}, Particle: {neg['negation']}")
        else:
            print(f"  {R}❌ Negation: Incorrect{NC}")
            print(f"     {R}{neg['reason']}{NC}")
    
    # Print question result
    q = results["question"]
    if q and q.get("type"):
        print(f"  {G}✅ Question: {q['type']} question (marker: {q['marker']}){NC}")
    
    # Print verb result
    v = results["verb"]
    if v and v.get("correct") is False:
        print(f"  {R}❌ Verb: {v['issue']}{NC}")
        print(f"     {R}{v['reason']}{NC}")
        if v.get("suggestion"):
            print(f"     {G}Suggestion: {v['suggestion']}{NC}")
    
    # Print patterns
    if results["patterns"]:
        print(f"\n  {C}Patterns detected:{NC}")
        for p in results["patterns"][:5]:
            print(f"    • {p['pattern']}: {p['description']}")
    
    # Print errors summary
    if results["errors"]:
        print(f"\n  {R}Found {len(results['errors'])} error(s):{NC}")
        for err in results["errors"]:
            print(f"    • {err['type']}: {err['message']}")
    else:
        print(f"\n  {G}No errors found!{NC}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Grammar Checker")
    parser.add_argument("--sentence", "-s", type=str, help="Sentence to check")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    args = parser.parse_args()
    
    if args.interactive:
        print(f"{C}═══ Zolai Grammar Checker ═══{NC}")
        print(f"Enter a Zolai sentence to check (Ctrl+D to exit):\n")
        try:
            while True:
                sentence = input("> ").strip()
                if sentence:
                    results = check_grammar(sentence)
                    print_results(results)
                    print()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{G}Goodbye!{NC}")
    elif args.sentence:
        results = check_grammar(args.sentence)
        print_results(results)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
