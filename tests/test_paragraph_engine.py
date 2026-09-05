"""Tests for paragraph_engine.py — Zolai Paragraph Learning & Style Intelligence Engine."""
import subprocess
import sys
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bible" / "paragraph_engine.py"
PIPELINE = Path(__file__).resolve().parent.parent / "scripts" / "bible" / "build_linguistic_pipeline.py"
MENU = Path(__file__).resolve().parent.parent / "scripts" / "bible" / "menu.sh"
WORKSPACE = Path(__file__).resolve().parent.parent.parent


def run_cmd(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class TestPyCompile:
    def test_paragraph_engine_compiles(self):
        result = run_cmd([sys.executable, "-c",
                          f"import py_compile; py_compile.compile('{SCRIPT}', doraise=True)"])
        assert result.returncode == 0, f"py_compile failed: {result.stderr}"

    def test_pipeline_compiles(self):
        result = run_cmd([sys.executable, "-c",
                          f"import py_compile; py_compile.compile('{PIPELINE}', doraise=True)"])
        assert result.returncode == 0, f"py_compile failed: {result.stderr}"


class TestRuff:
    def test_paragraph_engine_ruff(self):
        result = run_cmd(["ruff", "check", str(SCRIPT)])
        assert result.returncode == 0, f"ruff failed: {result.stdout}"

    def test_pipeline_ruff(self):
        result = run_cmd(["ruff", "check", str(PIPELINE)])
        assert result.returncode == 0, f"ruff failed: {result.stdout}"


class TestMenuSyntax:
    def test_menu_bash_syntax(self):
        result = run_cmd(["bash", "-n", str(MENU)])
        assert result.returncode == 0, f"menu syntax error: {result.stderr}"


class TestParagraphEngine:
    def test_stats(self):
        result = run_cmd([sys.executable, str(SCRIPT), "--stats"], timeout=15)
        assert result.returncode == 0, f"--stats failed: {result.stderr}"
        assert "ZO→EN dictionary" in result.stdout or "entries" in result.stdout

    def test_analyze_zolai(self):
        result = run_cmd([sys.executable, str(SCRIPT), "--analyze",
                          "--text", "Pasian in hi leh a piangsak hi"], timeout=15)
        assert result.returncode == 0, f"--analyze failed: {result.stderr}"
        assert "Language: ZO" in result.stdout or "narrative" in result.stdout

    def test_paraphrase_level2(self):
        result = run_cmd([sys.executable, str(SCRIPT), "--paraphrase", "--level", "2",
                          "--style", "SIMPLE",
                          "--text", "Pasian in hi leh a piangsak hi"], timeout=15)
        assert result.returncode == 0, f"--paraphrase failed: {result.stderr}"
        assert "Paraphrased" in result.stdout or "paraphrase" in result.stdout.lower()

    def test_multi_style(self):
        result = run_cmd([sys.executable, str(SCRIPT), "--paraphrase", "--level", "2",
                          "--multi-style",
                          "--text", "Pasian in hi leh a piangsak hi"], timeout=15)
        assert result.returncode == 0, f"--multi-style failed: {result.stderr}"
        assert "SIMPLE" in result.stdout or "FORMAL" in result.stdout


class TestDictionaryCleaning:
    def test_en_to_zo_search(self):
        """EN→ZO search shows 'Pasian' for 'god'."""
        result = run_cmd([sys.executable, "-c", f"""
import json
q = 'god'
path = '{WORKSPACE}/data/dictionary/processed/dict_canonical_clean.jsonl'
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('headword','').strip().lower()
        if q == hw:
            found.append(d.get('translations_clean',''))
            break
print(found[0] if found else 'NOT_FOUND')
"""], timeout=10)
        assert result.returncode == 0
        assert "Pasian" in result.stdout, f"Expected 'Pasian', got: {result.stdout}"

    def test_zo_to_en_search(self):
        """ZO→EN search shows 'God' for 'pasian'."""
        result = run_cmd([sys.executable, "-c", f"""
import json
q = 'pasian'
path = '{WORKSPACE}/data/dictionary/processed/dict_zo_en_clean.jsonl'
found = []
with open(path) as f:
    for line in f:
        d = json.loads(line)
        hw = d.get('zolai','').strip().lower()
        if q == hw:
            found.append(d.get('english_clean',''))
            break
print(found[0] if found else 'NOT_FOUND')
"""], timeout=10)
        assert result.returncode == 0
        assert "God" in result.stdout, f"Expected 'God', got: {result.stdout}"
