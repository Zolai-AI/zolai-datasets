#!/usr/bin/env python3
"""Format Zolai training data into Qwen3 chat template format.

Loads Bible parallel corpus, Zolai-English parallel pairs, and dictionary
entries, then produces Qwen3-compatible JSONL with im_start/im_end tokens
for QLoRA fine-tuning on Qwen3-4B.

Output format per line:
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user",   "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}

Usage:
    python format_training_data.py --output-dir ./output --max-pairs 50000
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[3]

DATA_PATHS = {
    "bible": WORKSPACE / "data/bible/parallel_corpus_v1.jsonl",
    "parallel": WORKSPACE / "data/parallel/zo_en_pairs_combined_v1.jsonl",
    "dict": WORKSPACE / "data/dictionary/processed/dict_zo_en_clean.jsonl",
}

SYSTEM_PROMPT = (
    "You are a Tedim Zolai (Zomi) language expert. "
    "You follow ZVS 2018 orthography strictly.\n\n"
    "Grammar rules:\n"
    "- Word order is SOV (Subject-Object-Verb).\n"
    "- Use 'hiam' for yes/no questions (not 'ze').\n"
    "- Use 'bang hang' or 'kua' for content questions.\n"
    "- 1st/2nd person negation: 'kei'. 3rd person negation: 'lo'.\n"
    "- Ergative marker: 'in' for transitive subjects.\n"
    "- Tense: -sak (past), -ah (progressive), -hen (completive), ding (future).\n\n"
    "Forbidden forms (use ZVS 2018 equivalents):\n"
    "- pathian → pasian (God)\n"
    "- ram → gam (earth)\n"
    "- fapa → tapa (fire)\n"
    "- bawipa → topa (lord)\n"
    "- siangpahrang → kumpipa (angel)\n"
    "- cu/cun → tua\n"
    "- suah → chuak\n"
    "- zalenna → suahtakna\n"
    "- nunnak → nuntakna\n\n"
    "Respond only in the requested language. "
    "For translations, give the single best translation on the first line, "
    "then optionally a brief grammar note on the second line."
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load a JSONL file, returning up to *limit* records."""
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_bible(limit: int | None = None) -> list[dict[str, str]]:
    """Load Bible parallel corpus → list of {zo, en, ref} dicts."""
    rows = _load_jsonl(DATA_PATHS["bible"], limit=limit)
    out: list[dict[str, str]] = []
    for r in rows:
        zo = (r.get("zo_tdb77") or "").strip()
        en = (r.get("en_kJV") or "").strip()
        ref = (r.get("ref") or "").strip()
        if zo and en:
            out.append({"zo": zo, "en": en, "ref": ref})
    return out


def load_parallel(limit: int | None = None) -> list[dict[str, str]]:
    """Load Zolai-English parallel pairs."""
    rows = _load_jsonl(DATA_PATHS["parallel"], limit=limit)
    out: list[dict[str, str]] = []
    for r in rows:
        zo = (r.get("zolai") or "").strip()
        en = (r.get("english") or "").strip()
        if zo and en:
            out.append({"zo": zo, "en": en, "ref": ""})
    return out


def load_dictionary(limit: int | None = None) -> list[dict[str, str]]:
    """Load dictionary entries → list of {zo, en} dicts."""
    rows = _load_jsonl(DATA_PATHS["dict"], limit=limit)
    out: list[dict[str, str]] = []
    for r in rows:
        zo = (r.get("zolai") or "").strip()
        en = (r.get("english_clean") or "").strip()
        if zo and en:
            out.append({"zo": zo, "en": en})
    return out


# ---------------------------------------------------------------------------
# Training example builders
# ---------------------------------------------------------------------------


def _chat(system: str, user: str, assistant: str) -> dict[str, Any]:
    """Wrap a single-turn conversation into the messages list format."""
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_translation_en_to_zo(
    pair: dict[str, str],
) -> dict[str, Any] | None:
    """Build an EN → ZO translation example."""
    ref_note = f" (Ref: {pair['ref']})" if pair.get("ref") else ""
    user = f"Translate the following English sentence into Tedim Zolai.{ref_note}\n\n{pair['en']}"
    return _chat(SYSTEM_PROMPT, user, pair["zo"])


def build_translation_zo_to_en(
    pair: dict[str, str],
) -> dict[str, Any] | None:
    """Build a ZO → EN translation example."""
    ref_note = f" (Ref: {pair['ref']})" if pair.get("ref") else ""
    user = f"Translate the following Tedim Zolai sentence into English.{ref_note}\n\n{pair['zo']}"
    return _chat(SYSTEM_PROMPT, user, pair["en"])


def build_vocabulary_quiz(entry: dict[str, str]) -> dict[str, Any] | None:
    """Build a vocabulary quiz: ZO → EN meaning."""
    user = (
        f"What does the Tedim Zolai word '{entry['zo']}' mean in English? "
        "Give the single best translation."
    )
    return _chat(SYSTEM_PROMPT, user, entry["en"])


def build_grammar_exercise(pair: dict[str, str]) -> dict[str, Any] | None:
    """Build a grammar analysis exercise from a parallel pair."""
    user = (
        "Analyze the grammar of the following Zolai sentence. "
        "Identify: subject, object, verb position, tense marker, and any particles. "
        "Then give the English translation.\n\n"
        f"Zolai: {pair['zo']}"
    )
    grammar_note = f"Translation: {pair['en']}"
    if pair.get("ref"):
        grammar_note += f"\nReference: {pair['ref']}"
    return _chat(SYSTEM_PROMPT, user, grammar_note)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def build_all_examples(
    bible_limit: int | None,
    parallel_limit: int | None,
    dict_limit: int | None,
) -> list[dict[str, Any]]:
    """Build all training examples from every source."""
    examples: list[dict[str, Any]] = []

    # --- Bible pairs: all 4 task types ---
    bible = load_bible(limit=bible_limit)
    for pair in bible:
        tr_en = build_translation_en_to_zo(pair)
        tr_zo = build_translation_zo_to_en(pair)
        if tr_en:
            examples.append(tr_en)
        if tr_zo:
            examples.append(tr_zo)
        gram = build_grammar_exercise(pair)
        if gram:
            examples.append(gram)
    print(f"  Bible: {len(bible)} pairs → {len(bible) * 3} examples")

    # --- Parallel pairs: translation + grammar ---
    parallel = load_parallel(limit=parallel_limit)
    for pair in parallel:
        tr_en = build_translation_en_to_zo(pair)
        tr_zo = build_translation_zo_to_en(pair)
        if tr_en:
            examples.append(tr_en)
        if tr_zo:
            examples.append(tr_zo)
        gram = build_grammar_exercise(pair)
        if gram:
            examples.append(gram)
    print(f"  Parallel: {len(parallel)} pairs → {len(parallel) * 3} examples")

    # --- Dictionary: vocabulary quiz ---
    dictionary = load_dictionary(limit=dict_limit)
    for entry in dictionary:
        quiz = build_vocabulary_quiz(entry)
        if quiz:
            examples.append(quiz)
    print(f"  Dictionary: {len(dictionary)} entries → {len(dictionary)} examples")

    return examples


def split_train_val(
    examples: list[dict[str, Any]],
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Randomly split into train and validation sets."""
    rng = random.Random(seed)
    indices = list(range(len(examples)))
    rng.shuffle(indices)
    split = int(len(examples) * (1.0 - val_ratio))
    train_idx = indices[:split]
    val_idx = indices[split:]
    train = [examples[i] for i in train_idx]
    val = [examples[i] for i in val_idx]
    return train, val


def write_jsonl(path: Path, data: list[dict[str, Any]]) -> None:
    """Write a list of dicts as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format Zolai data into Qwen3 chat template JSONL.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE / "data/training/qwen3_qlora",
        help="Directory to write train.jsonl and val.jsonl (default: data/training/qwen3_qlora/)",
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        help="Max pairs to load per data source (None = all)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Fraction of data for validation (default: 0.1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for train/val split (default: 42)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("=" * 60)
    print("Zolai Qwen3 QLoRA — Training Data Formatter")
    print("=" * 60)

    # Validate data files exist
    for name, path in DATA_PATHS.items():
        if not path.exists():
            print(f"ERROR: {name} data not found: {path}")
            raise SystemExit(1)

    # Build examples
    print("\nBuilding training examples...")
    examples = build_all_examples(
        bible_limit=args.max_pairs,
        parallel_limit=args.max_pairs,
        dict_limit=args.max_pairs,
    )
    print(f"\nTotal examples: {len(examples)}")

    if not examples:
        print("ERROR: No examples generated.")
        raise SystemExit(1)

    # Split
    train, val = split_train_val(examples, val_ratio=args.val_ratio, seed=args.seed)
    print(f"Train: {len(train)} | Val: {len(val)}")

    # Write
    train_path = args.output_dir / "train.jsonl"
    val_path = args.output_dir / "val.jsonl"
    write_jsonl(train_path, train)
    write_jsonl(val_path, val)

    print("\nWritten:")
    print(f"  {train_path} ({train_path.stat().st_size / 1024:.1f} KB)")
    print(f"  {val_path} ({val_path.stat().st_size / 1024:.1f} KB)")

    # Show a sample
    print("\n--- Sample (first training example) ---")
    print(json.dumps(train[0], ensure_ascii=False, indent=2)[:800])
    print("\nDone.")


if __name__ == "__main__":
    main()
