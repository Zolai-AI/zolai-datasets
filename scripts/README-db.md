# Dual-engine database layer (`scripts/db.py`)

Every script in this repo opens its database through `scripts/db.py`, so
switching storage engines is a **configuration change, not a code change**.

## Selecting the engine

| `ZOLAI_DB_URL` | Engine | Driver |
|---|---|---|
| unset (default) | SQLite at `data/zolai.db` | stdlib `sqlite3` (zero-dependency) |
| `sqlite:///path/to/db.sqlite3` | SQLite at an explicit path | stdlib `sqlite3` |
| `postgresql://user:pass@host:5432/db` | PostgreSQL | `psycopg` (v3) |
| `postgres://user:pass@host:5432/db` | PostgreSQL (alias) | `psycopg` (v3) |

```bash
# local / offline (default — nothing to set up)
python3 scripts/dictionary/search_dictionary.py pasian

# against PostgreSQL
export ZOLAI_DB_URL='postgresql://zolai:secret@localhost:5432/zolai'
python3 scripts/dictionary/search_dictionary.py pasian
```

PostgreSQL needs the optional extra (SQLite needs nothing):

```bash
pip install "psycopg[binary]"
```

## Usage from a script

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect, row_to_dict

conn = connect()                       # honours ZOLAI_DB_URL
cur = conn.execute("SELECT * FROM dictionary WHERE zolai = ?", ("pasian",))
row = cur.fetchone()
print(row_to_dict(row))
conn.close()
```

`connect()` is a drop-in replacement for `sqlite3.connect()`: same
`execute / executemany / commit / rollback / close`, same cursor
`fetchone / fetchall / rowcount`, and dict-like rows on **both** engines
(`row["col"]`, `row[0]`, and iteration all work).

## Portability rules (why both engines behave alike)

Scripts are written to a shared SQL subset so the same statement runs on either
engine. `connect()` translates `?` placeholders to `%s` on PostgreSQL
automatically.

- Placeholders are always written `?` — never `%s`, never f-string interpolation.
- Booleans are stored as `INTEGER` 0/1 (not `BOOLEAN`).
- Timestamps are ISO-8601 UTC strings (`2026-10-28T15:23:03+00:00`, `TEXT`);
  **never** `strftime()`, `datetime('now')`, or `CURRENT_TIMESTAMP` in SQL.
- JSON is stored as `TEXT` — no `jsonb` / `JSON1` dependency.
- Upserts use `INSERT … ON CONFLICT (cols) DO UPDATE SET …` (supported by both).
- Only `substr()`, `COALESCE`, and `SUM/COUNT` are used as SQL expressions.
- `PRAGMA journal_mode=WAL`, `busy_timeout`, and `foreign_keys=ON` are applied
  by the SQLite driver only — PostgreSQL enforces FKs by default.

## SQLite-only escape hatch

A few scripts legitimately need SQLite-specific features (virtual tables, FTS,
`PRAGMA` inspection). Where a statement cannot be made portable it is kept on
the SQLite path with an explicit `# sqlite-only` comment so the intent is
visible, rather than silently broken on PostgreSQL.

## Schema / migrations

`scripts/db.py` moves **data**, not schema. For managed schema evolution use
Prisma (`zolai-core/prisma/schema.prisma` is the schema of record) via
`prisma migrate`, or the dedicated migration scripts in `scripts/database/`.
