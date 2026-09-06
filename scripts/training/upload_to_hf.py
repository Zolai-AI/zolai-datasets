#!/usr/bin/env python3
"""Upload a Zolai fine-tuned model to HuggingFace Hub.

Creates a model card with Zolai language documentation, uploads model
weights, tokenizer, and LoRA adapter under the Zolai-AI organization.

Usage:
    python upload_to_hf.py --model-path ./zolai-qwen3-4b-lora --repo-name Zolai-AI/zolai-qwen3-4b
    HF_TOKEN=hf_xxx python upload_to_hf.py --model-path ./zolai-qwen3-4b --repo-name Zolai-AI/zolai-qwen3-4b
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ORG = "Zolai-AI"

MODEL_CARD_TEMPLATE = """---
language:
- en
- zom
- zolai
- tedim
tags:
- zolai
- tedim
- zomi
- low-resource
- qlora
- qwen3
- translation
- indigenous-language
license: mit
library_name: transformers
pipeline_tag: text-generation
base_model: {base_model}
---

# {model_name}

A QLoRA-fine-tuned {base_model} for **Tedim Zolai (ZVS 2018)** language tasks.

## Overview

This model was fine-tuned on parallel Zolai-English data using QLoRA
(Quantized Low-Rank Adaptation) on a Kaggle T4 GPU with the Unsloth library.

**Tasks:**
- English to Zolai translation
- Zolai to English translation
- Vocabulary quizzes and definitions
- Grammar analysis and exercises

## Language

**Tedim Zolai** (also written as Zomi, Zo) is a Tibeto-Burman language spoken
by the Zomi people of Myanmar and northeast India. This model follows the
**Zolai Vocabulary Standard (ZVS 2018)** orthography.

### Key Grammar Rules
- **Word order:** SOV (Subject-Object-Verb)
- **Question marker:** `hiam` (yes/no), `bang hang` / `kua` (content)
- **Negation:** 1st/2nd person `kei`, 3rd person `lo`
- **Ergative marker:** `in` for transitive subjects
- **Tense:** `-sak` (past), `-ah` (progressive), `-hen` (completive), `ding` (future)

### Forbidden Forms (ZVS 2018)
| Deprecated | ZVS 2018 | Meaning |
|-----------|----------|---------|
| pathian | pasian | God |
| ram | gam | earth |
| fapa | tapa | fire |
| bawipa | topa | lord |
| siangpahrang | kumpipa | angel |
| cu/cun | tua | (conjunction) |
| suah | chuak | (exit) |
| zalenna | suahtakna | (exceed) |
| nunnak | nuntakna | (knowledge) |

## Training Details

- **Base model:** {base_model}
- **Method:** QLoRA (4-bit NF4 quantization)
- **LoRA config:** r={lora_r}, alpha={lora_alpha}, dropout={lora_dropout}
- **Training:** {num_epochs} epochs, batch {batch_size}, lr {lr}
- **Hardware:** Kaggle T4 GPU (15GB VRAM)
- **Library:** Unsloth + transformers + peft

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Load base model + adapter
base_model = AutoModelForCausalLM.from_pretrained("{base_model}")
model = PeftModel.from_pretrained(base_model, "{hf_repo}")
tokenizer = AutoTokenizer.from_pretrained("{hf_repo}")

# Or merge first for faster inference
model = model.merge_and_unload()

# Translate English to Zolai
messages = [
    {{"role": "system", "content": "You are a Tedim Zolai language expert."}},
    {{"role": "user", "content": "Translate to Zolai: God created the heavens and the earth."}},
]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=128)
print(tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True))
# Expected: Pasian a vantung leh lebung piangsak hi.
```

## Data Sources

- **Bible parallel corpus:** 31,102 Zolai-English verse pairs (TDB77 / KJV)
- **Parallel sentences:** Zolai-English translation pairs
- **Dictionary:** Zolai-English dictionary entries
- All data follows ZVS 2018 orthography

## Evaluation

This model was evaluated on:
- Translation accuracy (human review by native speakers)
- ZVS 2018 orthographic compliance
- Grammar pattern adherence (SOV, negation, tense)

## Limitations

- Fine-tuned on limited parallel data (~30K pairs)
- May not handle complex code-switching
- Best for simple translation and vocabulary tasks
- Not suitable for long-form generation without context

## Citation

```bibtex
@misc{{zolai-qwen3-4b,
  title={{Zolai Qwen3-4B: A QLoRA-fine-tuned model for Tedim Zolai}},
  author={{Zolai-AI}},
  year={{2025}},
  url={{https://huggingface.co/{hf_repo}}}
}}
```

## License

MIT License. See [LICENSE](LICENSE) for details.
""".strip()


# ---------------------------------------------------------------------------
# Upload logic
# ---------------------------------------------------------------------------


def validate_model_path(model_path: Path) -> dict[str, str]:
    """Validate model path and detect its type.

    Returns:
        Dict with keys: type ('lora', 'merged', 'unknown'), base_model.
    """
    info: dict[str, str] = {"type": "unknown", "base_model": "Qwen/Qwen3-4B"}

    if not model_path.exists():
        raise FileNotFoundError(f"Model path not found: {model_path}")

    # Check for LoRA adapter
    adapter_config = model_path / "adapter_config.json"
    if adapter_config.exists():
        import json

        with open(adapter_config) as f:
            config = json.load(f)
        info["type"] = "lora"
        info["base_model"] = config.get("base_model_name_or_path", "Qwen/Qwen3-4B")
        info["lora_r"] = str(config.get("r", 16))
        info["lora_alpha"] = str(config.get("lora_alpha", 32))
        info["lora_dropout"] = str(config.get("lora_dropout", 0.05))
        return info

    # Check for merged model (has config.json but no adapter_config.json)
    config_json = model_path / "config.json"
    if config_json.exists():
        import json

        with open(config_json) as f:
            config = json.load(f)
        info["type"] = "merged"
        info["base_model"] = config.get(
            "_name_or_path",
            config.get("model_type", "Qwen/Qwen3-4B"),
        )
        return info

    raise ValueError(
        f"Cannot identify model type in {model_path}. "
        "Expected adapter_config.json (LoRA) or config.json (merged model)."
    )


def build_model_card(
    model_path: Path,
    hf_repo: str,
    model_info: dict[str, str],
) -> str:
    """Generate a model card from the template."""
    return MODEL_CARD_TEMPLATE.format(
        base_model=model_info.get("base_model", "Qwen/Qwen3-4B"),
        model_name=f"Zolai {model_info['base_model'].split('/')[-1]}",
        hf_repo=hf_repo,
        lora_r=model_info.get("lora_r", "16"),
        lora_alpha=model_info.get("lora_alpha", "32"),
        lora_dropout=model_info.get("lora_dropout", "0.05"),
        num_epochs="3",
        batch_size="16",
        lr="2e-4",
    )


def upload_to_hf(
    model_path: Path,
    repo_name: str,
    hf_token: str | None = None,
    private: bool = False,
    commit_message: str | None = None,
) -> str:
    """Upload model to HuggingFace Hub.

    Args:
        model_path: Path to the model directory.
        repo_name: Repository name (org/repo format).
        hf_token: HuggingFace API token. Falls back to HF_TOKEN env var.
        private: Whether to create a private repository.
        commit_message: Custom commit message.

    Returns:
        URL of the uploaded model.
    """
    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError as exc:
        print("ERROR: huggingface_hub is required. Install with:")
        print("  pip install huggingface_hub")
        raise SystemExit(1) from exc

    token = hf_token or os.environ.get("HF_TOKEN")
    if not token:
        print("ERROR: No HuggingFace token provided.")
        print("  Set HF_TOKEN environment variable or use --hf-token argument.")
        print("  Get a token at: https://huggingface.co/settings/tokens")
        raise SystemExit(1)

    api = HfApi(token=token)
    model_path = Path(model_path)

    # Validate model
    model_info = validate_model_path(model_path)
    print(f"Model type: {model_info['type']}")
    print(f"Base model: {model_info['base_model']}")

    # Create or get repo
    print(f"\nCreating/accessing repo: {repo_name}")
    try:
        repo_url = create_repo(
            repo_id=repo_name,
            token=token,
            private=private,
            exist_ok=True,
            repo_type="model",
        )
        print(f"  Repo URL: {repo_url}")
    except Exception as exc:
        print(f"  WARNING: Could not create repo: {exc}")
        print("  Attempting to upload to existing repo...")

    # Generate model card
    model_card = build_model_card(model_path, repo_name, model_info)

    # Determine commit message
    if not commit_message:
        if model_info["type"] == "lora":
            commit_message = "feat: add Zolai QLoRA adapter"
        else:
            commit_message = "feat: add Zolai merged model"

    # Upload files
    print(f"\nUploading files from {model_path}...")

    # Write model card to temp file
    readme_path = model_path / "README.md"
    readme_path.write_text(model_card)
    print(f"  Generated README.md ({len(model_card)} chars)")

    # Upload all files
    api.upload_folder(
        folder_path=str(model_path),
        repo_id=repo_name,
        commit_message=commit_message,
        token=token,
    )

    # Count uploaded files
    uploaded = list(model_path.glob("*"))
    total_size = sum(f.stat().st_size for f in uploaded if f.is_file())
    print(f"\nUploaded {len(uploaded)} files ({total_size / (1024**2):.1f} MB)")
    for f in sorted(uploaded):
        if f.is_file():
            size = f.stat().st_size
            print(f"  {f.name}: {size / (1024**2):.1f} MB")

    model_url = f"https://huggingface.co/{repo_name}"
    print(f"\nModel available at: {model_url}")

    # Clean up generated README if it wasn't there before
    # (Keep it - it's useful for the repo)

    return model_url


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload Zolai fine-tuned model to HuggingFace Hub.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        required=True,
        help="Path to the model directory (LoRA adapter or merged model).",
    )
    parser.add_argument(
        "--repo-name",
        type=str,
        default=f"{DEFAULT_ORG}/zolai-qwen3-4b",
        help=f"HuggingFace repo name in org/repo format (default: {DEFAULT_ORG}/zolai-qwen3-4b).",
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="HuggingFace API token. Falls back to HF_TOKEN env var.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=False,
        help="Create a private repository.",
    )
    parser.add_argument(
        "--commit-message",
        type=str,
        default=None,
        help="Custom commit message.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("Zolai Model — HuggingFace Upload")
    print("=" * 60)

    url = upload_to_hf(
        model_path=args.model_path,
        repo_name=args.repo_name,
        hf_token=args.hf_token,
        private=args.private,
        commit_message=args.commit_message,
    )

    print(f"\nDone! Model at: {url}")


if __name__ == "__main__":
    main()
