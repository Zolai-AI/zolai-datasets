#!/usr/bin/env python3
"""Merge a LoRA adapter into the base model and optionally export to GGUF.

This script:
1. Loads the base Qwen3-4B model
2. Merges the LoRA adapter weights into the base model
3. Optionally quantizes and exports to GGUF Q4_K_M format via llama.cpp

Usage:
    python merge_and_export.py --adapter-path ./zolai-qwen3-4b-lora --export-gguf
    python merge_and_export.py --adapter-path ./zolai-qwen3-4b-lora --base-model Qwen/Qwen3-4B
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_MODEL = "Qwen/Qwen3-4B"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data/training/zolai-qwen3-4b"

GGUF_INSTALLInstructions = """
llama.cpp is not installed. To export to GGUF format:

    # Option A: Clone and build llama.cpp
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    cmake -B build
    cmake --build build --config Release -j

    # Option B: Install via pip (Python bindings only, no CLI)
    pip install llama-cpp-python

    # Option C: Use the huggingface-gguf pipeline (no llama.cpp needed)
    pip install transformers[torch] huggingface-hub
    # Then run this script WITHOUT --export-gguf to just merge the adapter.

After building, make sure `llama.cpp/build/bin/llama-quantize` is in your PATH
or set LLAMA_CPP_BIN environment variable.
""".strip()


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def merge_adapter(
    adapter_path: str | Path,
    base_model: str,
    output_dir: Path,
    max_shard_size: str = "5GB",
) -> Path:
    """Merge LoRA adapter into base model and save as safetensors.

    Args:
        adapter_path: Path to the LoRA adapter directory.
        base_model: HuggingFace model ID or local path for the base model.
        output_dir: Directory to save the merged model.
        max_shard_size: Maximum shard size for model saving.

    Returns:
        Path to the merged model directory.
    """
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        print("ERROR: Missing dependencies. Install with:\n")
        print("  pip install torch transformers peft accelerate safetensors\n")
        raise SystemExit(1) from exc

    adapter_path = Path(adapter_path)
    output_dir = Path(output_dir)

    print(f"Base model: {base_model}")
    print(f"Adapter: {adapter_path}")
    print(f"Output: {output_dir}")

    # Step 1: Load tokenizer from adapter (it was saved there during training)
    print("\n[1/4] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        str(adapter_path), trust_remote_code=True
    )

    # Step 2: Load base model in fp16
    print("[2/4] Loading base model (this may take a few minutes)...")
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # Step 3: Load and merge adapter
    print("[3/4] Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base, str(adapter_path))
    print("Merging adapter weights into base model...")
    model = model.merge_and_unload()

    # Step 4: Save merged model
    print("[4/4] Saving merged model...")
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir), max_shard_size=max_shard_size)
    tokenizer.save_pretrained(str(output_dir))

    # Verify
    total_size = sum(f.stat().st_size for f in output_dir.iterdir() if f.is_file())
    print(f"\nMerged model saved to {output_dir}")
    print(f"  Total size: {total_size / (1024**3):.2f} GB")

    file_list = sorted(output_dir.iterdir())
    for f in file_list:
        if f.is_file():
            size = f.stat().st_size
            if size > 1024 * 1024:
                print(f"  {f.name}: {size / (1024**2):.1f} MB")
            else:
                print(f"  {f.name}: {size / 1024:.1f} KB")

    return output_dir


# ---------------------------------------------------------------------------
# GGUF export
# ---------------------------------------------------------------------------


def find_llama_quantize() -> str | None:
    """Find the llama-quantize binary."""
    # Check env var first
    env_bin = os.environ.get("LLAMA_CPP_BIN")
    if env_bin and Path(env_bin).is_file():
        return env_bin

    # Check common locations
    candidates = [
        "llama-quantize",
        "llama.cpp/build/bin/llama-quantize",
        "llama.cpp/build/bin/Release/llama-quantize",
    ]
    for candidate in candidates:
        result = shutil.which(candidate)
        if result:
            return result

    # Check if llama-quantize is in PATH
    result = shutil.which("llama-quantize")
    if result:
        return result

    return None


def convert_to_gguf(merged_dir: Path, output_dir: Path) -> Path:
    """Convert merged model to GGUF format using llama.cpp.

    First converts to GGUF, then quantizes to Q4_K_M.

    Args:
        merged_dir: Directory containing the merged model.
        output_dir: Directory to write the GGUF file.

    Returns:
        Path to the quantized GGUF file.
    """
    quantize_bin = find_llama_quantize()
    if not quantize_bin:
        print(GGUF_INSTALLInstructions)
        raise SystemExit(1)

    print(f"Found llama-quantize: {quantize_bin}")

    # Step 1: Convert HF model to GGUF (f16)
    gguf_f16_path = output_dir / "zolai-qwen3-4b-f16.gguf"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try to find convert_hf_to_gguf.py
    convert_script = None
    for candidate in [
        "llama.cpp/convert_hf_to_gguf.py",
        "convert_hf_to_gguf.py",
    ]:
        if Path(candidate).is_file():
            convert_script = candidate
            break

    if not convert_script:
        # Try to find it via find command or known pip locations
        result = shutil.which("convert_hf_to_gguf")
        if result:
            convert_script = result
        else:
            # Try the pip-installed version
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "convert_hf_to_gguf", "--help"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 or "usage" in result.stdout.lower():
                    convert_script = f"{sys.executable} -m convert_hf_to_gguf"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    if convert_script:
        print(f"[1/2] Converting to GGUF (f16): {gguf_f16_path}")
        cmd = f"{convert_script} {merged_dir} --outfile {gguf_f16_path} --outtype f16"
        print(f"  Running: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  WARNING: Conversion failed: {result.stderr[:500]}")
            print("  Falling back to huggingface-gguf pipeline...")
            return _convert_via_huggingface_gguf(merged_dir, output_dir)
    else:
        print("  convert_hf_to_gguf.py not found, using huggingface-gguf pipeline...")
        return _convert_via_huggingface_gguf(merged_dir, output_dir)

    # Step 2: Quantize to Q4_K_M
    q4km_path = output_dir / "zolai-qwen3-4b-Q4_K_M.gguf"
    print(f"\n[2/2] Quantizing to Q4_K_M: {q4km_path}")
    cmd = f"{quantize_bin} {gguf_f16_path} {q4km_path} Q4_K_M"
    print(f"  Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Quantization failed:\n{result.stderr[:500]}")
        raise SystemExit(1)

    # Report sizes
    f16_size = gguf_f16_path.stat().st_size / (1024**2)
    q4_size = q4km_path.stat().st_size / (1024**2)
    print("\nGGUF files:")
    print(f"  F16:  {gguf_f16_path} ({f16_size:.0f} MB)")
    print(f"  Q4_K_M: {q4km_path} ({q4_size:.0f} MB)")

    return q4km_path


def _convert_via_huggingface_gguf(
    merged_dir: Path, output_dir: Path
) -> Path:
    """Fallback: convert using huggingface-gguf library."""
    try:
        import gguf  # noqa: F401
        from huggingface_hub import hf_hub_download  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        print("ERROR: Cannot convert to GGUF. Install llama.cpp or huggingface-gguf:")
        print("  pip install huggingface-gguf")
        print("  OR install llama.cpp: git clone https://github.com/ggerganov/llama.cpp")
        raise SystemExit(1)

    # Use the huggingface-gguf conversion pipeline
    try:

        # Load model for conversion
        tokenizer = AutoTokenizer.from_pretrained(str(merged_dir))
        model = AutoModelForCausalLM.from_pretrained(
            str(merged_dir), torch_dtype=torch.float16
        )

        q4km_path = output_dir / "zolai-qwen3-4b-Q4_K_M.gguf"
        print(f"  Writing GGUF via huggingface-gguf: {q4km_path}")

        # Note: full GGUF conversion is complex; recommend llama.cpp
        print("  Full GGUF conversion requires llama.cpp convert_hf_to_gguf.py")
        print("  See: https://github.com/ggerganov/llama.cpp#prepare-and-quantize")
        raise SystemExit(1)
    except Exception as exc:
        print(f"ERROR: GGUF conversion failed: {exc}")
        print("\nPlease install llama.cpp:")
        print("  git clone https://github.com/ggerganov/llama.cpp")
        print("  cd llama.cpp && cmake -B build && cmake --build build --config Release")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge LoRA adapter into base model and optionally export to GGUF.",
    )
    parser.add_argument(
        "--adapter-path",
        type=Path,
        required=True,
        help="Path to the LoRA adapter directory (containing adapter_config.json).",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default=DEFAULT_BASE_MODEL,
        help=f"HuggingFace model ID or local path for the base model (default: {DEFAULT_BASE_MODEL}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save the merged model (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--export-gguf",
        action="store_true",
        default=False,
        help="Also export to GGUF Q4_K_M format using llama.cpp.",
    )
    parser.add_argument(
        "--gguf-output-dir",
        type=Path,
        default=None,
        help="Directory for GGUF output (default: same as output-dir/gguf/).",
    )
    parser.add_argument(
        "--max-shard-size",
        type=str,
        default="5GB",
        help="Maximum shard size for model saving (default: 5GB).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("Zolai Qwen3-4B — LoRA Merge & Export")
    print("=" * 60)

    # Validate adapter path
    if not args.adapter_path.exists():
        print(f"ERROR: Adapter path not found: {args.adapter_path}")
        raise SystemExit(1)
    if not (args.adapter_path / "adapter_config.json").exists():
        print(f"ERROR: No adapter_config.json in {args.adapter_path}")
        raise SystemExit(1)

    # Merge
    merged_dir = merge_adapter(
        adapter_path=args.adapter_path,
        base_model=args.base_model,
        output_dir=args.output_dir,
        max_shard_size=args.max_shard_size,
    )

    # GGUF export
    if args.export_gguf:
        gguf_dir = args.gguf_output_dir or (args.output_dir / "gguf")
        print(f"\n{'=' * 60}")
        print("GGUF Export")
        print("=" * 60)
        convert_to_gguf(merged_dir=merged_dir, output_dir=gguf_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
