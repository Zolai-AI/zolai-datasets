"""Comprehensive tests for all zolai-datasets Bible scripts."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts" / "bible"
DATA = Path("/home/peter/Documents/Projects/zolai-ai/data")


def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO), check=False)
    return r.returncode, r.stdout, r.stderr


def py_compile_check(path):
    rc, _, err = run([sys.executable, "-c",
                      f"import py_compile; py_compile.compile('{path}', doraise=True)"])
    return rc == 0, err


# === PY_COMPILE: All scripts ===

ALL_SCRIPTS = sorted(SCRIPTS.glob("*.py"))

def test_all_scripts_compile():
    failures = []
    for s in ALL_SCRIPTS:
        ok, err = py_compile_check(s)
        if not ok:
            failures.append(f"{s.name}: {err.strip()[:80]}")
    assert not failures, "Compile failures:\n" + "\n".join(failures)


# === MENU SYNTAX ===

def test_menu_syntax():
    rc, _, err = run(["bash", "-n", str(SCRIPTS / "menu.sh")])
    assert rc == 0, f"Menu syntax error: {err}"


# === BIBLE ENGINE ===

def test_bible_engine_stats():
    rc, out, err = run([sys.executable, str(SCRIPTS / "bible_engine.py"), "--stats"])
    assert rc == 0, f"--stats failed: {err}"
    assert "entries" in out, f"Missing entries: {out[:200]}"


def test_bible_engine_learn():
    rc, out, err = run([sys.executable, str(SCRIPTS / "bible_engine.py"),
                        "--learn", "--level", "1"])
    assert rc == 0, f"--learn failed: {err}"
    assert "Exercise" in out or "Correct" in out, f"No exercise: {out[:200]}"


def test_bible_engine_search():
    rc, _out, err = run([sys.executable, str(SCRIPTS / "bible_engine.py"),
                        "--search", "pasian", "--limit", "3"])
    assert rc == 0, f"--search failed: {err}"


def test_bible_engine_export():
    rc, _out, err = run([sys.executable, str(SCRIPTS / "bible_engine.py"),
                        "--export", "--type", "translation", "--limit", "5"])
    assert rc == 0, f"--export failed: {err}"


def test_bible_engine_review():
    rc, _out, err = run([sys.executable, str(SCRIPTS / "bible_engine.py"),
                        "--review", "--due"])
    assert rc == 0, f"--review failed: {err}"


# === PARAGRAPH ENGINE ===

def test_para_engine_stats():
    rc, out, err = run([sys.executable, str(SCRIPTS / "paragraph_engine.py"), "--stats"])
    assert rc == 0, f"--stats failed: {err}"
    assert "entries" in out, f"Missing: {out[:200]}"


def test_para_engine_analyze():
    rc, out, err = run([sys.executable, str(SCRIPTS / "paragraph_engine.py"),
                        "--analyze", "--text", "Pasian in hi leh a piangsak hi"])
    assert rc == 0, f"--analyze failed: {err}"
    assert "Language: ZO" in out, f"Not detected: {out[:200]}"


def test_para_engine_paraphrase():
    rc, out, err = run([sys.executable, str(SCRIPTS / "paragraph_engine.py"),
                        "--paraphrase", "--level", "2", "--style", "SIMPLE",
                        "--text", "Pasian in hi leh a piangsak hi"])
    assert rc == 0, f"--paraphrase failed: {err}"
    assert "Paraphrased" in out or "paraphrase" in out.lower(), f"No output: {out[:200]}"


def test_para_engine_multi_style():
    rc, out, err = run([sys.executable, str(SCRIPTS / "paragraph_engine.py"),
                        "--paraphrase", "--level", "2", "--multi-style",
                        "--text", "Pasian in hi leh a piangsak hi"])
    assert rc == 0, f"--multi-style failed: {err}"
    assert "SIMPLE" in out or "FORMAL" in out, f"No styles: {out[:200]}"


# === PIPELINE ===

def test_pipeline_stats():
    rc, _out, err = run([sys.executable, str(SCRIPTS / "build_linguistic_pipeline.py"), "--stats"])
    assert rc == 0, f"--stats failed: {err}"


def test_pipeline_steps():
    steps = ["raw", "sentence_alignment", "vocabulary", "phrases", "grammar",
             "evidence_graph", "learning", "metadata"]
    failures = []
    for step in steps:
        rc, _out, err = run([sys.executable, str(SCRIPTS / "build_linguistic_pipeline.py"),
                            "--step", step], timeout=60)
        if rc != 0:
            failures.append(f"{step}: {err.strip()[:100]}")
    assert not failures, "Pipeline failures:\n" + "\n".join(failures)


# === DICTIONARY ===

def test_dict_zo_en_clean():
    path = DATA / "dictionary" / "processed" / "dict_zo_en_clean.jsonl"
    assert path.exists(), f"Missing: {path}"
    with open(path) as f:
        first = json.loads(f.readline())
    assert "zolai" in first, f"Bad format: {first.keys()}"


def test_dict_canonical_clean():
    path = DATA / "dictionary" / "processed" / "dict_canonical_clean.jsonl"
    assert path.exists(), f"Missing: {path}"
    with open(path) as f:
        first = json.loads(f.readline())
    assert "headword" in first, f"Bad format: {first.keys()}"


def test_dict_zo_en_search():
    path = DATA / "dictionary" / "processed" / "dict_zo_en_clean.jsonl"
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("zolai", "").lower() == "pasian":
                assert "God" in d.get("english_clean", ""), f"Got: {d}"
                return
    assert False, "pasian not found"


def test_dict_en_zo_search():
    path = DATA / "dictionary" / "processed" / "dict_canonical_clean.jsonl"
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("headword", "").lower() == "god":
                assert "Pasian" in d.get("translations_clean", ""), f"Got: {d}"
                return
    assert False, "god not found"


# === OTHER SCRIPTS ===

def test_check_non_zolai():
    ok, err = py_compile_check(SCRIPTS / "check_non_zolai.py")
    assert ok, f"Failed: {err}"

def test_build_full_kb():
    ok, err = py_compile_check(SCRIPTS / "build_full_knowledge_base.py")
    assert ok, f"Failed: {err}"

def test_study_bible_books():
    ok, err = py_compile_check(SCRIPTS / "study_bible_books.py")
    assert ok, f"Failed: {err}"

def test_align_words():
    ok, err = py_compile_check(SCRIPTS / "align_words.py")
    assert ok, f"Failed: {err}"

def test_build_parallel_corpus():
    ok, err = py_compile_check(SCRIPTS / "build_parallel_corpus.py")
    assert ok, f"Failed: {err}"

def test_extract_grammar():
    ok, err = py_compile_check(SCRIPTS / "extract_grammar_patterns.py")
    assert ok, f"Failed: {err}"

def test_generate_training():
    ok, err = py_compile_check(SCRIPTS / "generate_training_data.py")
    assert ok, f"Failed: {err}"

def test_build_vocab_db():
    ok, err = py_compile_check(SCRIPTS / "build_vocabulary_db.py")
    assert ok, f"Failed: {err}"

def test_build_bible_dict():
    ok, err = py_compile_check(SCRIPTS / "build_bible_dictionary.py")
    assert ok, f"Failed: {err}"

def test_bible_vocab_pipeline():
    ok, err = py_compile_check(SCRIPTS / "bible_vocab_pipeline.py")
    assert ok, f"Failed: {err}"

def test_crossref_vocab():
    ok, err = py_compile_check(SCRIPTS / "crossref_bible_vocab.py")
    assert ok, f"Failed: {err}"

def test_corpus_analyzer():
    ok, err = py_compile_check(SCRIPTS / "bible_corpus_analyzer.py")
    assert ok, f"Failed: {err}"
