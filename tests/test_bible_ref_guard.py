"""Verse-ref guard: bible_knowledge_builder must never emit an impossible ref.

Spec: ``docs/planning/BIBLE_REF_FIX_PLAN.md`` (workspace-root repo) —
``build_from_markdown`` validates every parsed reference against the committed
KJV verse-count table (``scripts/bible/verse_counts.py``, mirror of zolai-core's
``zolai/data/verse_counts.py``) and refuses the build when one is impossible.

Historical bug reproduced here: a ``## Chapter N`` header is applied *before*
the pending last verse of chapter N-1 is flushed, so ``**1:31**`` followed by
``## Chapter 2`` is emitted as ``GEN 2:31`` — a verse that exists in no edition.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BIBLE_SCRIPTS = REPO / "scripts" / "bible"
GUARD = BIBLE_SCRIPTS / "verse_counts.py"
BUILDER = BIBLE_SCRIPTS / "bible_knowledge_builder.py"

_MD_HEADER = """## Chapter {chapter}
**{chapter}:{verse}**
TDB77: {zo}
KJV: {en}
"""


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verse_counts = _load("datasets_verse_counts", GUARD)
bible_knowledge_builder = _load("datasets_bible_knowledge_builder", BUILDER)


# ---------------------------------------------------------------------------
# The embedded table
# ---------------------------------------------------------------------------


class TestVerseCountTable:
    def test_shape_and_total(self) -> None:
        assert len(verse_counts.BOOK_ORDER) == 66
        assert set(verse_counts.VERSE_COUNTS) == set(verse_counts.BOOK_ORDER)
        assert sum(sum(v) for v in verse_counts.VERSE_COUNTS.values()) == 31102
        assert verse_counts.TOTAL_VERSES == 31102

    @pytest.mark.parametrize(
        "ref,expected",
        [
            ("GEN 1:1", True),
            ("GEN 1:31", True),
            ("GEN 2:31", False),   # chapter-final re-label (the 547-bug)
            ("GEN 1:32", False),
            ("1CH 19:19", True),
            ("1CH 19:20", False),
            ("1CH 18:20", False),  # 1 Chronicles 18 has 17 verses
            ("1CO 16:58", False),
            ("3JN 1:14", True),
            ("3JN 1:15", False),
            ("JOL 3:21", True),
            ("JOL 4:12", False),
            ("NOTABOOK 1:1", False),
            ("", False),
            (None, False),
        ],
    )
    def test_is_valid_ref(self, ref, expected) -> None:
        assert verse_counts.is_valid_ref(ref) is expected

    @pytest.mark.parametrize("path", [GUARD, BUILDER])
    def test_scripts_compile(self, path: Path) -> None:
        compiled = subprocess.run(
            [sys.executable, "-c",
             f"import py_compile; py_compile.compile('{path}', doraise=True)"],
            capture_output=True, text=True, check=False,
        )
        assert compiled.returncode == 0, compiled.stderr

    def test_guard_file_passes_ruff(self) -> None:
        # Only the new file is gated: bible_knowledge_builder.py carries 5
        # pre-existing RUF012 hits in unrelated builder classes (HEAD = same 5).
        ruff = shutil.which("ruff")
        if not ruff:
            pytest.skip("ruff not installed")
        lint = subprocess.run([ruff, "check", str(GUARD)],
                              capture_output=True, text=True, check=False)
        assert lint.returncode == 0, lint.stdout


# ---------------------------------------------------------------------------
# build_from_markdown refuses impossible refs
# ---------------------------------------------------------------------------


def _write_corpus(workspace: Path, md_body: str) -> Path:
    corpus = workspace / "data" / "corpus" / "bible" / "markdown" / "Parallel_Corpus" / "Tedim_Chin"
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / "GEN_Tedim_Chin_Parallel.md").write_text(md_body, encoding="utf-8")
    return workspace / "data" / "bible" / "parallel_corpus_v1.jsonl"


def _build(workspace: Path):
    builder = bible_knowledge_builder.ParallelBuilder(workspace=workspace)
    return builder.build_from_markdown()


class TestBuildFromMarkdownGuard:
    def test_refuses_impossible_ref_and_writes_nothing(self, tmp_path: Path, capsys) -> None:
        # chapter-final verse re-labeled: pending GEN 1:31 flushed after the
        # "## Chapter 2" header → emitted as GEN 2:31 (impossible).
        body = (
            _MD_HEADER.format(chapter=1, verse=31, zo="A khatpik nek ding hi.",
                              en="And Adam lived an hundred and thirty years.")
            + _MD_HEADER.format(chapter=2, verse=1, zo="Dup row.",
                                en="This is the book of the generations of Adam.")
        )
        output = _write_corpus(tmp_path, body)

        stats = _build(tmp_path)

        assert stats == {"error": 1, "invalid_refs": 1}
        captured = capsys.readouterr()
        assert "impossible verse ref" in captured.err
        assert "GEN 2:31" in captured.err
        assert not output.exists(), "refusal must leave no partial output"

    def test_valid_corpus_builds(self, tmp_path: Path) -> None:
        body = _MD_HEADER.format(chapter=1, verse=1,
                                 zo="Pasian in vantung leh leitung a piangsak hi.",
                                 en="In the beginning God created the heaven and the earth.")
        output = _write_corpus(tmp_path, body)

        stats = _build(tmp_path)

        assert stats == {"books": 1, "verses": 1, "complete": 1, "partial": 0}
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        assert [r["ref"] for r in rows] == ["GEN 1:1"]
        assert all(verse_counts.is_valid_ref(r["ref"]) for r in rows)

    def test_unknown_book_code_is_also_refused(self, tmp_path: Path, capsys) -> None:
        """A file whose book code is not one of the canonical 66 must not slip through."""
        corpus = (
            tmp_path / "data" / "corpus" / "bible" / "markdown"
            / "Parallel_Corpus" / "Tedim_Chin"
        )
        corpus.mkdir(parents=True, exist_ok=True)
        (corpus / "XYZ_book.md").write_text(
            _MD_HEADER.format(chapter=1, verse=1, zo="x", en="y"), encoding="utf-8"
        )
        output = tmp_path / "data" / "bible" / "parallel_corpus_v1.jsonl"

        stats = _build(tmp_path)

        assert stats == {"error": 1, "invalid_refs": 1}
        assert "XYZ_book.md: XYZ 1:1" in capsys.readouterr().err
        assert not output.exists()

    def test_build_all_propagates_guard_error(self, tmp_path: Path, capsys) -> None:
        body = (
            _MD_HEADER.format(chapter=1, verse=31, zo="z", en="e")
            + _MD_HEADER.format(chapter=2, verse=1, zo="z", en="e")
        )
        _write_corpus(tmp_path, body)
        builder = bible_knowledge_builder.ParallelBuilder(workspace=tmp_path)

        stats = builder.build_all()

        assert stats == {"error": 1, "invalid_refs": 1}
        assert "impossible verse ref" in capsys.readouterr().err
