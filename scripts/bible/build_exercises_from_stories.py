#!/usr/bin/env python3
"""
Script 5: Build exercises from Gentehna_Tuamtuam_le_A_Deihnate.txt (51 stories)
Generates fill-in-blank, sentence reordering, vocab MCQ, comprehension Q.
"""

import json
import re
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
INPUT_FILE = DATA_DIR / "reference" / "grammar" / "Gentehna_Tuamtuam_le_A_Deihnate.txt"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "exercises_from_references.jsonl"


def parse_stories(text: str) -> list:
    """Parse stories from Gentehna Tuamtuam text (numbered sections with A Thugil/A Deihna)."""
    stories = []
    
    # Split by numbered sections: "N. Title"
    # The actual stories start after the TOC (around line 219)
    sections = re.split(r'(?=^\d+\.\s)', text, flags=re.MULTILINE)
    
    for section in sections:
        # Match "N. Title" at start
        header_match = re.match(r'^(\d+)\.\s+(.+?)$', section, re.MULTILINE)
        if not header_match:
            continue
        
        story_num = int(header_match.group(1))
        title = header_match.group(2).strip()
        
        # Extract sentences (Zolai sentences end with "hi" or punctuation)
        sentences = []
        for line in section.split('\n'):
            line = line.strip()
            # Skip headers, page markers, empty lines
            if not line or line.startswith('PA Lian') or line.startswith('Page '):
                continue
            if 'A Thugil:' in line or 'A Deihna:' in line:
                continue
            # Keep meaningful lines (Zolai sentences)
            if len(line) > 15 and ('hi' in line or 'ci' in line or 'in' in line):
                sentences.append(line)
        
        if sentences:
            stories.append({
                "story_number": story_num,
                "title": title,
                "sentences": sentences[:10],  # Limit per story
                "word_count": sum(len(s.split()) for s in sentences)
            })
    
    return stories


def generate_fill_in_blank(sentences: list) -> list:
    """Generate fill-in-blank exercises from sentences."""
    exercises = []
    
    for sentence in sentences[:5]:  # Limit to 5 per story
        words = sentence.split()
        if len(words) > 3:
            # Remove a random word
            idx = random.randint(1, len(words) - 2)
            correct_word = words[idx]
            words[idx] = "_____"
            blank_sentence = " ".join(words)
            
            exercises.append({
                "type": "fill_in_blank",
                "question": f"Fill in the blank: {blank_sentence}",
                "answer": correct_word,
                "hint": f"The missing word is '{correct_word}'",
                "original_sentence": sentence
            })
    
    return exercises


def generate_sentence_reorder(sentences: list) -> list:
    """Generate sentence reordering exercises (SOV practice)."""
    exercises = []
    
    for sentence in sentences[:3]:  # Limit to 3 per story
        words = sentence.split()
        if len(words) > 3:
            # Shuffle words
            shuffled = words.copy()
            random.shuffle(shuffled)
            
            exercises.append({
                "type": "sentence_reorder",
                "question": f"Rearrange these words into correct Zolai (SOV) order: {' '.join(shuffled)}",
                "answer": sentence,
                "words": shuffled
            })
    
    return exercises


def generate_vocab_mcq(stories: list) -> list:
    """Generate vocabulary multiple choice questions."""
    exercises = []
    
    # Extract unique words from all stories
    all_words = []
    for story in stories:
        for sentence in story["sentences"]:
            words = sentence.split()
            all_words.extend([w for w in words if len(w) > 2])
    
    # Get unique words
    unique_words = list(set(all_words))
    
    # Generate MCQ for random words
    if unique_words:
        sample_words = random.sample(unique_words, min(10, len(unique_words)))
        
        for word in sample_words:
            # Find context
            for story in stories:
                for sentence in story["sentences"]:
                    if word in sentence:
                        # Create wrong options
                        other_words = [w for w in unique_words if w != word]
                        if len(other_words) >= 3:
                            wrong_options = random.sample(other_words, 3)
                            options = [word] + wrong_options
                            random.shuffle(options)
                            
                            exercises.append({
                                "type": "vocab_mcq",
                                "question": f"What does '{word}' mean in context?",
                                "sentence": sentence,
                                "options": options,
                                "answer": word
                            })
                        break
                else:
                    continue
                break
    
    return exercises


def generate_comprehension_questions(stories: list) -> list:
    """Generate comprehension questions."""
    exercises = []
    
    question_templates = [
        "What happens in this story?",
        "Who are the main characters?",
        "Where does the story take place?",
        "What is the main event?",
        "How does the story end?"
    ]
    
    for story in stories[:5]:  # Limit to 5 stories
        if story["sentences"]:
            # Use first sentence as context
            context = story["sentences"][0]
            
            exercises.append({
                "type": "comprehension",
                "question": random.choice(question_templates),
                "context": context,
                "answer": f"Based on: {context[:100]}...",
                "story_number": story["story_number"]
            })
    
    return exercises


def main():
    """Main build function."""
    print(f"Reading {INPUT_FILE}...")
    
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found")
        return
    
    text = INPUT_FILE.read_text(encoding='utf-8')
    print(f"Processing {len(text)} characters...")
    
    # Parse stories
    stories = parse_stories(text)
    print(f"Found {len(stories)} stories")
    
    # Generate exercises
    all_exercises = []
    
    for story in stories:
        # Generate different exercise types
        fill_in_blank = generate_fill_in_blank(story["sentences"])
        sentence_reorder = generate_sentence_reorder(story["sentences"])
        
        all_exercises.extend(fill_in_blank)
        all_exercises.extend(sentence_reorder)
    
    # Add vocab MCQ and comprehension
    vocab_mcq = generate_vocab_mcq(stories)
    comprehension = generate_comprehension_questions(stories)
    
    all_exercises.extend(vocab_mcq)
    all_exercises.extend(comprehension)
    
    print(f"Generated {len(all_exercises)} exercises")
    
    # Save to JSONL
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(json.dumps(exercise, ensure_ascii=False) + '\n' for exercise in all_exercises)
    
    print(f"Saved to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()