"""Publish datasets to the HuggingFace Hub.

Usage:
    python -m scripts.hf_publisher.hf_publisher --dataset zolai-parallel-zo-en
    python -m scripts.hf_publisher.hf_publisher --all
"""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi

from scripts.export_utils.config import DATASETS, get_hf_token

# ---------------------------------------------------------------------------
# Card generation
# ---------------------------------------------------------------------------

def generate_dataset_card(
    name: str,
    description: str,
    license: str,
    tags: list[str],
) -> str:
    """Return a README.md string with YAML front matter for the dataset card."""
    tag_list = "\n".join(f"  - {t}" for t in tags)
    return f"""---
language:
  - ctd
license: {license}
task_categories:
  - text-generation
  - text-classification
tags:
{tag_list}
---

# {name}

{description}
"""


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def publish_dataset(
    name: str,
    data_path: str,
    repo_id: str,
    token: str,
) -> str:
    """Create (or reuse) an HF repo and upload the dataset files.

    Parameters
    ----------
    name:
        Short human-readable dataset name.
    data_path:
        Path to the data file or directory to upload.
    repo_id:
        ``<org>/<dataset-name>`` on the Hub.
    token:
        HuggingFace API token.

    Returns
    -------
    str
        The URL of the published dataset.
    """
    api = HfApi(token=token)

    # Create repo if it doesn't exist (repo_type="dataset")
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)

    src = Path(data_path)
    if src.is_dir():
        # Upload entire directory contents
        api.upload_folder(
            folder_path=str(src),
            repo_id=repo_id,
            repo_type="dataset",
        )
    elif src.is_file():
        api.upload_file(
            path_or_fileobj=str(src),
            path_in_repo=src.name,
            repo_id=repo_id,
            repo_type="dataset",
        )
    else:
        raise FileNotFoundError(f"Data path does not exist: {data_path}")

    # Generate and upload dataset card
    meta = DATASETS.get(name, {})
    card_content = generate_dataset_card(
        name=name,
        description=meta.get("description", ""),
        license=meta.get("license", "cc-by-4.0"),
        tags=meta.get("tags", []),  # type: ignore[arg-type]
    )
    api.upload_file(
        path_or_fileobj=card_content.encode(),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
    )

    return f"https://huggingface.co/datasets/{repo_id}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish Zolai datasets to HuggingFace Hub.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        help="Publish a single dataset.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        dest="publish_all",
        help="Publish all registered datasets.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)
    token = get_hf_token()

    names = list(DATASETS.keys()) if args.publish_all else [args.dataset]

    for name in names:
        ds = DATASETS[name]
        print(f"Publishing {name} …")
        url = publish_dataset(
            name=name,
            data_path=str(ds["path"]),
            repo_id=str(ds["repo_id"]),
            token=token,
        )
        print(f"  → {url}")

    print("Done.")


if __name__ == "__main__":
    main()
