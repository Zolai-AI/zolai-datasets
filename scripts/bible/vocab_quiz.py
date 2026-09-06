#!/usr/bin/env python3
"""
ZOLAI VOCABULARY QUIZ — Test word knowledge
Quiz types: bible, phrases, reverse, frequency
"""

import sys
import json
import random
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from bible_engine import load_jsonl, load_zo_en_dict

# Colors
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
C = "\033[0;36m"
M = "\033[0;35m"
NC = "\033[0m"

# Data paths
DATA = Path("/home/peter/Documents/Projects/zolai-ai/data")
VOCAB_INDEX = DATA / "bible" / "vocab_index_full.jsonl"
PHRASES_DB = DATA / "bible" / "phrases_v1.jsonl"
DICT_ZO_EN = DATA / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
SUPPLEMENT_DICT = DATA / "dictionary" / "processed" / "dict_bible_supplement_v1.jsonl"

class VocabQuiz:
    """Vocabulary quiz engine."""
    
    def __init__(self):
        self.vocab = self._load_vocab()
        self.phrases = self._load_phrases()
        self.dict_zo_en = self._load_dict()
    
    def _load_vocab(self) -> list[dict]:
        """Load vocabulary index."""
        return load_jsonl(VOCAB_INDEX)
    
    def _load_phrases(self) -> list[dict]:
        """Load phrases database."""
        return load_jsonl(PHRASES_DB)
    
    def _load_dict(self) -> dict[str, list[str]]:
        """Load ZO→EN dictionary."""
        return load_zo_en_dict()
    
    def quiz_bible(self, num_questions: int = 10):
        """Bible word quiz (ZO→EN)."""
        print(f"\n{C}═══ Bible Word Quiz ═══{NC}\n")
        print(f"Translate the Zolai word to English.\n")
        
        # Select random words from vocabulary
        words = random.sample(self.vocab, min(num_questions, len(self.vocab)))
        
        score = 0
        for i, word in enumerate(words, 1):
            zo_word = word.get("word", "")
            en_word = word.get("translation", "")
            frequency = word.get("frequency", 0)
            
            print(f"  {Y}Question {i}/{num_questions}{NC}")
            print(f"  What does '{M}{zo_word}{NC}' mean? (frequency: {frequency})")
            
            answer = input("  > ").strip().lower()
            
            if answer in en_word.lower() or en_word.lower() in answer:
                print(f"  {G}✅ Correct!{NC} {zo_word} = {en_word}\n")
                score += 1
            else:
                print(f"  {R}❌ Incorrect{NC}. {zo_word} = {en_word}\n")
        
        self._print_score(score, num_questions)
    
    def quiz_phrases(self, num_questions: int = 10):
        """Phrase quiz (multi-word expressions)."""
        print(f"\n{C}═══ Phrase Quiz ═══{NC}\n")
        print(f"Translate the Zolai phrase to English.\n")
        
        # Select random phrases
        phrases = random.sample(self.phrases, min(num_questions, len(self.phrases)))
        
        score = 0
        for i, phrase in enumerate(phrases, 1):
            zo_phrase = phrase.get("zo", "")
            en_phrase = phrase.get("en", "")
            
            print(f"  {Y}Question {i}/{num_questions}{NC}")
            print(f"  What does '{M}{zo_phrase}{NC}' mean?")
            
            answer = input("  > ").strip().lower()
            
            # Check if answer matches (fuzzy matching)
            if self._check_answer(answer, en_phrase):
                print(f"  {G}✅ Correct!{NC} {zo_phrase} = {en_phrase}\n")
                score += 1
            else:
                print(f"  {R}❌ Incorrect{NC}. {zo_phrase} = {en_phrase}\n")
        
        self._print_score(score, num_questions)
    
    def quiz_reverse(self, num_questions: int = 10):
        """Reverse quiz (EN→ZO)."""
        print(f"\n{C}═══ Reverse Quiz (EN→ZO) ═══{NC}\n")
        print(f"Translate the English word to Zolai.\n")
        
        # Select random words from dictionary
        words = random.sample(list(self.dict_zo_en.keys()), min(num_questions, len(self.dict_zo_en)))
        
        score = 0
        for i, en_word in enumerate(words, 1):
            zo_words = self.dict_zo_en[en_word]
            zo_answer = zo_words[0] if zo_words else ""
            
            print(f"  {Y}Question {i}/{num_questions}{NC}")
            print(f"  How do you say '{M}{en_word}{NC}' in Zolai?")
            
            answer = input("  > ").strip().lower()
            
            if answer in zo_answer.lower() or zo_answer.lower() in answer:
                print(f"  {G}✅ Correct!{NC} {en_word} = {zo_answer}\n")
                score += 1
            else:
                print(f"  {R}❌ Incorrect{NC}. {en_word} = {zo_answer}\n")
        
        self._print_score(score, num_questions)
    
    def quiz_frequency(self, num_questions: int = 10, top_n: int = 100):
        """Frequency-based quiz (top N most common words)."""
        print(f"\n{C}═══ Frequency Quiz (Top {top_n} Words) ═══{NC}\n")
        print(f"Test your knowledge of the {top_n} most common Zolai words.\n")
        
        # Sort by frequency and take top N
        sorted_vocab = sorted(self.vocab, key=lambda x: x.get("frequency", 0), reverse=True)
        top_words = sorted_vocab[:top_n]
        
        # Select random words from top N
        words = random.sample(top_words, min(num_questions, len(top_words)))
        
        score = 0
        for i, word in enumerate(words, 1):
            zo_word = word.get("word", "")
            en_word = word.get("translation", "")
            frequency = word.get("frequency", 0)
            
            print(f"  {Y}Question {i}/{num_questions}{NC}")
            print(f"  What does '{M}{zo_word}{NC}' mean? (rank: #{i}/{top_n})")
            
            answer = input("  > ").strip().lower()
            
            if answer in en_word.lower() or en_word.lower() in answer:
                print(f"  {G}✅ Correct!{NC} {zo_word} = {en_word}\n")
                score += 1
            else:
                print(f"  {R}❌ Incorrect{NC}. {zo_word} = {en_word}\n")
        
        self._print_score(score, num_questions)
    
    def _check_answer(self, answer: str, expected: str) -> bool:
        """Check if answer matches expected (fuzzy matching)."""
        answer = answer.lower().strip()
        expected = expected.lower().strip()
        
        # Exact match
        if answer == expected:
            return True
        
        # Partial match (answer contains expected or vice versa)
        if answer in expected or expected in answer:
            return True
        
        # Check individual words
        answer_words = set(answer.split())
        expected_words = set(expected.split())
        if answer_words & expected_words:  # Intersection
            return True
        
        return False
    
    def _print_score(self, score: int, total: int):
        """Print final score."""
        percentage = (score / total) * 100
        
        print(f"\n{C}═══ Quiz Results ═══{NC}\n")
        print(f"  Score: {score}/{total} ({percentage:.1f}%)\n")
        
        if percentage >= 90:
            print(f"  {G}🌟 Excellent! You're mastering Zolai!{NC}")
        elif percentage >= 70:
            print(f"  {G}👍 Good job! Keep practicing!{NC}")
        elif percentage >= 50:
            print(f"  {Y}📚 Keep learning! You're getting there!{NC}")
        else:
            print(f"  {R}💪 Don't give up! Practice makes perfect!{NC}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Vocabulary Quiz")
    parser.add_argument("--type", "-t", choices=["bible", "phrases", "reverse", "frequency"],
                        default="bible", help="Quiz type")
    parser.add_argument("--questions", "-q", type=int, default=10, help="Number of questions")
    parser.add_argument("--top", type=int, default=100, help="Top N words for frequency quiz")
    args = parser.parse_args()
    
    quiz = VocabQuiz()
    
    if args.type == "bible":
        quiz.quiz_bible(args.questions)
    elif args.type == "phrases":
        quiz.quiz_phrases(args.questions)
    elif args.type == "reverse":
        quiz.quiz_reverse(args.questions)
    elif args.type == "frequency":
        quiz.quiz_frequency(args.questions, args.top)

if __name__ == "__main__":
    main()
