"""Validate all canonical schemas against real data files."""
import os
import sys
sys.path.insert(0, "/home/peter/Documents/Projects/zolai-ai/zolai-core")

from zolai.data.schemas import validate_file, CANONICAL_SCHEMAS

DATA_ROOT = "/home/peter/Documents/Projects/zolai-ai/data"

for filename, (schema, subdir) in CANONICAL_SCHEMAS.items():
    path = os.path.join(DATA_ROOT, subdir, filename)
    if os.path.exists(path):
        result = validate_file(path, schema, max_errors=3)
        print(result.summary())
        print()
    else:
        print(f"SKIP: {path} not found")
        print()
