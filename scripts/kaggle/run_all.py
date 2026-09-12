#!/usr/bin/env python3
"""Phase 8: Run All — execute the full Kaggle integration pipeline."""
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    ("Phase 1: Schema Migration", "migrate_schema.py"),
    ("Phase 2: Bible Parallel", "integrate_bible_parallel.py"),
    ("Phase 3: Bible Versions", "integrate_bible_versions.py"),
    ("Phase 4: Dictionary Merge", "merge_dictionary.py"),
    ("Phase 5: Corpora", "integrate_corpora.py"),
    ("Phase 6: Songs", "integrate_songs.py"),
    ("Phase 6.5: Convert Lesson PDFs", "convert_pdfs.py"),
    ("Phase 7: Validate", "validate_integration.py"),
]


def main() -> None:
    start = time.time()
    print("=" * 60)
    print("Kaggle Data Integration Pipeline")
    print("=" * 60)

    failed = []
    for label, script in SCRIPTS:
        script_path = os.path.join(SCRIPT_DIR, script)
        print(f"\n{'─' * 60}")
        print(f"▶ {label}")
        print(f"{'─' * 60}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=False,
            text=True,
        )
        if result.returncode != 0:
            failed.append(label)
            print(f"  ❌ FAILED (exit {result.returncode})")
            if "validate" not in script.lower():
                print("  Stopping pipeline.")
                break
        else:
            print("  ✅ DONE")

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Pipeline completed in {elapsed:.1f}s")
    if failed:
        print(f"Failed phases: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All phases passed ✅")


if __name__ == "__main__":
    main()
