#!/usr/bin/env python3
"""
ZOLAI LANGUAGE LEARNING SYSTEM
Learn Zolai (ZVS 2018) from Zero → Fluent
Like Duolingo, but for Zolai language

Bible = data source
Goal = ANY human can learn Zolai from scratch
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

def load_course():
    path = LEARNING / "duolingo_course.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def load_vocab():
    path = LEARNING / "vocab_by_frequency.jsonl"
    data = []
    if path.exists():
        with open(path) as f:
            for line in f:
                data.append(json.loads(line))
    return data

def load_exercises():
    path = LEARNING / "exercises.jsonl"
    data = []
    if path.exists():
        with open(path) as f:
            for line in f:
                data.append(json.loads(line))
    return data

def show_banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════════════╗
║{NC}  {M}ZOLAI LANGUAGE LEARNING SYSTEM{NC}                           {C}║
║{NC}  {B}From Zero to Fluent — Like Duolingo for Zolai{NC}            {C}║
║{NC}  {G}30 weeks • 15 min/day • Real conversations{NC}               {C}║
║{NC}  {B}Bible = data source. YOU = the learner.{NC}                   {C}║
{C}╚══════════════════════════════════════════════════════════════╝{NC}
""")

def show_course_overview(course):
    print(f"\n{Y}═══ COURSE: {course.get('title', 'Zolai')} ═══{NC}")
    print(f"{course.get('subtitle', '')}")
    print(f"Duration: {course.get('total_weeks', 30)} weeks, {course.get('daily_minutes', 15)} min/day")
    print(f"Goal: {course.get('goal', 'Hold a basic conversation')}\n")
    
    for unit in course.get("units", []):
        print(f"  {M}Unit {unit['unit']}: {unit['name']} (Weeks {unit['weeks']}){NC}")
        print(f"    {unit['description']}")
        for lesson in unit.get("lessons", []):
            w = len(lesson.get("new_words", []))
            p = len(lesson.get("practice", []))
            print(f"      {G}W{lesson['week']}D{lesson['day']}{NC}: {lesson['title']} ({w} words, {p} exercises)")
        print()

def run_lesson(lesson):
    """Run a single lesson interactively."""
    print(f"\n{'='*60}")
    print(f"{Y}LESSON: {lesson.get('title', 'Unknown')}{NC}")
    print(f"{'='*60}\n")
    
    # 1. NEW WORDS
    new_words = lesson.get("new_words", [])
    if new_words:
        print(f"{G}── NEW WORDS ──{NC}\n")
        for i, (word, zolai, note) in enumerate(new_words, 1):
            print(f"  {i}. {C}{zolai}{NC} = {word} ({note})")
        print()
        
        # Practice pronunciation
        input(f"{B}Press Enter to practice pronunciation...{NC}")
        for word, zolai, note in new_words:
            print(f"  Say: {G}{zolai}{NC}")
            input(f"  (Press Enter after saying it)")
        print()
    
    # 2. GRAMMAR NOTE
    grammar = lesson.get("grammar", "")
    if grammar:
        print(f"{G}── GRAMMAR ──{NC}\n")
        print(f"  {grammar}\n")
    
    # 3. PRACTICE EXERCISES
    practices = lesson.get("practice", [])
    if practices:
        print(f"{G}── PRACTICE ──{NC}\n")
        score = 0
        total = len(practices)
        
        for i, ex in enumerate(practices, 1):
            ex_type = ex.get("type", "unknown")
            prompt = ex.get("prompt", "")
            answer = ex.get("answer", "")
            
            print(f"  {i}/{total}. {B}{ex_type.upper()}{NC}")
            print(f"  {prompt}")
            
            if ex_type in ("listen_repeat", "roleplay", "narrate", "writing", "reading", "describe", "comprehensive", "exam"):
                input(f"  {C}(Do the exercise, then press Enter){NC}")
                print(f"  {G}✓ Completed{NC}\n")
                score += 1
            else:
                user_input = input(f"  Your answer: ").strip()
                if user_input.lower() in answer.lower() or answer.lower() in user_input.lower():
                    print(f"  {G}✅ Correct!{NC}\n")
                    score += 1
                else:
                    print(f"  {R}❌ Wrong.{NC} Answer: {answer}\n")
        
        # Lesson complete
        pct = score / total * 100 if total else 0
        print(f"\n{Y}── LESSON COMPLETE ──{NC}")
        print(f"Score: {score}/{total} ({pct:.0f}%)")
        if pct == 100:
            print(f"{G}🌟 Perfect! You're amazing!{NC}")
        elif pct >= 80:
            print(f"{G}👏 Great job! Keep going!{NC}")
        elif pct >= 60:
            print(f"{B}💪 Good effort! Practice more!{NC}")
        else:
            print(f"{Y}📚 Keep practicing! You'll get it!{NC}")
        print()

def quiz_vocab(vocab, level=1, count=10):
    """Vocabulary quiz."""
    words = [v for v in vocab if v.get("level") == level and v.get("translation")]
    if not words:
        print(f"{R}No vocabulary at level {level}{NC}")
        return
    
    quiz_words = random.sample(words, min(count, len(words)))
    
    print(f"\n{Y}═══ VOCABULARY QUIZ — Level {level} ═══{NC}\n")
    print(f"Translate Zolai → English\n")
    
    score = 0
    for i, v in enumerate(quiz_words, 1):
        word = v["word"]
        answer = v.get("translation", "")
        
        print(f"  {i}/{len(quiz_words)}. {G}{word}{NC}")
        user_input = input("    Your answer: ").strip()
        
        if user_input.lower() in answer.lower() or answer.lower() in user_input.lower():
            print(f"    {G}✅ Correct!{NC}\n")
            score += 1
        else:
            print(f"    {R}❌ Wrong.{NC} Answer: {answer}\n")
    
    print(f"\n{Y}Score: {score}/{len(quiz_words)}{NC}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Language Learning System")
    parser.add_argument("--overview", action="store_true", help="Show full course overview")
    parser.add_argument("--lesson", type=str, help="Run lesson (format: W1D1)")
    parser.add_argument("--quiz", type=int, nargs="?", const=1, help="Quiz vocabulary at level")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()
    
    show_banner()
    
    print(f"{G}Loading Zolai language data...{NC}")
    course = load_course()
    vocab = load_vocab()
    exercises = load_exercises()
    print(f"{G}Loaded: {len(vocab)} words, {len(exercises)} exercises{NC}\n")
    
    if args.overview:
        show_course_overview(course)
    
    elif args.lesson:
        # Parse W1D1 format
        try:
            w = int(args.lesson[1:3])
            d = int(args.lesson[4:5])
            found = False
            for unit in course.get("units", []):
                for lesson in unit.get("lessons", []):
                    if lesson.get("week") == w and lesson.get("day") == d:
                        run_lesson(lesson)
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"{R}Lesson not found: {args.lesson}{NC}")
        except (ValueError, IndexError):
            print(f"{R}Invalid lesson format. Use: W1D1, W5D3, etc.{NC}")
    
    elif args.quiz:
        quiz_vocab(vocab, level=args.quiz)
    
    elif args.interactive:
        while True:
            print(f"\n{M}── Zolai Learning Menu ──{NC}")
            print(f"  {G}1{NC}) Course Overview")
            print(f"  {G}2{NC}) Start Lesson W1D1")
            print(f"  {G}3{NC}) Continue from where I left off")
            print(f"  {G}4{NC}) Vocabulary Quiz")
            print(f"  {G}5{NC}) Grammar Reference")
            print(f"  {G}0{NC}) Exit")
            
            choice = input(f"\n  Select: ").strip()
            if choice == "0":
                print(f"\n{G}Keep learning Zolai! See you next time!{NC}\n")
                break
            elif choice == "1":
                show_course_overview(course)
            elif choice == "2":
                # Start from W1D1
                for unit in course.get("units", []):
                    for lesson in unit.get("lessons", []):
                        if lesson.get("week") == 1 and lesson.get("day") == 1:
                            run_lesson(lesson)
                            break
            elif choice == "3":
                print(f"\n  {C}Available lessons:{NC}")
                for unit in course.get("units", []):
                    for lesson in unit.get("lessons", []):
                        w = lesson.get("week", 0)
                        d = lesson.get("day", 0)
                        title = lesson.get("title", "")
                        print(f"    W{w}D{d}: {title}")
                lesson_id = input(f"\n  Enter lesson (e.g., W5D3): ").strip()
                # Parse and run
                try:
                    w = int(lesson_id[1:3])
                    d = int(lesson_id[4:5])
                    for unit in course.get("units", []):
                        for lesson in unit.get("lessons", []):
                            if lesson.get("week") == w and lesson.get("day") == d:
                                run_lesson(lesson)
                                break
                except:
                    print(f"{R}Invalid format{NC}")
            elif choice == "4":
                lvl = input("  Level (1-8): ").strip()
                if lvl.isdigit():
                    quiz_vocab(vocab, level=int(lvl))
            elif choice == "5":
                # Show grammar
                grammar_path = LEARNING / "grammar_patterns.jsonl"
                if grammar_path.exists():
                    print(f"\n{Y}═══ ZOLAI GRAMMAR REFERENCE ═══{NC}\n")
                    with open(grammar_path) as f:
                        for line in f:
                            p = json.loads(line)
                            print(f"  {G}{p['pattern']}{NC}")
                            print(f"    {p['description']}")
                            print(f"    Frequency: {p['frequency']} verses\n")
    else:
        # Default: show overview and instructions
        show_course_overview(course)
        print(f"\n{C}Usage:{NC}")
        print(f"  python3 zolai_learn.py --overview              # See full course")
        print(f"  python3 zolai_learn.py --lesson W1D1           # Start a lesson")
        print(f"  python3 zolai_learn.py --quiz 1                # Quiz vocabulary")
        print(f"  python3 zolai_learn.py --interactive           # Interactive mode")

if __name__ == "__main__":
    main()
