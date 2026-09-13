#!/usr/bin/env python3
"""CLI entry point for human syllable annotation.

Usage:
    python -m zolai.syllable.annotation --sample 500 --output data/syllable/gold_human.jsonl
    python scripts/syllable/annotate_gold.py --sample 10 --export conll
"""

import sys
from pathlib import Path

# Add zolai-core to path for imports
zolai_core_path = Path(__file__).parent.parent.parent.parent / "zolai-core"
sys.path.insert(0, str(zolai_core_path))

from zolai.syllable.annotation import main


if __name__ == "__main__":
    sys.exit(main())