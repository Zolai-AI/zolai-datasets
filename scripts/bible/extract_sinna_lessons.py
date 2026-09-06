#!/usr/bin/env python3
"""
Script 2: Extract Sinna lessons from Zolai_Sinna.md
Parses 34 lessons into structured JSON with vocab, sentences, grammar.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
INPUT_FILE = DATA_DIR / "reference" / "grammar" / "Zolai_Sinna.md"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "sinna_lessons.json"


def parse_lessons(text: str) -> list:
    """Parse Sinna N lessons from text."""
    lessons = []
    
    # Split by lesson headers
    lesson_pattern = r'(?:Sinna|SINNA)\s+(\d+)[:\s]*(.*?)(?=(?:Sinna|SINNA)\s+\d+|$)'
    matches = re.finditer(lesson_pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        lesson_num = int(match.group(1))
        content = match.group(2).strip()
        
        lesson = {
            "lesson_number": lesson_num,
            "title": f"Sinna {lesson_num}",
            "vocab": [],
            "sentences": [],
            "grammar_point": "",
            "raw_content": content[:2000]  # Truncate for storage
        }
        
        # Extract vocabulary (ZO → EN pairs)
        vocab_pattern = r'(\w+)\s*[-–—]\s*([A-Za-z][\w\s]*?)(?:\n|$)'
        vocab_matches = re.findall(vocab_pattern, content)
        for zo, en in vocab_matches:
            if len(zo) < 20 and len(en) < 50:  # Sanity check
                lesson["vocab"].append({"zo": zo.strip(), "en": en.strip()})
        
        # Extract sentences (look for longer lines)
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 20 and '–' not in line and not line.startswith('#'):
                # Likely a sentence
                lesson["sentences"].append(line)
        
        # Extract grammar points (lines with "grammar", "tense", "pattern", etc.)
        grammar_keywords = ['grammar', 'tense', 'pattern', 'rule', 'note', 'remember']
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in grammar_keywords):
                lesson["grammar_point"] = line.strip()
                break
        
        lessons.append(lesson)
    
    return lessons


def main():
    """Main extraction function."""
    print(f"Reading {INPUT_FILE}...")
    
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found")
        return
    
    text = INPUT_FILE.read_text(encoding='utf-8')
    print(f"Processing {len(text)} characters...")
    
    # Parse lessons
    lessons = parse_lessons(text)
    print(f"Found {len(lessons)} lessons")
    
    # Build output
    output = {
        "metadata": {
            "source": "Zolai_Sinna.md",
            "total_lessons": len(lessons),
            "description": "34 progressive lessons from ABC to advanced Zolai"
        },
        "lessons": lessons
    }
    
    # Save output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()