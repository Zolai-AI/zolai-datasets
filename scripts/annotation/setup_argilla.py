#!/usr/bin/env python3
"""
Argilla Community Annotation Platform Setup for Zolai

This script sets up Argilla for community-driven data annotation.
Based on Masakhane Playbook and best practices from ACL 2025.

Requirements:
    pip install argilla

Usage:
    python setup_argilla.py --init
    python setup_argilla.py --create-dataset "zolai_validation"
    python setup_argilla.py --import-data data/bible/parallel_corpus_v1.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    import argilla as rg
    ARGILLA_AVAILABLE = True
except ImportError:
    ARGILLA_AVAILABLE = False
    print("Warning: argilla not installed. Run: pip install argilla")


def init_argilla(api_url: str = "http://localhost:6900", api_key: str = "owner.apikey"):
    """Initialize Argilla connection."""
    if not ARGILLA_AVAILABLE:
        print("Cannot initialize: argilla not installed")
        return False
    
    rg.init(api_url=api_url, api_key=api_key)
    print(f"✅ Connected to Argilla at {api_url}")
    return True


def create_zolai_dataset(dataset_name: str = "zolai_validation"):
    """Create a Zolai-specific annotation dataset."""
    if not ARGILLA_AVAILABLE:
        print("Cannot create dataset: argilla not installed")
        return None
    
    # Define annotation fields
    fields = [
        rg.TextField(name="zolai_text", title="Zolai Text"),
        rg.TextField(name="english_translation", title="English Translation"),
        rg.TextField(name="context", title="Context (optional)"),
    ]
    
    # Define annotation questions
    questions = [
        rg.RatingQuestion(
            name="translation_quality",
            title="Translation Quality",
            description="Rate the accuracy of the English translation",
            values={
                1: "Poor - Major errors",
                2: "Fair - Some errors",
                3: "Good - Minor issues",
                4: "Very Good - Accurate",
                5: "Excellent - Perfect"
            }
        ),
        rg.RatingQuestion(
            name="cultural_accuracy",
            title="Cultural Accuracy",
            description="Does the translation respect cultural context?",
            values={
                1: "Inappropriate",
                2: "Questionable",
                3: "Acceptable",
                4: "Good",
                5: "Excellent"
            }
        ),
        rg.MultiChoiceQuestion(
            name="issues",
            title="Issues Found",
            description="Select all that apply",
            values=[
                "Grammar error",
                "Vocabulary error",
                "Cultural inappropriateness",
                "Missing context",
                "Unnatural phrasing",
                "None - all good"
            ],
            required=False
        ),
        rg.TextQuestion(
            name="suggested_correction",
            title="Suggested Correction",
            description="If issues found, suggest correction (optional)",
            required=False
        ),
    ]
    
    # Create dataset
    dataset = rg.Dataset(
        name=dataset_name,
        fields=fields,
        questions=questions,
        guidelines="Annotate Zolai-English translation pairs for quality and cultural accuracy."
    )
    
    print(f"✅ Created dataset: {dataset_name}")
    return dataset


def import_bible_data(file_path: str, dataset_name: str = "zolai_validation", limit: int = 100):
    """Import Bible data for annotation."""
    if not ARGILLA_AVAILABLE:
        print("Cannot import: argilla not installed")
        return
    
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            
            entry = json.loads(line)
            zolai = entry.get('zo_tdb77', '') or entry.get('zo_tedim2010', '')
            english = entry.get('en_kJV', '')
            
            if zolai and english:
                records.append(
                    rg.Record(
                        fields={
                            "zolai_text": zolai,
                            "english_translation": english,
                            "context": f"Reference: {entry.get('ref', '')}"
                        },
                        metadata={
                            "book": entry.get('book', ''),
                            "chapter": entry.get('chapter', ''),
                            "verse": entry.get('verse', '')
                        }
                    )
                )
    
    # Log records to dataset
    rg.log(records, name=dataset_name)
    print(f"✅ Imported {len(records)} records to {dataset_name}")


def list_datasets():
    """List all available datasets."""
    if not ARGILLA_AVAILABLE:
        print("Cannot list: argilla not installed")
        return
    
    datasets = rg.list_datasets()
    print("\n=== Available Datasets ===")
    for ds in datasets:
        print(f"  - {ds.name}")


def main():
    parser = argparse.ArgumentParser(description='Zolai Annotation Platform Setup')
    parser.add_argument('--init', action='store_true', help='Initialize Argilla connection')
    parser.add_argument('--create-dataset', type=str, help='Create a new dataset')
    parser.add_argument('--import-data', type=str, help='Import data from JSONL file')
    parser.add_argument('--dataset', type=str, default='zolai_validation', help='Dataset name')
    parser.add_argument('--limit', type=int, default=100, help='Import limit')
    parser.add_argument('--list', action='store_true', help='List available datasets')
    
    args = parser.parse_args()
    
    if args.init:
        init_argilla()
    elif args.create_dataset:
        create_zolai_dataset(args.create_dataset)
    elif args.import_data:
        import_bible_data(args.import_data, args.dataset, args.limit)
    elif args.list:
        list_datasets()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
