#!/usr/bin/env python3
"""
Script 8: Build consolidated AI context index
All rules summary, vocab highlights, polysemy summary, lesson outline.
Optimized for RAG injection.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
OUTPUT_FILE = DATA_DIR / "bible" / "language_learning" / "reference_index.json"

# Source files
SOURCES = {
    "grammar_comprehensive": DATA_DIR / "bible" / "language_learning" / "grammar_comprehensive.json",
    "sinna_lessons": DATA_DIR / "bible" / "language_learning" / "sinna_lessons.json",
    "zvs_rules": DATA_DIR / "bible" / "language_learning" / "zvs_rules.json",
    "polysemy_database": DATA_DIR / "bible" / "language_learning" / "polysemy_database.json",
    "exercises": DATA_DIR / "bible" / "language_learning" / "exercises_from_references.jsonl",
    "vocab_comprehensive": DATA_DIR / "bible" / "language_learning" / "vocab_comprehensive_v2.jsonl",
    "grammar_reference_v2": DATA_DIR / "bible" / "language_learning" / "grammar_reference_v2.json"
}


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    if not filepath.exists():
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_jsonl(filepath: Path) -> list:
    """Load JSONL file."""
    if not filepath.exists():
        return []
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return data


def build_grammar_summary(grammar: dict) -> dict:
    """Build concise grammar summary."""
    summary = {
        "word_order": "SOV",
        "tone_system": "two-tone (high/low)",
        "key_particles": {
            "a": "possessive",
            "in": "ergative/subordinator",
            "hiam": "question marker",
            "si": "negation"
        },
        "verb_morphology": {
            "tense_markers": ["-sak (past)", "-nak (progressive)", "-ah (future)"],
            "negation": "si + Verb",
            "question": "hiam (sentence-final)"
        },
        "noun_morphology": {
            "formation": ["Verb + -na (agent)", "Verb + -hna (abstract)", "Verb + -sak (result)"],
            "possession": "NP + a + NP"
        }
    }
    
    return summary


def build_vocab_highlights(vocab: list) -> dict:
    """Build vocabulary highlights."""
    highlights = {
        "total_words": len(vocab),
        "top_50": [],
        "categories": {}
    }
    
    # Get top 50 by frequency
    sorted_vocab = sorted(vocab, key=lambda x: x.get("frequency", 0), reverse=True)
    highlights["top_50"] = [
        {"zo": entry["zo"], "en": entry.get("en", "")}
        for entry in sorted_vocab[:50]
    ]
    
    # Categorize by source
    for entry in vocab:
        for source in entry.get("sources", []):
            if source not in highlights["categories"]:
                highlights["categories"][source] = 0
            highlights["categories"][source] += 1
    
    return highlights


def build_polysemy_summary(polysemy: dict) -> dict:
    """Build polysemy summary."""
    summary = {
        "total_polysemous_words": polysemy.get("metadata", {}).get("total_words", 0),
        "key_examples": [
            {"word": "kha", "meanings": ["spirit", "moon", "leg", "foot"]},
            {"word": "in", "meanings": ["ergative marker", "drink", "metal"]},
            {"word": "si", "meanings": ["negation", "death", "perish"]},
            {"word": "hi", "meanings": ["copula", "emphasis", "assertion"]},
            {"word": "pen", "meanings": ["emphasis marker", "old"]}
        ],
        "note": "Zolai is like Chinese: same word, different meaning based on context"
    }
    
    return summary


def build_lesson_outline(sinna: dict) -> dict:
    """Build lesson outline from Sinna."""
    outline = {
        "total_lessons": sinna.get("metadata", {}).get("total_lessons", 0),
        "lesson_topics": [],
        "progression": [
            "Basic ABC and pronunciation",
            "Simple sentences (SOV)",
            "Verb conjugation",
            "Tense markers",
            "Question formation",
            "Negation patterns",
            "Complex sentences",
            "Advanced grammar"
        ]
    }
    
    # Extract lesson topics
    lessons = sinna.get("lessons", [])
    for lesson in lessons[:10]:  # Top 10 for summary
        outline["lesson_topics"].append({
            "lesson": lesson.get("lesson_number", 0),
            "vocab_count": len(lesson.get("vocab", [])),
            "sentences_count": len(lesson.get("sentences", []))
        })
    
    return outline


def build_zvs_summary(zvs: dict) -> dict:
    """Build ZVS summary."""
    summary = {
        "standard": "ZVS 2018",
        "key_rules": [
            "Forbidden forms: pathian→pasian, ram→gam, fapa→tapa",
            "Apostrophe for glottal stop",
            "Verb+na=Noun formation",
            "Vowel chart: a e i o u + diphthongs"
        ],
        "forbidden_count": len(zvs.get("forbidden_forms", {}).get("replacements", []))
    }
    
    return summary


def main():
    """Main build function."""
    print("Building consolidated AI context index...")
    
    # Load all sources
    grammar = load_json(SOURCES["grammar_comprehensive"])
    sinna = load_json(SOURCES["sinna_lessons"])
    zvs = load_json(SOURCES["zvs_rules"])
    polysemy = load_json(SOURCES["polysemy_database"])
    exercises = load_jsonl(SOURCES["exercises"])
    vocab = load_jsonl(SOURCES["vocab_comprehensive"])
    grammar_v2 = load_json(SOURCES["grammar_reference_v2"])
    
    print(f"Loaded: grammar={len(grammar)} sections, sinna={len(sinna)} lessons")
    print(f"Loaded: zvs={len(zvs)} sections, polysemy={len(polysemy)} words")
    print(f"Loaded: {len(exercises)} exercises, {len(vocab)} vocab words")
    
    # Build index
    index = {
        "metadata": {
            "version": "1.0",
            "description": "Consolidated AI context index for Zolai language",
            "optimized_for": "RAG injection",
            "total_sections": 6
        },
        "grammar_summary": build_grammar_summary(grammar),
        "vocab_highlights": build_vocab_highlights(vocab),
        "polysemy_summary": build_polysemy_summary(polysemy),
        "lesson_outline": build_lesson_outline(sinna),
        "zvs_summary": build_zvs_summary(zvs),
        "exercise_stats": {
            "total_exercises": len(exercises),
            "types": {}
        }
    }
    
    # Count exercise types
    for exercise in exercises:
        ex_type = exercise.get("type", "unknown")
        index["exercise_stats"]["types"][ex_type] = index["exercise_stats"]["types"].get(ex_type, 0) + 1
    
    # Add quick reference
    index["quick_reference"] = {
        "common_phrases": [
            {"zo": "Pasian hiam?", "en": "Is it God?"},
            {"zo": "Tua hiam?", "en": "What is it?"},
            {"zo": "Kua hiam?", "en": "Who is it?"},
            {"zo": "Mi a kaw", "en": "Person's house"},
            {"zo": "Si tua", "en": "Not teach"},
            {"zo": "Hihleh", "en": "Hello"}
        ],
        "numbers": [
            {"zo": "khat", "en": "one"},
            {"zo": "hnih", "en": "two"},
            {"zo": "thum", "en": "three"},
            {"zo": "li", "en": "four"},
            {"zo": "nga", "en": "five"}
        ],
        "greetings": [
            {"zo": "Hihleh", "en": "Hello"},
            {"zo": "Va hihleh", "en": "Good morning"},
            {"zo": "Kha thuam", "en": "Good evening"}
        ]
    }
    
    # Save output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    
    # Print summary
    print("\n=== Reference Index Summary ===")
    print(f"Grammar sections: {len(index['grammar_summary'])}")
    print(f"Vocabulary: {index['vocab_highlights']['total_words']} words")
    print(f"Polysemous words: {index['polysemy_summary']['total_polysemous_words']}")
    print(f"Lessons: {index['lesson_outline']['total_lessons']}")
    print(f"Exercises: {index['exercise_stats']['total_exercises']}")


if __name__ == "__main__":
    main()