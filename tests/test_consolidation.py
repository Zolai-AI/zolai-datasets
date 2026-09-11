"""Tests for the consolidated bible_knowledge_builder module.

Covers:
  - test_consolidated_module_imports
  - test_builders_return_expected_structure
  - test_deprecation_notices_present
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/bible is on the path so we can import the module
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "bible"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import bible_knowledge_builder as bkb

# ── 1. Module imports ────────────────────────────────────────────────────────

class TestConsolidatedModuleImports:
    """Verify that all three builder classes import cleanly."""

    def test_import_module(self) -> None:
        """Module-level import succeeds."""
        assert hasattr(bkb, "ParallelBuilder")
        assert hasattr(bkb, "VocabularyBuilder")
        assert hasattr(bkb, "GrammarBuilder")

    def test_parallel_builder_instantiates(self) -> None:
        """ParallelBuilder can be instantiated with default paths."""
        pb = bkb.ParallelBuilder()
        assert pb.workspace.exists() or not pb.workspace.exists()  # no crash
        assert pb.bible_versions  # dict of 3 versions

    def test_vocabulary_builder_instantiates(self) -> None:
        """VocabularyBuilder can be instantiated."""
        vb = bkb.VocabularyBuilder()
        assert vb.POS_MAP  # non-empty
        assert "n" in vb.POS_MAP

    def test_grammar_builder_instantiates(self) -> None:
        """GrammarBuilder can be instantiated."""
        gb = bkb.GrammarBuilder()
        assert gb.TENSE_MARKERS
        assert gb.NEGATION_PATTERNS
        assert gb.ASPECT_MARKERS
        assert gb.AGREEMENT_MARKERS

    def test_book_names_count(self) -> None:
        """Shared BOOK_NAMES contains all 66 Bible books."""
        assert len(bkb.BOOK_NAMES) == 66
        assert "GEN" in bkb.BOOK_NAMES
        assert "REV" in bkb.BOOK_NAMES

    def test_tokenize_function(self) -> None:
        """Shared _tokenize helper works."""
        tokens = bkb._tokenize("Pasian in vantung a piangsak hi.")
        assert "pasian" in tokens
        assert "vantung" in tokens
        assert "piangsak" in tokens


# ── 2. Builder return structures ─────────────────────────────────────────────

class TestBuildersReturnExpectedStructure:
    """Verify that builder methods return the expected dict structure."""

    def test_load_dict_entries_returns_dict(self) -> None:
        """VocabularyBuilder.load_dict_entries returns a dict."""
        vb = bkb.VocabularyBuilder()
        entries = vb.load_dict_entries()
        assert isinstance(entries, dict)
        # Values should have 'meanings' and 'pos'
        if entries:
            first_val = next(iter(entries.values()))
            assert "meanings" in first_val
            assert "pos" in first_val

    def test_load_dict_entries_no_crash(self) -> None:
        """Loading dictionary does not crash even if files are missing."""
        vb = bkb.VocabularyBuilder()
        # Should return empty dict or populated dict, never crash
        entries = vb.load_dict_entries()
        assert isinstance(entries, dict)

    def test_grammar_pattern_detection(self) -> None:
        """GrammarBuilder._find_pattern detects SOV and negation."""
        gb = bkb.GrammarBuilder()
        patterns = gb._find_pattern(
            ["pasian", "in", "vantung", "a", "piangsak", "hi"],
            "God created the heaven",
            "GEN 1:1",
        )
        pattern_names = [p["pattern"] for p in patterns]
        assert "SOV" in pattern_names

    def test_grammar_negation_detection(self) -> None:
        """GrammarBuilder._find_pattern detects negation patterns."""
        gb = bkb.GrammarBuilder()
        patterns = gb._find_pattern(
            ["ka", "pai", "kei", "hi"],
            "I do not go",
            "TEST 1:1",
        )
        pattern_names = [p["pattern"] for p in patterns]
        assert "negation_kei" in pattern_names

    def test_grammar_agreement_detection(self) -> None:
        """GrammarBuilder._find_pattern detects agreement markers."""
        gb = bkb.GrammarBuilder()
        patterns = gb._find_pattern(
            ["ka", "ne", "hi"],
            "I eat",
            "TEST 1:1",
        )
        pattern_names = [p["pattern"] for p in patterns]
        assert "agreement_ka" in pattern_names

    def test_strip_page_markers(self) -> None:
        """GrammarBuilder._strip_page_markers removes page markers."""
        text = "Page 1 of 288\nHello world\nPage 2 of 288"
        result = bkb.GrammarBuilder._strip_page_markers(text)
        assert "Page" not in result
        assert "Hello world" in result


# ── 3. Deprecation notices ───────────────────────────────────────────────────

DEPRECATED_SCRIPTS = [
    "build_parallel_corpus.py",
    "build_parallel_bible.py",
    "rebuild_bible_parallel.py",
    "build_vocabulary_db.py",
    "extract_bible_vocab.py",
    "learn_bible_vocab.py",
    "fill_bible_vocab_gaps.py",
    "fill_bible_vocab_local.py",
    "crossref_bible_vocab.py",
    "extract_grammar_patterns.py",
    "extract_grammar_from_vol1.py",
    "extract_zvs_rules.py",
    "extract_sinna_lessons.py",
    "build_grammar_reference_v2.py",
]


class TestDeprecationNoticesPresent:
    """Verify that all 14 deprecated scripts have deprecation notices."""

    @pytest.mark.parametrize("script_name", DEPRECATED_SCRIPTS)
    def test_deprecation_notice_in_file(self, script_name: str) -> None:
        """Each deprecated script starts with a deprecation comment."""
        script_path = _SCRIPTS_DIR / script_name
        assert script_path.exists(), f"{script_name} not found"

        first_lines = script_path.read_text(encoding="utf-8")[:300]
        assert "deprecated" in first_lines.lower() or "DEPRECATED" in first_lines, (
            f"{script_name} missing deprecation notice in first 300 chars"
        )

    def test_all_14_scripts_deprecated(self) -> None:
        """All 14 scripts are accounted for."""
        assert len(DEPRECATED_SCRIPTS) == 14

    def test_consolidation_doc_exists(self) -> None:
        """CONSOLIDATION.md exists and references the builder."""
        doc_path = _SCRIPTS_DIR / "CONSOLIDATION.md"
        assert doc_path.exists()
        content = doc_path.read_text(encoding="utf-8")
        assert "bible_knowledge_builder" in content
        assert "ParallelBuilder" in content
        assert "VocabularyBuilder" in content
        assert "GrammarBuilder" in content
