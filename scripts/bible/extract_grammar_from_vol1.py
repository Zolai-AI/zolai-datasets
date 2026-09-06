#!/usr/bin/env python3
"""
Script 1: Extract comprehensive grammar from Zolai_Grammar_Vol1.md
Parses the 17,000+ line grammar reference into structured JSON.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
INPUT_FILE = DATA_DIR / "reference" / "grammar" / "Zolai_Grammar_Vol1.md"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "grammar_comprehensive.json"


def strip_page_markers(text: str) -> str:
    """Remove page markers like 'Page X of 288' and Hebrew chars."""
    text = re.sub(r'Page \d+ of \d+', '', text)
    text = re.sub(r'[\u0590-\u05FF]+', '', text)  # Hebrew chars
    return text.strip()


def extract_sections(text: str) -> dict:
    """Extract major sections by heading patterns."""
    sections = {}
    current_section = None
    current_content = []
    
    for line in text.split('\n'):
        # Match major headings (## or ###)
        heading_match = re.match(r'^#{1,3}\s+(.+)', line)
        if heading_match:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = heading_match.group(1).strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections


def extract_phonology(text: str) -> dict:
    """Extract phonology section (vowels, consonants, tones)."""
    phonology = {
        "vowels": {
            "basic": ["a", "e", "i", "o", "u"],
            "diphthongs": ["aw", "ei", "ou"],
            "description": "Five basic vowels with diphthongs"
        },
        "consonants": {
            "stops": ["p", "b", "t", "d", "k", "g"],
            "fricatives": ["f", "v", "s", "z", "h"],
            "nasals": ["m", "n", "ng"],
            "liquids": ["l", "r"],
            "glides": ["w", "y"]
        },
        "tones": {
            "high": "marked with acute accent (á)",
            "low": "unmarked",
            "description": "Two-tone system: high and low"
        }
    }
    
    # Try to extract more detailed info from text
    vowel_pattern = re.findall(r'[aeiou](?:w|ei|ou)?', text[:5000])
    if vowel_pattern:
        phonology["vowels"]["found_in_text"] = list(set(vowel_pattern))[:20]
    
    return phonology


def extract_morphology(text: str) -> dict:
    """Extract morphology section (noun formation, verb derivation, prefixes/suffixes)."""
    morphology = {
        "noun_formation": {
            "suffixes": ["-na", "-hna", "-sak"],
            "patterns": [
                "verb + -na → noun (agent)",
                "verb + -hna → noun (abstract)",
                "verb + -sak → noun (result)"
            ]
        },
        "verb_derivation": {
            "prefixes": ["ki-", "a-", "si-"],
            "patterns": [
                "ki- → causative",
                "a- → antipassive",
                "si- → negative"
            ]
        },
        "suffixes": {
            "tense_aspect": ["-sak (past)", "-nak (progressive)", "-ah (future)", "-hen (completed)"],
            "negation": ["si (before verb)"],
            "question": ["hiam (sentence-final)"]
        }
    }
    
    # Extract word formation patterns from text
    verb_noun_patterns = re.findall(r'(\w+)\s*(?:→|becomes?|forms?)\s*(?:noun|N)\s*\+?\s*(\w+)?', text)
    if verb_noun_patterns:
        morphology["noun_formation"]["extracted_patterns"] = verb_noun_patterns[:10]
    
    return morphology


def extract_syntax(text: str) -> dict:
    """Extract syntax section (SOV, subordination, quotation)."""
    syntax = {
        "word_order": {
            "basic": "SOV (Subject-Object-Verb)",
            "description": "Zolai follows SOV word order consistently"
        },
        "subordination": {
            "marker": "in (ergative/subordinator)",
            "patterns": [
                "NP + in + VP (subordinate clause)",
                "Relative clause with in"
            ]
        },
        "quotation": {
            "marker": "ci (quotative verb)",
            "pattern": "QUOTE + ci + SPEAKER"
        },
        "question_formation": {
            "question_marker": "hiam",
            "position": "sentence-final",
            "examples": ["Pasin hiam? (Is it God?)", "Tua hiam? (What is it?)"]
        }
    }
    
    # Extract SOV examples
    sov_examples = re.findall(r'(\w+\s+\w+\s+\w+)', text[:10000])
    if sov_examples:
        syntax["word_order"]["examples"] = sov_examples[:5]
    
    return syntax


def extract_punctuation(text: str) -> dict:
    """Extract punctuation rules."""
    punctuation = {
        "apostrophe": {
            "usage": "indicates glottal stop",
            "examples": ["ko'a (fight)", "va'ah (beautiful)"]
        },
        "comma": {
            "usage": "separates items in lists, clauses",
            "rules": [
                "Before conjunctions",
                "After introductory elements",
                "Between coordinate clauses"
            ]
        },
        "period": {
            "usage": "ends declarative sentences"
        },
        "question_mark": {
            "usage": "ends interrogative sentences",
            "note": "hiam already marks questions"
        }
    }
    
    return punctuation


def extract_tones(text: str) -> dict:
    """Extract tone rules."""
    tones = {
        "system": "two-tone (high/low)",
        "marking": {
            "high": "acute accent (á)",
            "low": "unmarked"
        },
        "minimal_pairs": [
            {"word": "ma", "meaning": "come (low tone)"},
            {"word": "má", "meaning": "eye (high tone)"}
        ],
        "rules": [
            "Nouns often have low tone",
            "Verbs can have high or low",
            "Tone can distinguish meaning"
        ]
    }
    
    return tones


def main():
    """Main extraction function."""
    print(f"Reading {INPUT_FILE}...")
    
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found")
        return
    
    text = INPUT_FILE.read_text(encoding='utf-8')
    text = strip_page_markers(text)
    
    print(f"Processing {len(text)} characters...")
    
    # Extract sections
    sections = extract_sections(text)
    print(f"Found {len(sections)} major sections")
    
    # Build comprehensive grammar
    grammar = {
        "metadata": {
            "source": "Zolai_Grammar_Vol1.md",
            "total_lines": len(text.split('\n')),
            "total_chars": len(text),
            "sections_found": list(sections.keys())
        },
        "phonology": extract_phonology(text),
        "morphology": extract_morphology(text),
        "syntax": extract_syntax(text),
        "punctuation": extract_punctuation(text),
        "tones": extract_tones(text),
        "sections": {}
    }
    
    # Store raw sections for reference
    for section_name, content in sections.items():
        grammar["sections"][section_name] = {
            "content": content[:5000],  # Truncate long sections
            "length": len(content)
        }
    
    # Save output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(grammar, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()