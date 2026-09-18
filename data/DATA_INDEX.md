# Zolai datasets — data index

Updated: 2026-09-18

## Manifests (CI)

- [`DATASET_MANIFEST.json`](DATASET_MANIFEST.json) — published HF/Kaggle + local tracked artifacts
- [`ARCHIVE_MANIFEST.json`](ARCHIVE_MANIFEST.json) — source archive inventory (counts from CREDITS)

## Local artifacts

| Path | Role |
|------|------|
| `zolai.db` | SQLite index (may be large; tracked when present) |
| `dictionary/` | Dictionary working tree (optional local) |
| `master_source_v1.jsonl` | Working JSONL (often gitignored via `*.jsonl`) |

## Attribution

See [`../docs/CREDITS.md`](../docs/CREDITS.md). License status: org `credits-license-inventory.md`.
