# Zolai Datasets — Architecture

- Scripts: crawlers, data_pipeline, dictionary, cleaner, bible.
- Storage: HF Hub + Kaggle (canonical), local `data/` gitignored mirror. Bulk data lives in the container shared folder at `../data` (6.3G, not a git repo).
- Versioning: timestamped manifest (`data/MANIFEST.json`), HF/Kaggle revision tags.
- Invariants: no large files in git; no secrets; ZVS 2018 compliance.
