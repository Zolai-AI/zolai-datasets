#!/usr/bin/env python3
"""Audit every script's SQL against the live core database schema.

The workspace has one canonical store — ``data/zolai.db`` (2.9 GB, ~132 tables),
owned by ``zolai-core``. Scripts written before that consolidation still name the
old dictionary schema (``headword``/``sources``/``raw_json``) or tables that only
ever existed in a scratch DB (``entries``/``stems``/``fts_idx``). Against the core
database those statements fail mid-run, sometimes after earlier batches have
already committed.

This tool parses the SQL string literals out of each script and reports:
  * writes to columns the core schema does not have (would raise);
  * reads from tables that do not exist (would raise);
  * ``CREATE TABLE`` statements that would add a new table to the core DB
    (usually unintended once a script is repointed at it).

Usage:
    python3 scripts/audit_core_schema.py              # report
    python3 scripts/audit_core_schema.py --strict      # exit 1 on hard errors
    python3 scripts/audit_core_schema.py --json         # machine-readable
    ZOLAI_DB_URL=postgresql://… python3 scripts/audit_core_schema.py
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from db import connect, db_path, resolve_url  # noqa: E402

# INSERT INTO t (a, b) / UPDATE t SET a = ?, b = ? / DELETE FROM t
_INSERT = re.compile(
    r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)", re.I)
_UPDATE = re.compile(
    r"\bUPDATE\s+([a-zA-Z_]\w*)\s+SET\s+(.*?)(?:\bWHERE\b|;|$)", re.I | re.S)
_READ = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_]\w*)", re.I)
_CREATE = re.compile(
    r"\bCREATE\s+(?:VIRTUAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_]\w*)", re.I)

# Identifiers that follow FROM/JOIN but are never real tables in this codebase.
_NOT_A_TABLE = {
    "sqlite_master", "information_schema", "dual", "values", "select",
    "json_each", "json_tree", "pragma_table_info", "generate_series",
}


def _literals(path: pathlib.Path):
    """Yield (line, string) for every SQL-looking string constant in a file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, ValueError) as exc:
        yield 0, f"# parse error: {exc}"
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if re.search(
                r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM"
                r"|CREATE\s+(?:VIRTUAL\s+)?TABLE)\b", text, re.I):
                yield node.lineno or 0, text


def _required_missing(live, table, supplied):
    """NOT NULL columns with no default that the INSERT leaves out."""
    rows = live.get(f"{table}::__required__") or []
    return [c for c in rows if c not in supplied and c != "id"]


def _cols_of(live: dict[str, list[str]], table: str) -> set[str] | None:
    names = live.get(table)
    return {c.lower() for c in names} if names else None


def _script_targets_core(path: pathlib.Path) -> bool:
    """Whether a script's own DB_PATH resolves to the canonical core store.

    A builder that writes a private scratch file legitimately owns that file's
    schema, so ``entries``/``stems``/``fts_idx`` inside it are not core-schema
    violations. Only scripts pointed at the shared database are held to it.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(
        r"^\s*(?:DB_PATH|DB|DATABASE|db_path|TARGET_DB|original_path)\s*=\s*(.+)$",
        text, re.M)
    if not m:
        return True  # unknown target — assume it uses connect()/core
    expr = m.group(1).strip()
    if "db_path()" in expr or re.search(r"[\"']zolai\.db[\"']", expr):
        return True
    if "db_path(name=" in expr or "db_path(" in expr:
        return False
    return bool(re.search(r"[\"'].*zolai\.db", expr))


def audit(root: pathlib.Path, live: dict[str, list[str]], tables: set[str]):
    findings = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in str(path) or path.name in {"db.py", pathlib.Path(__file__).name}:
            continue
        rel = path.relative_to(root.parent)
        targets_core = _script_targets_core(path)
        own: set[str] = set()
        if not targets_core:
            # Tables this builder creates itself belong to its scratch schema.
            for line, sql in _literals(path):
                for m in _CREATE.finditer(sql):
                    own.add(m.group(1).lower())
        for line, sql in _literals(path):
            if sql.startswith("# parse error"):
                findings.append({"file": str(rel), "line": line, "kind": "parse",
                                 "detail": sql, "severity": "warn"})
                continue
            for m in _INSERT.finditer(sql):
                table, body = m.group(1).lower(), m.group(2)
                if not targets_core and table in own:
                    continue
                if table not in tables:
                    findings.append({"file": str(rel), "line": line, "kind": "missing-table",
                                     "detail": f"INSERT → {table}", "severity": "error"})
                    continue
                have = _cols_of(live, table)
                # FTS5 admin commands use the table's own name as the column:
                #   INSERT INTO t_fts(t_fts) VALUES('rebuild')
                if body.strip().strip('"`[]').lower() == table:
                    continue
                supplied = [c.strip().strip('"`[]').lower()
                            for c in body.split(",") if c.strip()]
                for col in supplied:
                    if col and col not in have:
                        findings.append({"file": str(rel), "line": line,
                                         "kind": "bad-column",
                                         "detail": f"INSERT {table}.{col}",
                                         "severity": "error"})
                # A column that is NOT NULL without a DEFAULT and absent from the
                # INSERT list raises IntegrityError at runtime, which the
                # column-name check above cannot see.
                for col in _required_missing(live, table, supplied):
                    findings.append({"file": str(rel), "line": line,
                                     "kind": "missing-required",
                                     "detail": f"INSERT {table} omits NOT NULL {col}",
                                     "severity": "error"})
            for m in _UPDATE.finditer(sql):
                table, body = m.group(1).lower(), m.group(2)
                if not targets_core and table in own:
                    continue
                if table not in tables:
                    findings.append({"file": str(rel), "line": line, "kind": "missing-table",
                                     "detail": f"UPDATE → {table}", "severity": "error"})
                    continue
                have = _cols_of(live, table)
                for part in body.split(","):
                    col = part.split("=")[0].strip().strip('"`[]')
                    if col and not col.startswith("?") and "%" not in col \
                            and col.lower() not in have:
                        findings.append({"file": str(rel), "line": line,
                                         "kind": "bad-column",
                                         "detail": f"UPDATE {table}.{col}",
                                         "severity": "error"})
            for m in _READ.finditer(sql):
                table = m.group(1).lower()
                if table in _NOT_A_TABLE or table in tables:
                    continue
                if not targets_core and table in own:
                    continue
                # Subqueries/aliases are common after FROM; only flag snake_case
                # names that look like intended tables.
                if "_" in table or table[0].islower():
                    findings.append({"file": str(rel), "line": line,
                                     "kind": "missing-table",
                                     "detail": f"read ← {table}", "severity": "warn"})
            for m in _CREATE.finditer(sql):
                table = m.group(1).lower()
                if table not in tables and targets_core:
                    findings.append({"file": str(rel), "line": line, "kind": "new-table",
                                     "detail": f"CREATE TABLE {table} — would add a "
                                               f"table to the core DB",
                                     "severity": "warn"})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scripts-dir", default=None,
                    help="directory to scan (default: this repo's scripts/)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when any error-severity finding exists")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    dialect, target = resolve_url(None)
    root = pathlib.Path(args.scripts_dir) if args.scripts_dir else \
        pathlib.Path(__file__).resolve().parent
    if not root.exists():
        print(f"error: nothing to scan at {root}", file=sys.stderr)
        return 2

    conn = connect(None)
    live: dict[str, list[str]] = {}
    if dialect == "sqlite":
        tables = {r[0].lower() for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        for t in sorted(tables):
            info = list(conn.execute(f'PRAGMA table_info("{t}")'))
            live[t] = [r[1] for r in info]
            live[f"{t}::__required__"] = [
                r[1] for r in info if r[3] and r[4] is None and not r[5]
            ]
    else:
        tables = {r[0].lower() for r in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'")}
        for t in sorted(tables):
            info = list(conn.execute(
                "SELECT column_name, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ?", (t,)))
            live[t] = [r[0] for r in info]
            live[f"{t}::__required__"] = [
                r[0] for r in info if r[1] == "NO" and r[2] is None
            ]
    conn.close()

    print(f"Schema source: {dialect} → "
          f"{target if dialect == 'sqlite' else 'server'}")
    print(f"Core tables:   {len(tables)}")
    print(f"Scanning:      {root}\n")

    findings = audit(root, live, tables)
    if args.as_json:
        print(json.dumps(findings, indent=2))
    else:
        order = {"error": 0, "warn": 1}
        for f in sorted(findings, key=lambda x: (order[x["severity"]], x["file"], x["line"])):
            print(f"  [{f['severity'].upper():5}] {f['file']}:{f['line']} "
                  f"{f['kind']:15} {f['detail']}")
        counts = Counter(f"{f['kind']}/{f['severity']}" for f in findings)
        print(f"\n{len(findings)} findings")
        for k, v in sorted(counts.items()):
            print(f"  {k}: {v}")

    errors = sum(1 for f in findings if f["severity"] == "error")
    if args.strict and errors:
        print(f"\n{errors} error-severity finding(s) — scripts would fail against "
              f"the core schema.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
