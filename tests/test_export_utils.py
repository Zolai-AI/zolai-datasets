"""Tests for export utility modules (config, hf_publisher, kaggle_publisher)."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from scripts.export_utils.config import (
    DATASETS,
    get_hf_token,
    get_kaggle_token,
)
from scripts.hf_publisher.hf_publisher import generate_dataset_card
from scripts.kaggle_publisher.kaggle_publisher import generate_metadata_json

# ---------------------------------------------------------------------------
# config.py — DATASETS registry
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {
    "zolai-parallel-zo-en",
    "zolai-dictionary",
    "zolai-training-master",
    "zolai-bible-corpus",
}

REQUIRED_FIELDS = {"path", "repo_id", "description", "license", "tags"}


class TestDatasetsRegistry:
    def test_has_all_expected_keys(self) -> None:
        assert set(DATASETS.keys()) == EXPECTED_KEYS

    def test_each_dataset_has_required_fields(self) -> None:
        for name, meta in DATASETS.items():
            missing = REQUIRED_FIELDS - set(meta.keys())
            assert not missing, f"{name} missing fields: {missing}"

    def test_repo_ids_are_valid_format(self) -> None:
        for name, meta in DATASETS.items():
            repo_id = str(meta["repo_id"])
            assert "/" in repo_id, f"{name}: repo_id must be org/name"
            assert repo_id.startswith("Zolai-AI/"), f"{name}: wrong org prefix"

    def test_tags_are_lists(self) -> None:
        for name, meta in DATASETS.items():
            tags = meta["tags"]
            assert isinstance(tags, list), f"{name}: tags must be a list"
            assert len(tags) > 0, f"{name}: tags must not be empty"

    def test_licenses_are_valid(self) -> None:
        valid = {"cc-by-4.0", "cc-by-sa-4.0", "mit"}
        for name, meta in DATASETS.items():
            lic = str(meta["license"])
            assert lic in valid, f"{name}: unexpected license '{lic}'"


# ---------------------------------------------------------------------------
# config.py — get_hf_token / get_kaggle_token
# ---------------------------------------------------------------------------


class TestGetTokens:
    def test_get_hf_token_returns_env_value(self) -> None:
        with patch.dict(os.environ, {"HF_TOKEN": "fake-token-123"}):
            assert get_hf_token() == "fake-token-123"

    def test_get_hf_token_raises_when_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(
            RuntimeError, match="HF_TOKEN"
        ):
            get_hf_token()

    def test_get_kaggle_token_returns_env_value(self) -> None:
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "kaggle-456"}):
            assert get_kaggle_token() == "kaggle-456"

    def test_get_kaggle_token_raises_when_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(
            RuntimeError, match="KAGGLE_API_TOKEN"
        ):
            get_kaggle_token()


# ---------------------------------------------------------------------------
# hf_publisher.py — generate_dataset_card
# ---------------------------------------------------------------------------


class TestGenerateDatasetCard:
    def test_returns_string_with_yaml_front_matter(self) -> None:
        card = generate_dataset_card(
            name="test-dataset",
            description="A test dataset.",
            license="cc-by-4.0",
            tags=["zomi", "nlp"],
        )
        assert isinstance(card, str)
        assert card.startswith("---\n")
        # YAML front matter closes
        parts = card.split("---")
        assert len(parts) >= 3, "Card must have YAML front matter between --- delimiters"

    def test_includes_name_in_heading(self) -> None:
        card = generate_dataset_card(
            name="my-ds",
            description="desc",
            license="cc-by-4.0",
            tags=[],
        )
        assert "# my-ds" in card

    def test_includes_description(self) -> None:
        card = generate_dataset_card(
            name="ds",
            description="Important bilingual corpus.",
            license="cc-by-4.0",
            tags=[],
        )
        assert "Important bilingual corpus." in card

    def test_includes_license_in_yaml(self) -> None:
        card = generate_dataset_card(
            name="ds",
            description="desc",
            license="cc-by-4.0",
            tags=[],
        )
        front_matter = card.split("---")[1]
        assert "license: cc-by-4.0" in front_matter

    def test_includes_tags_in_yaml(self) -> None:
        card = generate_dataset_card(
            name="ds",
            description="desc",
            license="cc-by-4.0",
            tags=["zomi", "tedim"],
        )
        front_matter = card.split("---")[1]
        assert "zomi" in front_matter
        assert "tedim" in front_matter

    def test_empty_tags_produces_valid_card(self) -> None:
        card = generate_dataset_card(
            name="ds",
            description="desc",
            license="cc-by-4.0",
            tags=[],
        )
        assert "---" in card


# ---------------------------------------------------------------------------
# kaggle_publisher.py — generate_metadata_json
# ---------------------------------------------------------------------------


class TestGenerateMetadataJson:
    def test_returns_valid_json(self) -> None:
        result = generate_metadata_json(
            name="test-ds",
            description="Test",
            license="cc-by-4.0",
            tags=["zomi"],
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_required_fields(self) -> None:
        result = generate_metadata_json(
            name="my-dataset",
            description="A dataset.",
            license="cc-by-4.0",
            tags=["nlp"],
        )
        parsed = json.loads(result)
        for key in ("title", "description", "id", "licenses", "keywords"):
            assert key in parsed, f"Missing required field: {key}"

    def test_id_uses_org_prefix(self) -> None:
        result = generate_metadata_json(
            name="zolai-dict",
            description="dict",
            license="cc-by-4.0",
            tags=[],
        )
        parsed = json.loads(result)
        assert parsed["id"].startswith("zolai/")

    def test_licenses_format(self) -> None:
        result = generate_metadata_json(
            name="ds",
            description="desc",
            license="cc-by-4.0",
            tags=[],
        )
        parsed = json.loads(result)
        assert isinstance(parsed["licenses"], list)
        assert parsed["licenses"][0]["name"] == "cc-by-4.0"

    def test_keywords_match_tags(self) -> None:
        tags = ["zomi", "bible", "corpus"]
        result = generate_metadata_json(
            name="ds",
            description="desc",
            license="cc-by-4.0",
            tags=tags,
        )
        parsed = json.loads(result)
        assert parsed["keywords"] == tags

    def test_title_matches_name(self) -> None:
        result = generate_metadata_json(
            name="bilingual-corpus",
            description="desc",
            license="cc-by-4.0",
            tags=[],
        )
        parsed = json.loads(result)
        assert parsed["title"] == "bilingual-corpus"
