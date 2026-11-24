"""Dual-engine DB access: ZOLAI_DB_URL selects sqlite or postgres.

Default (ZOLAI_DB_URL unset): ``sqlite:///data/zolai.db`` relative to the repo
root — or, when a script passes its own path, that path (unchanged behaviour).
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

Resolution order for ``connect(url=...)``:
  1. an explicit URL (anything containing ``://``);
  2. the ``ZOLAI_DB_URL`` environment variable — this is what switching
     engines means (config, not code);
  3. a bare path argument (legacy sqlite behaviour);
  4. ``<repo root>/data/zolai.db``.

Optional dependency (only needed for postgres): ``pip install "psycopg[binary]"``.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = REPO_ROOT / "data" / "zolai.db"

__all__ = [
    "connect",
    "row_to_dict",
    "Row",
    "DbError",
    "DEFAULT_SQLITE_PATH",
    "resolve_url",
]


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


class _PgCursor:
    """Thin cursor wrapper: translates ``?`` → ``%s`` and yields Row objects."""

    def __init__(self, raw: Any, conn: "PgConn") -> None:
        self._raw = raw
        self._conn = conn

    def execute(self, sql: str, params: Iterable[Any] = ()) -> "_PgCursor":
        self._raw.execute(self._conn.translate(sql), tuple(params) if params else None)
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
    def lastrowid(self) -> Any:  # parity helper; use RETURNING id for portability
        return getattr(self._raw, "lastrowid", None)

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

    def __init__(self, conninfo: str) -> None:
        self.conninfo = conninfo
        self._raw: Any = None
        self._module = ""

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
        return sql.replace("?", "%s")

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
        statements = [part.strip() for part in sql.split(";") if part.strip()]
        for statement in statements:
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


def resolve_url(url: str | None = None) -> tuple[str, str]:
    """Return ``(dialect, target)`` per the resolution order in the docstring."""
    env = os.environ.get("ZOLAI_DB_URL", "").strip()
    candidate = ""
    if url and "://" in url:
        candidate = url.strip()
    elif env:
        candidate = env
    elif url:
        raw = str(url).strip()
        if raw != ":memory:":
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = REPO_ROOT / path  # bare relative paths anchor at repo root
            return "sqlite", str(path)
        return "sqlite", raw
    else:
        candidate = f"sqlite:///{DEFAULT_SQLITE_PATH}"

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
            path = str(REPO_ROOT / path)  # sqlite:///relative/… anchors at repo root
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
