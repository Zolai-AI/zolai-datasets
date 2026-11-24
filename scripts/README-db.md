# `scripts/db.py` — dual-engine database access

Every data script connects through **one** helper:

```python
from db import connect, row_to_dict   # scripts/db.py bootstraps sys.path for you

conn = connect(DB_PATH)               # legacy sqlite path stays the fallback
```

With the default configuration (nothing set) this opens `DB_PATH` as SQLite —
behavior is byte-for-byte what `sqlite3.connect(DB_PATH)` did before, plus
WAL, `foreign_keys=ON`, a busy timeout, and dict-like rows (`sqlite3.Row`).

## Switching engines: `ZOLAI_DB_URL`

Switching to PostgreSQL is a **configuration change, not a code change**.
When `ZOLAI_DB_URL` is set it takes precedence over the path each script
passes:

```bash
# SQLite (default — same URLs the scripts already use internally)
export ZOLAI_DB_URL="sqlite:///data/zolai.db"          # relative to repo root
export ZOLAI_DB_URL="sqlite:////srv/zolai/zolai.db"    # absolute (4 slashes)

# PostgreSQL (psycopg v3 recommended; psycopg2 also detected)
export ZOLAI_DB_URL="postgresql://zolai:secret@localhost:5432/zolai"
export ZOLAI_DB_URL="postgres://zolai:secret@db.internal/zolai"   # alias
```

Resolution order for `connect(url=...)`: explicit URL containing `://` →
`ZOLAI_DB_URL` → bare path argument (sqlite, anchored at repo root when
relative) → `sqlite:///data/zolai.db` at repo root.

Optional dependency (postgres only — nothing else is added to the repo):

```bash
pip install "psycopg[binary]"
```

## What the wrapper gives you

| API | sqlite | postgres |
|-----|--------|----------|
| `conn.execute(sql, params)` | native cursor | `?` rewritten to `%s` |
| `conn.executemany(sql, seq)` | native | translated |
| `conn.cursor()` / `with conn:` | native | translating cursor, same tx semantics |
| `conn.fetchone/fetchall(sql, params)` | convenience | convenience |
| `conn.commit/rollback/close` | native | native |
| `conn.executescript(sql)` | native | split on `;` (DDL bootstrap only) |
| `conn.dialect` | `"sqlite"` | `"postgres"` |
| rows | `sqlite3.Row` | `db.Row` (key **and** index access) |
| `row_to_dict(row)` | works | works |

## Portability rules (same as `zolai-tts/src/zolai_tts/db/drivers.py`)

- write placeholders as `?`; the helper rewrites them to `%s` for postgres;
- booleans as INTEGER `0/1`; timestamps as ISO-8601 UTC TEXT; JSON as TEXT;
- upserts via `INSERT … ON CONFLICT (…) DO UPDATE SET …`;
- no `strftime()`/`datetime()` SQL — format timestamps in Python;
- only `substr()`, `COALESCE`, and aggregates in SQL expressions.

## Known sqlite-only pockets

The connection layer is engine-neutral; a few **schema/DDL maintenance**
scripts (`database/regenerate_db.py`, `online/migrate_schema.py`,
`dictionary/build_dictionary_db.py`, `database/clean_database.py`, and
similar) still contain `AUTOINCREMENT`, `INSERT OR REPLACE/IGNORE`, or
`PRAGMA` statements. They run under the default sqlite engine; when operating
on PostgreSQL, apply the schema out-of-band (org pattern: the Prisma schema in
`zolai-core/prisma/schema.prisma` is the schema-of-record) and keep these
scripts as sqlite tooling. Nothing else changed: scripts that only read/write
rows work on either engine.

`scripts/bible/menu.sh` embeds small `sqlite3.connect()` snippets in shell
heredocs and is intentionally left as-is (interactive sqlite tooling).
