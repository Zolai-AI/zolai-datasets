"""Publish datasets to Kaggle via the ``kaggle`` CLI.

Usage:
    python -m scripts.kaggle_publisher.kaggle_publisher --dataset zolai-parallel-zo-en
    python -m scripts.kaggle_publisher.kaggle_publisher --all
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.export_utils.config import DATASETS, get_kaggle_token

# Default Kaggle slug prefix (org)
_KAGGLE_ORG = "zolai"


# ---------------------------------------------------------------------------
# Metadata generation
# ---------------------------------------------------------------------------

def generate_metadata_json(
    name: str,
    description: str,
    license: str,
    tags: list[str],
) -> str:
    """Return the JSON string for dataset-metadata.json."""
    meta = {
        "title": name,
        "description": description,
        "id": f"{_KAGGLE_ORG}/{name}",
        "licenses": [{"name": license}],
        "keywords": tags,
    }
    return json.dumps(meta, indent=2)


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def publish_dataset(
    name: str,
    data_path: str,
    kaggle_slug: str,
    token: str,
) -> str:
    """Create or update a Kaggle dataset.

    Parameters
    ----------
    name:
        Short human-readable dataset name.
    data_path:
        Path to the data file or directory to upload.
    kaggle_slug:
        Kaggle dataset slug (``<owner>/<dataset-name>``).
    token:
        Kaggle API token.

    Returns
    -------
    str
        The URL of the published dataset.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        src = Path(data_path)
        if src.is_dir():
            # Copy directory contents into staging area
            dest = tmp / "data"
            shutil.copytree(str(src), str(dest))
        elif src.is_file():
            dest = tmp / "data"
            dest.mkdir()
            shutil.copy2(str(src), str(dest / src.name))
        else:
            raise FileNotFoundError(f"Data path does not exist: {data_path}")

        # Generate metadata
        meta = DATASETS.get(name, {})
        metadata_content = generate_metadata_json(
            name=name,
            description=meta.get("description", ""),
            license=meta.get("license", "cc-by-4.0"),
            tags=meta.get("tags", []),  # type: ignore[arg-type]
        )
        (tmp / "dataset-metadata.json").write_text(metadata_content)

        # Set Kaggle credentials via env
        env = os.environ.copy()
        env["KAGGLE_USERNAME"] = _KAGGLE_ORG
        env["KAGGLE_KEY"] = token

        # Create / update the dataset
        subprocess.run(
            ["kaggle", "datasets", "init", "-p", str(tmp)],
            check=True,
            env=env,
        )
        subprocess.run(
            ["kaggle", "datasets", "create", "-p", str(tmp), "--dir-mode", "zip"],
            check=True,
            env=env,
        )

    return f"https://www.kaggle.com/datasets/{kaggle_slug}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish Zolai datasets to Kaggle.",
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
    token = get_kaggle_token()

    names = list(DATASETS.keys()) if args.publish_all else [args.dataset]

    for name in names:
        ds = DATASETS[name]
        slug = str(ds["repo_id"]).replace("Zolai-AI/", f"{_KAGGLE_ORG}/")
        print(f"Publishing {name} to Kaggle …")
        url = publish_dataset(
            name=name,
            data_path=str(ds["path"]),
            kaggle_slug=slug,
            token=token,
        )
        print(f"  → {url}")

    print("Done.")


if __name__ == "__main__":
    main()
