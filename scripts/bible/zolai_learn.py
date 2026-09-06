#!/usr/bin/env python3
"""
ZOLAI LANGUAGE LEARNING SYSTEM
From Kindergarten to Graduate School — Learn Zolai like a human

Bible = data source (sentences, vocabulary, grammar)
Goal = Learn Zolai language systematically
Use = Later apply to other Zolai domains
"""

import json
import random
import sys
from pathlib import Path

DATA = Path("/home/peter/Documents/Projects/zolai-ai/data")
LEARNING = DATA / "bible" / "language_learning"
DICT = DATA / "dictionary" / "processed"

# Colors
R = "\033[0;31m"; G = "\033[0;32m"; Y = "\033[1;33m"
B = "\033[0;34m"; C = "\033[0;36m"; M = "\033[0;35m"; NC = "\033[0m"

def load_jsonl(path):
    data = []
    if path.exists():
        with open(path) as f:
            for line in f:
                data.append(json.loads(line))
    return data

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def show_banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════════════╗
║{NC}  {M}ZOLAI LANGUAGE LEARNING SYSTEM{NC}                           {C}║
║{NC}  {B}From Kindergarten to Graduate School{NC}                    {C}║
║{NC}  {B}23,383 words • 17 levels • 31,102 example sentences{NC}      {C}║
║{NC}  {G}Bible = data source. Goal = Learn Zolai language.{NC}        {C}║
{C}╚══════════════════════════════════════════════════════════════╝{NC}
""")

def show_curriculum(curriculum):
    print(f"\n{Y}═══ ZOLAI LEARNING CURRICULUM ═══{NC}\n")
    
    stages = [
        ("🏫 KINDERGARTEN", ["K1_Primer", "K2_Words"]),
        ("📚 PRIMARY SCHOOL", ["P1_Basic", "P2_Family", "P3_Questions", "P4_Tenses"]),
        ("📖 MIDDLE SCHOOL", ["M1_Connect", "M2_Describe", "M3_Voice"]),
        ("🎓 HIGH SCHOOL", ["H1_Read", "H2_Write", "H3_Lit"]),
        ("🏛️ UNIVERSITY", ["U1_Academic", "U2_Translate"]),
        ("🔬 GRADUATE SCHOOL", ["G1_CompLing", "G2_Corpus", "G3_Creative"]),
    ]
    
    for stage_name, levels in stages:
        print(f"  {M}{stage_name}{NC}")
        for lvl in levels:
            info = curriculum.get(lvl, {})
            name = info.get("name", lvl)
            age = info.get("age", "?")
            vocab = info.get("vocab", "?")
            print(f"    {G}{lvl:15s}{NC} — {name} (age {age}, ~{vocab} words)")
        print()

def show_level_exercises(exercises, level):
    level_exs = [e for e in exercises if e.get("level") == level]
    if not level_exs:
        print(f"\n  {R}No exercises at level {level}{NC}\n")
        return
    
    print(f"\n{Y}═══ LEVEL {level} — {len(level_exs)} exercises ═══{NC}\n")
    
    for i, ex in enumerate(level_exs[:10], 1):
        ex_type = ex.get("type", "unknown")
        
        if ex_type == "word_match":
            print(f"  {i}. {G}What does '{ex['instruction']}' mean?{NC}")
            user = input(f"    Answer: ").strip()
            answer = ex.get("answer", "")
            if user.lower() in answer.lower() or answer.lower() in user.lower():
                print(f"    {G}✅ Correct!{NC} → {answer}\n")
            else:
                print(f"    {R}❌ Wrong.{NC} Answer: {answer}\n")
        
        elif ex_type == "sentence_translate":
            print(f"  {i}. {G}Translate this:{NC}")
            print(f"    ZO: {ex.get('zo', '')[:80]}")
            user = input(f"    Your translation: ").strip()
            en = ex.get("en", "")[:80]
            print(f"    {B}KJV:{NC} {en}")
            print(f"    {C}(Check: does your answer match the meaning?){NC}\n")
        
        elif ex_type == "question_form":
            print(f"  {i}. {G}This is a question — what is being asked?{NC}")
            print(f"    ZO: {ex.get('zo', '')[:80]}")
            user = input(f"    What is the question? ").strip()
            en = ex.get("en", "")[:80]
            print(f"    {B}English:{NC} {en}\n")
        
        elif ex_type == "tense_identify":
            print(f"  {i}. {G}What tense is this sentence?{NC}")
            print(f"    ZO: {ex.get('zo', '')[:80]}")
            user = input(f"    Tense (past/present/future): ").strip()
            en = ex.get("en", "")[:80]
            print(f"    {B}English:{NC} {en}")
            print(f"    {C}(Look for: -sak=past, -uh=present, -hen=future){NC}\n")
        
        elif ex_type == "conjunction_use":
            print(f"  {i}. {G}How does 'leh' connect ideas here?{NC}")
            print(f"    ZO: {ex.get('zo', '')[:80]}")
            print(f"    EN: {ex.get('en', '')[:80]}")
            user = input(f"    Explain: ").strip()
            print(f"    {C}Leh = and/but (connects two ideas){NC}\n")
        
        elif ex_type == "reading_comprehension":
            print(f"  {i}. {G}READ & UNDERSTAND — {ex.get('book', '')}{NC}")
            print(f"    {C}Passage (Zolai):{NC}")
            print(f"    {ex.get('passage_zo', '')[:200]}")
            print(f"\n    {C}Passage (English):{NC}")
            print(f"    {ex.get('passage_en', '')[:200]}")
            for q in ex.get("questions", []):
                user = input(f"\n    Q: {q}\n    A: ").strip()
                print(f"    {C}(Think about this as you read){NC}")
            print()
        
        elif ex_type == "writing_prompt":
            print(f"  {i}. {G}WRITING EXERCISE: {ex.get('topic', '')}{NC}")
            print(f"    {ex.get('instruction', '')}")
            hints = ex.get("hints", [])
            if hints:
                print(f"    {C}Hints:{NC}")
                for h in hints:
                    print(f"      • {h}")
            print(f"\n    Write your answer on paper or in a file.")
            input(f"    Press Enter when done...")
            print()
        
        elif ex_type == "translation_exercise":
            print(f"  {i}. {G}TRANSLATE into Zolai:{NC}")
            print(f"    {ex.get('source', '')[:200]}")
            hints = ex.get("hints", [])
            if hints:
                print(f"    {C}Vocabulary:{NC} {', '.join(hints)}")
            print(f"\n    Write your Zolai translation on paper.")
            input(f"    Press Enter when done...")
            print()
        
        elif ex_type == "grammar_analysis":
            print(f"  {i}. {G}GRAMMAR ANALYSIS{NC}")
            print(f"    {ex.get('instruction', '')}")
            passage = ex.get("passage", "")
            if passage:
                print(f"    ZO: {passage[:150]}")
            print(f"    {C}Task: {ex.get('task', '')}{NC}")
            input(f"    Press Enter when done...")
            print()
        
        elif ex_type == "essay":
            print(f"  {i}. {G}ESSAY{NC}")
            print(f"    {ex.get('instruction', '')}")
            print(f"    {C}Word count: {ex.get('word_count', '300-500 words')}{NC}")
            print(f"    {C}Requirements: {', '.join(ex.get('requirements', []))}{NC}")
            print(f"\n    Write your essay on paper or in a file.")
            input(f"    Press Enter when done...")
            print()
    
    if len(level_exs) > 10:
        print(f"  {C}... and {len(level_exs) - 10} more exercises at this level{NC}\n")

def show_vocab_level(vocab, level, limit=20):
    words = [v for v in vocab if v.get("level") == level]
    print(f"\n{Y}═══ LEVEL {level} VOCABULARY (showing {min(limit, len(words))}/{len(words)}) ═══{NC}\n")
    for v in words[:limit]:
        trans = v.get("translation", "")
        freq = v.get("frequency", 0)
        print(f"  {G}{v['word']:20s}{NC} → {trans:40s} ({freq}x)")

def show_grammar_summary(grammar):
    print(f"\n{Y}═══ ZOLAI GRAMMAR PATTERNS ═══{NC}\n")
    for p in grammar:
        print(f"  {G}{p['pattern']}{NC}")
        print(f"    {p['description']}")
        print(f"    Found in {p['frequency']} verses\n")

def show_progress():
    print(f"\n{Y}═══ YOUR LEARNING PROGRESS ═══{NC}\n")
    print(f"  {C}Track your progress as you complete exercises{NC}")
    print(f"  Levels completed: __ / 17")
    print(f"  Exercises done: __ / 201")
    print(f"  Vocabulary learned: __ / 23,383")
    print()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Language Learning System")
    parser.add_argument("--curriculum", action="store_true", help="Show full curriculum")
    parser.add_argument("--level", type=int, help="Practice exercises at level (1-8)")
    parser.add_argument("--vocab", type=int, help="Show vocabulary at level (1-8)")
    parser.add_argument("--grammar", action="store_true", help="Show grammar patterns")
    parser.add_argument("--progress", action="store_true", help="Show learning progress")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()
    
    show_banner()
    
    # Load data
    print(f"{G}Loading Zolai language data...{NC}")
    curriculum = load_json(LEARNING / "curriculum.json")
    exercises = load_jsonl(LEARNING / "exercises.jsonl")
    vocab = load_jsonl(LEARNING / "vocab_by_frequency.jsonl")
    grammar = load_jsonl(LEARNING / "grammar_patterns.jsonl")
    print(f"{G}Loaded: {len(vocab)} words, {len(exercises)} exercises, {len(grammar)} grammar patterns{NC}\n")
    
    if args.curriculum:
        show_curriculum(curriculum)
    elif args.level:
        show_level_exercises(exercises, args.level)
    elif args.vocab:
        show_vocab_level(vocab, args.vocab)
    elif args.grammar:
        show_grammar_summary(grammar)
    elif args.progress:
        show_progress()
    elif args.interactive:
        while True:
            print(f"\n{M}── Main Menu ──{NC}")
            print(f"  {G}1{NC}) Show Curriculum")
            print(f"  {G}2{NC}) Practice Level 1 (Words)")
            print(f"  {G}3{NC}) Practice Level 2 (Simple Sentences)")
            print(f"  {G}4{NC}) Practice Level 3 (Questions)")
            print(f"  {G}5{NC}) Practice Level 4 (Tenses)")
            print(f"  {G}6{NC}) Practice Level 5 (Conjunctions)")
            print(f"  {G}7{NC}) Practice Level 6 (Reading)")
            print(f"  {G}8{NC}) Practice Level 7 (Writing)")
            print(f"  {G}9{NC}) Practice Level 8 (Academic)")
            print(f"  {G}V{NC}) View Vocabulary")
            print(f"  {G}G{NC}) Grammar Patterns")
            print(f"  {G}P{NC}) My Progress")
            print(f"  {G}0{NC}) Exit")
            
            choice = input(f"\n  Select: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                show_curriculum(curriculum)
            elif choice in ("2","3","4","5","6","7","8","9"):
                show_level_exercises(exercises, int(choice))
            elif choice.lower() == "v":
                lvl = input("  Level (1-8): ").strip()
                if lvl.isdigit():
                    show_vocab_level(vocab, int(lvl))
            elif choice.lower() == "g":
                show_grammar_summary(grammar)
            elif choice.lower() == "p":
                show_progress()
    else:
        # Default: show curriculum and instructions
        show_curriculum(curriculum)
        print(f"\n{C}Usage:{NC}")
        print(f"  python3 zolai_learn.py --curriculum        # Show learning path")
        print(f"  python3 zolai_learn.py --level 1           # Practice Level 1")
        print(f"  python3 zolai_learn.py --vocab 1           # View Level 1 vocabulary")
        print(f"  python3 zolai_learn.py --grammar           # Show grammar patterns")
        print(f"  python3 zolai_learn.py --interactive       # Interactive mode")

if __name__ == "__main__":
    main()
