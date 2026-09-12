"""Build trilingual dictionary: Zolai → Myanmar → English.

Reads the extracted dalsuum ZO→MY data and joins with the canonical
ZO→EN dictionary to produce:

  data/processed/my/dict_zo_my_v1.jsonl      — ZO→MY (deduplicated)
  data/processed/my/dict_my_zo_v1.jsonl      — MY→ZO (reverse)
  data/processed/my/dict_trilingual_v1.jsonl  — ZO→MY→EN (trilingual)

Usage:
    python build_zo_my_dictionary.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parents[2]  # zolai-ai root

# Input paths
DALSUUM_MY_PATH = (
    WORKSPACE / "data" / "processed" / "my" / "dict_zo_my_dalsuum.jsonl"
)
ZO_EN_MASTER_PATH = (
    WORKSPACE / "data" / "dictionary" / "processed" / "dict_zo_en_master_v1.jsonl"
)

# Output paths
OUTPUT_DIR = WORKSPACE / "data" / "processed" / "my"
ZO_MY_OUT = OUTPUT_DIR / "dict_zo_my_v1.jsonl"
MY_ZO_OUT = OUTPUT_DIR / "dict_my_zo_v1.jsonl"
TRILINGUAL_OUT = OUTPUT_DIR / "dict_trilingual_v1.jsonl"


def load_zo_my() -> dict[str, str]:
    """Load dalsuum ZO→MY, dedup by headword (take first sense)."""
    headwords: dict[str, str] = {}
    if not DALSUUM_MY_PATH.exists():
        print(f"ERROR: {DALSUUM_MY_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(DALSUUM_MY_PATH, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            zw = entry.get("zolai", "")
            my = entry.get("myanmar", "")
            # Only keep first sense per headword
            if zw and my and zw not in headwords:
                headwords[zw] = my
    return headwords


def load_zo_en() -> dict[str, str]:
    """Load canonical ZO→EN master dictionary.

    Returns {zolai_word: english_translation}.
    """
    entries: dict[str, str] = {}
    if not ZO_EN_MASTER_PATH.exists():
        print(f"WARNING: {ZO_EN_MASTER_PATH} not found", file=sys.stderr)
        return entries

    with open(ZO_EN_MASTER_PATH, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            zw = entry.get("zolai", "")
            en = (
                entry.get("english_clean")
                or entry.get("english", "")
            )
            if zw and en and zw not in entries:
                entries[zw] = en
    return entries


def build_outputs(
    zo_my: dict[str, str],
    zo_en: dict[str, str],
) -> None:
    """Write all three output files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. ZO→MY (deduplicated)
    with open(ZO_MY_OUT, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({
                "zolai": zw,
                "myanmar": my,
                "source": "dalsuum",
            }, ensure_ascii=False) + "\n" for zw, my in sorted(zo_my.items()))

    # 2. MY→ZO (reverse)
    with open(MY_ZO_OUT, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({
                "myanmar": my,
                "zolai": zw,
                "source": "dalsuum",
            }, ensure_ascii=False) + "\n" for zw, my in sorted(zo_my.items()))

    # 3. Trilingual ZO→MY→EN
    matched = 0
    with open(TRILINGUAL_OUT, "w", encoding="utf-8") as f:
        for zw, my in sorted(zo_my.items()):
            en = zo_en.get(zw, "")
            if en:
                matched += 1
            f.write(json.dumps({
                "zolai": zw,
                "myanmar": my,
                "english": en,
                "source": "dalsuum+zo_en_master",
            }, ensure_ascii=False) + "\n")

    return matched


def main() -> int:
    print("Building ZO→MY dictionary ...")
    zo_my = load_zo_my()
    print(f"  ZO→MY headwords (deduped): {len(zo_my)}")

    zo_en = load_zo_en()
    print(f"  ZO→EN headwords loaded: {len(zo_en)}")

    matched = build_outputs(zo_my, zo_en)
    print("\nOutputs written:")
    print(f"  {ZO_MY_OUT}  ({len(zo_my)} entries)")
    print(f"  {MY_ZO_OUT}  ({len(zo_my)} entries)")
    print(f"  {TRILINGUAL_OUT}  ({len(zo_my)} entries, {matched} with EN)")

    # Stats
    my_only = len(zo_my) - matched
    coverage_pct = matched / len(zo_my) * 100 if zo_my else 0
    print("\nSummary:")
    print(f"  Trilingual coverage: {matched}/{len(zo_my)} ({coverage_pct:.1f}%)")
    print(f"  ZO+MY only (no EN): {my_only}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
