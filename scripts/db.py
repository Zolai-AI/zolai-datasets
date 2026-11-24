"""Dual-engine DB access: ZOLAI_DB_URL selects sqlite or postgres.

Default (nothing set): the **core workspace database** at ``<workspace>/data/
zolai.db`` — the same 2.9 GB / 132-table store that ``zolai-core`` owns and the
API serves. This repo holds build scripts, not the data; it must not silently
create a private, empty ``data/zolai.db`` beside itself.

Switching engines is a configuration change, not a code change:

    sqlite:///data/zolai.db               → stdlib sqlite3 (default, zero-dep)
    postgresql://user:pass@host:5432/db   → psycopg (v3) or psycopg2 (optional)
    postgres://…                          (alias)

Every script calls the same ``connect(...)``; ``translate()`` rewrites ``?``
placeholders to ``%s`` when the dialect is postgres. Rows are dict-like in
both engines (``sqlite3.Row`` on sqlite, :class:`Row` on postgres), so
``row["column"]`` and ``row_to_dict(row)`` work everywhere.

Portability rules the scripts follow so both engines behave alike
(same rules as ``zolai-tts/src/zolai_tts/db/drivers.py``):
  * placeholders are written ``?`` and translated to ``%s`` for PostgreSQL;
  * booleans are stored as INTEGER 0/1;
  * timestamps are ISO-8601 UTC strings (TEXT) — no strftime()/datetime() SQL;
  * JSON is stored as TEXT (no jsonb dependency);
  * upserts use ``INSERT … ON CONFLICT (…) DO UPDATE SET …`` (both engines);
  * ``substr()`` and ``COALESCE/SUM/COUNT`` are the only SQL expressions used.

Resolution order (mirrors ``zolai-core/zolai/config.py`` so one deployment
config drives every repo):
  1. an explicit URL (anything containing ``://``);
  2. the ``ZOLAI_DB_URL`` environment variable — this is what switching
     engines means (config, not code);
  3. ``ZOLAI_DB_PATH`` — the canonical path override used by zolai-core;
  4. ``ZOLAI_DATA_ROOT``/zolai.db, then the legacy ``DATA``/zolai.db;
  5. a bare path argument from the script — anchored at the repo root, but
     falling back to the same-named file under the workspace ``data/`` when the
     repo-local copy is absent (so ``connect('data/zolai.db')`` reaches the core
     DB rather than creating an empty one);
  6. ``<workspace>/data/zolai.db``, then ``<repo root>/data/zolai.db``.

Optional dependency (only needed for postgres): ``pip install "psycopg[binary]"``.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
# zolai-datasets sits beside the shared data/ dir in the workspace checkout.
WORKSPACE_ROOT = REPO_ROOT.parent


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else None


def _core_db_path() -> Path:
    """The canonical zolai.db, using the same env vars as zolai-core.

    A repo-local ``data/zolai.db`` is honoured only when it already exists
    (test fixtures, CI sandboxes); it is never created as a fallback, because a
    silently-empty private DB reads as "no rows" instead of "wrong path".
    """
    direct = _env_path("ZOLAI_DB_PATH")
    if direct is not None:
        return direct
    for root_var in ("ZOLAI_DATA_ROOT", "DATA"):
        root = _env_path(root_var)
        if root is not None:
            return root / "zolai.db"
    repo_local = REPO_ROOT / "data" / "zolai.db"
    if repo_local.exists():
        return repo_local
    return WORKSPACE_ROOT / "data" / "zolai.db"


DEFAULT_SQLITE_PATH = _core_db_path()

__all__ = [
    "connect",
    "row_to_dict",
    "Row",
    "DbError",
    "DEFAULT_SQLITE_PATH",
    "core_db_path",
    "data_root",
    "db_path",
    "resolve_url",
    "translate_ddl",
    "assert_rebuildable",
    "table_columns",
    "check_sql_columns",
    "assert_schema",
]


def core_db_path() -> Path:
    """Public accessor for the resolved canonical database path."""
    return _core_db_path()


def data_root() -> Path:
    """The shared ``data/`` directory that holds ``zolai.db`` and the corpora.

    Scripts previously hardcoded an absolute ``/home/<user>/…`` path, which is
    both machine-specific and a leak in a public repo. Override with
    ``ZOLAI_DATA_ROOT`` (or the legacy ``DATA``); the default is the ``data/``
    dir beside this repo in the workspace checkout.
    """
    for var in ("ZOLAI_DATA_ROOT", "DATA"):
        root = _env_path(var)
        if root is not None:
            return root
    direct = _env_path("ZOLAI_DB_PATH")
    if direct is not None:
        return direct.parent
    return _core_db_path().parent


def db_path(value: "str | Path | None" = None, *, name: str = "zolai.db") -> Path:
    """Resolve a database path for use as a module-level ``DB_PATH``.

    Scripts previously hardcoded ``'data/zolai.db'`` (which depended on the
    current working directory), ``parents[3] / "data"`` (which only held on one
    checkout depth), or an absolute ``/home/…`` path (machine-specific and
    wrong for a public repo). All of them now read:

        DB_PATH = db_path()                  # the canonical core zolai.db
        DB_PATH = db_path("dictionary_v3.db")  # a sibling dataset

    Postgres deployments are unaffected by the returned path: ``connect()``
    still prefers ``ZOLAI_DB_URL`` when it is set, so this value is only the
    sqlite fallback and an existence-check target.
    """
    if value is not None:
        raw = str(value).strip()
        if raw:
            if "://" in raw:
                return Path(_anchor_relative(_sqlite_path_from_url(raw)))
            p = Path(raw).expanduser()
            if p.is_absolute():
                return p
            if p.parent == Path("."):
                # A bare filename is a sibling dataset of the canonical DB.
                return _core_db_path().parent / p.name
            return Path(_anchor_relative(raw))
    if os.environ.get("ZOLAI_DB_URL", "").strip() and "://" in os.environ["ZOLAI_DB_URL"]:
        url = os.environ["ZOLAI_DB_URL"].strip().lower()
        if url.startswith(("postgres://", "postgresql://", "pg://")):
            # No filesystem path exists for a server engine; hand back the
            # canonical location so callers can still log/stub it.
            return _core_db_path().with_name(name)
    explicit = _env_path("ZOLAI_DB_PATH")
    if explicit is not None and name == "zolai.db":
        return explicit
    base = _core_db_path()
    if name == base.name:
        return base
    return base.parent / name


class DbError(RuntimeError):
    """Raised when a database URL is unsupported or a driver is missing."""


class Row:
    """Dict-like row for postgres that mirrors ``sqlite3.Row`` semantics:
    index access (``row[0]``), key access (``row["col"]``), ``keys()``,
    iteration over values, and ``dict(row)`` via ``keys()`` + ``__getitem__``.
    """

    __slots__ = ("_keys", "_values", "_map")

    def __init__(self, keys: tuple[str, ...], values: tuple[Any, ...]) -> None:
        self._keys = keys
        self._values = values
        self._map = dict(zip(keys, values))

    def keys(self) -> tuple[str, ...]:
        return self._keys

    def values(self) -> tuple[Any, ...]:
        return self._values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._map.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in self._map

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"Row({self._map!r})"


def translate_ddl(sql: str) -> list[str]:
    """Split a sqlite-flavoured DDL script into PostgreSQL-valid statements.

    Mirrors ``src-tauri/src/db/mod.rs::translate_ddl`` so both repos apply the
    same portability rules:

    * leading ``--`` comment lines are dropped *before* classification, so a
      schema file's header comment cannot hide a ``PRAGMA`` (that used to reach
      the server as a syntax error);
    * ``PRAGMA …`` statements are sqlite-only and are dropped;
    * ``AUTOINCREMENT`` becomes ``GENERATED BY DEFAULT AS IDENTITY`` — the
      surrogate-key form PostgreSQL understands.

    Statements that need a genuine rewrite (``INSERT OR REPLACE/IGNORE``,
    ``sqlite_master`` inspection) are left untouched and documented in
    ``scripts/README-db.md``: ``executescript`` is for CREATE/ALTER scripts, not
    for data-preserving rewrites.
    """
    statements: list[str] = []
    for chunk in sql.split(";"):
        lines = chunk.strip().splitlines()
        # Drop leading blanks/comments so the first meaningful token decides.
        while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
            lines.pop(0)
        body = "\n".join(lines).strip()
        if not body or body.upper().startswith("PRAGMA"):
            continue
        statements.append(body.replace("AUTOINCREMENT", "GENERATED BY DEFAULT AS IDENTITY"))
    return statements


def row_to_dict(row: Any) -> Any:
    """Normalize a row from either dialect into a plain dict.

    ``None`` passes through (fetchone style), so this is safe to wrap around
    every fetch in a script.
    """
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if isinstance(row, Row):
        return dict(zip(row.keys(), row.values()))
    if hasattr(row, "keys"):  # sqlite3.Row and psycopg2 RealDictRow
        return {k: row[k] for k in row.keys()}
    return row  # plain tuple/scalar — nothing to convert


# ── sqlite ──────────────────────────────────────────────────────────────────


class SqliteConn(sqlite3.Connection):
    """sqlite3.Connection plus the dual-engine surface (``dialect``,
    ``translate``, convenience ``fetchone``/``fetchall``).

    Returning the native connection (via ``factory=``) keeps every existing
    call site working unchanged: cursors, ``row_factory``, ``executescript``,
    transactions, context managers.
    """

    dialect = "sqlite"

    def translate(self, sql: str) -> str:
        return sql

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Any:
        return self.execute(sql, tuple(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[Any]:
        return self.execute(sql, tuple(params)).fetchall()


def _open_sqlite(path_or_url: str, timeout: float) -> SqliteConn:
    path = Path(path_or_url).expanduser()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=timeout,
                           check_same_thread=False, factory=SqliteConn)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


# ── postgres ────────────────────────────────────────────────────────────────


_INSERT_RE = re.compile(r"^\s*insert\b", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\breturning\b", re.IGNORECASE)
_INSERT_TARGET_RE = re.compile(
    r"^\s*insert\s+(?:or\s+\w+\s+)?into\s+([A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)?)",
    re.IGNORECASE,
)


class _PgCursor:
    """Thin cursor wrapper: translates ``?`` → ``%s`` and yields Row objects."""

    def __init__(self, raw: Any, conn: "PgConn") -> None:
        self._raw = raw
        self._conn = conn
        self._lastrowid: Any = None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> "_PgCursor":
        translated = self._conn.translate(sql)
        self._lastrowid = None
        if _INSERT_RE.match(translated) and not _RETURNING_RE.search(translated):
            match = _INSERT_TARGET_RE.match(translated)
            if match and self._conn._table_has_id(match.group(1)):
                # sqlite3.Cursor.lastrowid parity: PostgreSQL has no lastrowid,
                # so ask for the generated key explicitly.
                body = translated.rstrip().rstrip(";")
                self._raw.execute(body + " RETURNING id",
                                  tuple(params) if params else None)
                row = self._raw.fetchone()
                self._lastrowid = row[0] if row else None
                return self
        self._raw.execute(translated, tuple(params) if params else None)
        return self

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]) -> "_PgCursor":
        self._raw.executemany(self._conn.translate(sql),
                              [tuple(p) for p in seq])
        return self

    def _wrap(self, row: Any) -> Any:
        if row is None or isinstance(row, (dict, Row)):
            return row
        keys = tuple(d[0] for d in (self._raw.description or ()))
        return Row(keys, tuple(row))

    def fetchone(self) -> Any:
        return self._wrap(self._raw.fetchone())

    def fetchall(self) -> list[Any]:
        return [self._wrap(r) for r in self._raw.fetchall()]

    def fetchmany(self, size: int | None = None) -> list[Any]:
        rows = self._raw.fetchmany(size) if size else self._raw.fetchmany()
        return [self._wrap(r) for r in rows]

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    @property
    def lastrowid(self) -> Any:
        return self._lastrowid if self._lastrowid is not None else getattr(self._raw, "lastrowid", None)

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> "_PgCursor":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False

    def __iter__(self):
        return iter(self.fetchall())


class PgConn:
    """PostgreSQL connection via psycopg (v3, preferred) or psycopg2.

    Same call-site surface as :class:`SqliteConn`: ``execute``, ``executemany``,
    ``cursor``, ``fetchone``, ``fetchall``, ``commit``, ``rollback``, ``close``,
    ``executescript``, ``dialect``, ``translate``.
    """

    dialect = "postgres"

    @property
    def row_factory(self) -> Any:
        # Scripts assign sqlite3.Row after connect(); PgConn already returns
        # dict-like Row objects, so accept the assignment as a no-op.
        return Row

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        pass

    def __init__(self, conninfo: str) -> None:
        self.conninfo = conninfo
        self._raw: Any = None
        self._module = ""
        self._id_columns: dict[str, bool] = {}

    def _table_has_id(self, table: str) -> bool:
        """Whether ``table`` exposes an ``id`` column (cached per connection).

        Used to decide if an INSERT can emit ``RETURNING id`` for lastrowid
        parity. Tables without an ``id`` column simply keep lastrowid None.
        """
        key = table.lower()
        if key not in self._id_columns:
            name = key.rsplit(".", 1)[-1].strip('"')
            cursor = self.raw.cursor()
            try:
                cursor.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = 'id' LIMIT 1",
                    (name,),
                )
                self._id_columns[key] = cursor.fetchone() is not None
            finally:
                cursor.close()
        return self._id_columns[key]

    def _import(self):
        try:
            import psycopg

            self._module = "psycopg"
            return psycopg
        except ImportError:
            pass
        try:
            import psycopg2

            self._module = "psycopg2"
            return psycopg2
        except ImportError as exc:
            raise DbError(
                "PostgreSQL needs the psycopg driver: pip install \"psycopg[binary]\" "
                "(psycopg2 also works for simple call sites)"
            ) from exc

    @property
    def raw(self) -> Any:
        if self._raw is None:
            module = self._import()
            self._raw = module.connect(self.conninfo)
        return self._raw

    def translate(self, sql: str) -> str:
        # `?` -> `%s`; our portable SQL never embeds '?' inside string literals.
        # AUTOINCREMENT only ever appears in DDL, so rewriting it here is safe
        # for DML too and keeps single CREATE TABLE calls portable.
        return sql.replace("?", "%s").replace(
            "AUTOINCREMENT", "GENERATED BY DEFAULT AS IDENTITY"
        )

    def cursor(self) -> _PgCursor:
        return _PgCursor(self.raw.cursor(), self)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> _PgCursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]) -> None:
        cur = self.cursor()
        cur.executemany(sql, seq)
        cur.close()

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Any:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[Any]:
        return self.execute(sql, params).fetchall()

    def executescript(self, sql: str) -> None:
        # sqlite scripts carry PRAGMAs and AUTOINCREMENT; translate_ddl drops
        # the former and maps the latter to an identity column.
        for statement in translate_ddl(sql):
            self.execute(statement)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        if self._raw is not None:
            self._raw.rollback()

    def close(self) -> None:
        if self._raw is not None:
            self._raw.close()
            self._raw = None

    # `with conn:` commits on clean exit / rolls back on exception — same
    # semantics sqlite3 gives, so `with conn:` blocks in scripts keep working.
    def __enter__(self) -> "PgConn":
        self.raw  # ensure connected
        return self

    def __exit__(self, *exc: Any) -> bool:
        if exc[0] is None:
            self.commit()
        else:
            self.rollback()
        return False


# ── URL plumbing ─────────────────────────────────────────────────────────────


def _sqlite_path_from_url(url: str) -> str:
    if url.lower().startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.lower().startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


def _anchor_relative(raw: str) -> str:
    """Anchor a script-supplied relative sqlite path.

    Scripts write ``'data/zolai.db'`` or ``Path('data')/'zolai.db'``. Repo-root
    anchoring used to create an empty private DB beside zolai-datasets; now, if
    that path does not exist, the same-named file under the workspace ``data/``
    dir is preferred so the core database is used.
    """
    if raw == ":memory:":
        return raw
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path)
    repo_local = REPO_ROOT / path
    if repo_local.exists():
        return str(repo_local)
    workspace_local = WORKSPACE_ROOT / path
    if workspace_local.exists():
        return str(workspace_local)
    # Nothing on disk yet — for a fresh DB, honour the configured core path
    # when the filename matches, otherwise keep the repo-root anchor.
    core = _core_db_path()
    if path.name == core.name and path.parent.name == "data":
        return str(core)
    return str(repo_local)


def resolve_url(url: "str | Path | None" = None) -> tuple[str, str]:
    """Return ``(dialect, target)`` per the resolution order in the docstring.

    Accepts a ``str`` or a ``pathlib.Path`` — scripts commonly hold ``DB_PATH``
    as a ``Path``, and ``sqlite3.connect`` accepted one, so this layer must too.
    """
    env = os.environ.get("ZOLAI_DB_URL", "").strip()
    candidate = ""
    if url is not None:
        url = str(url).strip() or None
    if url and "://" in url:
        candidate = url.strip()
    elif env:
        candidate = env
    elif url:
        return "sqlite", _anchor_relative(url)
    else:
        # No argument: use the configured engine, defaulting to the core DB.
        if os.environ.get("ZOLAI_POSTGRES_URL", "").strip() or os.environ.get(
            "ZOLAI_PG_URL", ""
        ).strip():
            candidate = (
                os.environ.get("ZOLAI_POSTGRES_URL", "").strip()
                or os.environ.get("ZOLAI_PG_URL", "").strip()
            )
        else:
            candidate = f"sqlite:///{_core_db_path()}"

    lowered = candidate.lower()
    if lowered.startswith(("postgres://", "postgresql://", "pg://")):
        conninfo = candidate
        for alias in ("postgres://", "pg://"):
            if conninfo.lower().startswith(alias):
                conninfo = "postgresql://" + conninfo[len(alias):]
        return "postgres", conninfo
    if lowered.startswith("sqlite://"):
        path = _sqlite_path_from_url(candidate)
        # Tolerate zolai-tts-style "sqlite:///home/user/…": a first segment that
        # is a filesystem root means the author meant an absolute path.
        if path and path.split("/", 1)[0] in ("home", "Users", "mnt", "media", "var", "private", "Volumes"):
            path = "/" + path
        if path != ":memory:" and not Path(path).is_absolute():
            path = _anchor_relative(path)
        return "sqlite", path
    if "://" in candidate:
        scheme = candidate.split("://", 1)[0]
        raise DbError(
            f"Unsupported database URL scheme {scheme!r}. "
            "Use sqlite:///path or postgresql://user:pass@host:5432/db"
        )
    return "sqlite", candidate


def connect(url: str | None = None, *, timeout: float = 30.0) -> Any:
    """Open a dual-engine connection. See module docstring for semantics.

    Drop-in replacement for ``sqlite3.connect(path)``: with the default
    configuration (no ``ZOLAI_DB_URL``) the script's own path is opened as
    SQLite exactly as before, plus WAL, ``foreign_keys=ON``, a busy timeout,
    ``check_same_thread=False`` and ``sqlite3.Row`` rows.
    """
    dialect, target = resolve_url(url)
    if dialect == "sqlite":
        return _open_sqlite(target, timeout)
    return PgConn(target)


# ── Core-schema guard ────────────────────────────────────────────────────────

_WRITE_RE = re.compile(
    r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+([a-zA-Z_][\w]*)\s*\(([^)]*)\)"
    r"|\bUPDATE\s+([a-zA-Z_][\w]*)\s+SET\s+(.*?)(?:\bWHERE\b|$)",
    re.I | re.S,
)


def table_columns(conn, table: str) -> set[str] | None:
    """Live column names for ``table`` (``None`` when the table is absent)."""
    if getattr(conn, "dialect", "sqlite") == "postgres":
        cur = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ?",
            (table,),
        )
        names = {str(r[0]) for r in cur.fetchall()}
    else:
        cur = conn.execute(f"PRAGMA table_info('{table.replace(chr(39), '')}')")
        names = {str(r[1]) for r in cur.fetchall()}
    return names or None


def check_sql_columns(conn, sql: str) -> list[str]:
    """Return human-readable problems for a single write statement.

    The core database is a 2.9 GB shared store with an established schema
    (``dictionary.zolai``/``english``/``source``, not the older
    ``headword``/``sources``/``raw_json``). Scripts that predate the merge still
    emit those stale names; without this guard they die deep inside a loop with a
    bare ``OperationalError``, sometimes after earlier batches have committed.
    """
    problems: list[str] = []
    for m in _WRITE_RE.finditer(sql):
        table = (m.group(1) or m.group(3) or "").lower()
        body = m.group(2) if m.group(1) else m.group(4)
        if not table or body is None:
            continue
        live = table_columns(conn, table)
        if live is None:
            problems.append(
                f"table {table!r} does not exist in the core database"
            )
            continue
        if m.group(1):  # INSERT … (cols)
            names = [c.strip().strip('"`[]') for c in body.split(",")]
        else:  # UPDATE … SET a=?, b=?
            names = [c.split("=")[0].strip().strip('"`[]') for c in body.split(",")]
        lowered = {c.lower() for c in live}
        missing = [
            n for n in names
            if n and not n.startswith("?") and "%" not in n and n.lower() not in lowered
        ]
        for n in missing:
            problems.append(
                f"{table}.{n!r} is not a column of the core schema "
                f"(has: {', '.join(sorted(live)[:6])}…)"
            )
    return problems


def assert_schema(conn, *statements: str, strict: bool = True) -> None:
    """Raise :class:`DbError` if any write targets a column the core DB lacks.

    Call this once, before a migration/backfill loop, so a stale script fails at
    startup instead of leaving a half-written table behind.
    """
    found = [f"[{i}] {p}" for i, s in enumerate(statements)
             for p in check_sql_columns(conn, s)]
    if found and strict:
        raise DbError(
            "Script schema does not match the core database:\n  "
            + "\n  ".join(found)
            + "\n\nThe canonical schema is defined by zolai-core "
              "(prisma/schema.prisma). Update this script's column names, or "
              "point ZOLAI_DB_URL at a scratch database while developing."
        )


# ── Destructive-operation guard ──────────────────────────────────────────────

#: Set this env var to acknowledge rebuilding the canonical database in place.
DESTRUCTIVE_ACK_ENV = "ZOLAI_ALLOW_CORE_REBUILD"

_CORE_TABLE_COUNT = 50  # a scratch builder never legitimately sees this many tables


def assert_rebuildable(path: "str | Path", *, purpose: str = "rebuild") -> Path:
    """Refuse to delete/recreate the canonical core database by accident.

    Several dataset scripts were written against a private scratch file and later
    repointed at ``data/zolai.db``. Their ``os.remove(DB_PATH)`` + ``CREATE TABLE``
    flow therefore wipes the whole shared store — 2.9 GB, ~132 tables, owned by
    ``zolai-core`` — the first time anyone runs them. Builders must either write a
    sibling file (``db_path(name="dictionary/db/…")``) or set
    ``ZOLAI_ALLOW_CORE_REBUILD=1`` after taking a backup.
    """
    target = Path(path).expanduser()
    try:
        resolved = target.resolve()
    except OSError:
        resolved = target
    core = _core_db_path().resolve()
    looks_like_core = resolved == core or _table_count(resolved) >= _CORE_TABLE_COUNT

    if not looks_like_core:
        return target
    if os.environ.get(DESTRUCTIVE_ACK_ENV, "").strip().lower() in {"1", "true", "yes"}:
        print(
            f"[db] {DESTRUCTIVE_ACK_ENV} is set — {purpose} will DESTROY the core "
            f"database at {core}. A backup is your responsibility.",
            file=sys.stderr,
        )
        return target
    raise DbError(
        f"Refusing to {purpose} the canonical core database: {core}\n"
        "  This script was written against its own scratch file. Give it one:\n"
        f"      DB_PATH = db_path(name='dictionary/db/{target.name or 'builder.db'}')\n"
        "  Or, if you really mean to rebuild the core store, back it up first and run:\n"
        f"      {DESTRUCTIVE_ACK_ENV}=1 python3 <this script>\n"
        "  The core schema is owned by zolai-core; recreating it here would also drop "
        "the tables the platform API depends on."
    )


def _table_count(path: Path) -> int:
    """How many tables a sqlite file holds (0 when missing or unreadable)."""
    try:
        if not path.exists():
            return 0
        probe = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    try:
        row = probe.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        probe.close()
