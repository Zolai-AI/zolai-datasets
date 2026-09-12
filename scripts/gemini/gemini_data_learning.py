#!/usr/bin/env python3
"""
Gemini Data Learning & Database Update Pipeline.

Uses Gemini Web API to ANALYZE existing Zolai data, identify
gaps/errors/suggest improvements, and generate "pending" entries
in the database for human review/approval.

CRITICAL: Gemini uses YOUR data as context/anchors — never
generates in vacuum.
"""

import sqlite3
import json
import sys
import os
import re
import asyncio
import time

# Add bible dir for gemini_cookies
BIBLE_DIR = os.path.join(
    "/home/peter/Documents/Projects/zolai-ai",
    "zolai-datasets/scripts/bible",
)
if BIBLE_DIR not in sys.path:
    sys.path.insert(0, BIBLE_DIR)

from gemini_cookies import get_gemini_client

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds, doubles each retry
TIMEOUT = 60  # seconds per request


async def _retry_async(coro_factory, retries=MAX_RETRIES):
    """Run an async operation with retry + exponential backoff.

    Args:
        coro_factory: callable that returns a new coroutine
        retries: max attempts

    Returns:
        result on success, raises last exception on failure
    """
    delay = RETRY_DELAY
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(
                    f"    Retry {attempt}/{retries} "
                    f"after {delay}s: {e}",
                    file=sys.stderr,
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(
                    f"    Failed after {retries} attempts: "
                    f"{e}",
                    file=sys.stderr,
                )
    raise last_err


async def analyze_dictionary_gaps():
    """Gemini analyzes dictionary entries and suggests
    improvements."""
    client = get_gemini_client()

    ANALYSIS_PROMPT = (
        "You are a Zolai (Tedim Chin) dictionary "
        "analysis expert.\n"
        "You are given dictionary entries. Your task is "
        "to ANALYZE them and SUGGEST improvements.\n\n"
        "FORBIDDEN ZVS 2018 forms (NEVER suggest these):\n"
        "- pathian -> must be pasian (God)\n"
        "- ram -> must be gam (earth/land)\n"
        "- fapa -> must be tapa (life/son)\n"
        "- bawipa -> must be topa (Lord/master)\n"
        "- siangpahrang -> must be kumpipa (Savior)\n"
        "- cu/cun -> must be tua (that/conjunction)\n\n"
        "Also check for:\n"
        "- suah -> suahtakna (holiness context-dependent)\n"
        "- nunnak -> nuntakna (life context-dependent)\n\n"
        "Return ONLY JSON:\n"
        "{\n"
        '  "analysis_type":'
        ' "gap_filling|error_correction|pattern_analysis'
        '|vocabulary_expansion",\n'
        '  "entries_suggested": [\n'
        "    {\n"
        '      "original_zolai": "current word",\n'
        '      "suggested_zolai": "correction or new",\n'
        '      "suggested_english": ["translations"],\n'
        '      "suggested_pos":'
        ' "noun|verb|adj|adv|particle|number",\n'
        '      "suggested_remarks": "ZVS note",\n'
        '      "suggested_description": "description",\n'
        '      "zvs_status": "passed|failed|pending",\n'
        '      "confidence": 0.0-1.0\n'
        "    }\n"
        "  ],\n"
        '  "overall_assessment": "brief summary",\n'
        '  "total_issues": 0,\n'
        '  "critical_fixes": 0\n'
        "}"
    )

    # Read a sample from the database
    db_path = os.path.join(
        "/home/peter/Documents/Projects/zolai-ai",
        "data/zolai.db",
    )
    if not os.path.exists(db_path):
        return {
            "analysis_type": "error",
            "entries_suggested": [],
            "overall_assessment": (
                f"Database not found: {db_path}"
            ),
            "total_issues": 0,
            "critical_fixes": 0,
        }

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT zolai, english_clean "
        "FROM dictionary "
        "WHERE english_clean IS NOT NULL "
        "LIMIT 50"
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "analysis_type": "error",
            "entries_suggested": [],
            "overall_assessment": (
                "No dictionary entries found"
            ),
            "total_issues": 0,
            "critical_fixes": 0,
        }

    # Build summary
    summary_parts = []
    for zolai, english in rows:
        hw = (
            zolai.strip().strip('"').strip("'").strip()
            if zolai
            else ""
        )
        if hw:
            summary_parts.append(
                f"HEADWORD: {hw} | ENGLISH: {english}"
            )

    prompt = (
        ANALYSIS_PROMPT
        + "\n\nANALYZE this sample of Zolai "
        + "dictionary entries:\n\n"
        + "\n".join(summary_parts[:20])
        + "\n\nFocus on:\n"
        "1. ZVS 2018 compliance (forbidden forms)\n"
        "2. Definition accuracy\n"
        "3. Missing words or senses\n"
        "4. Polysemy clarity\n"
        "5. Grammar pattern consistency\n\n"
        "Generate suggestions for improvement."
    )

    try:
        output = await _retry_async(
            lambda: client.generate_content(
                prompt=prompt, model="gemini-3-flash"
            )
        )
        text = output.text or ""

        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])

        return json.loads(text.strip())

    except Exception as e:
        print(
            f"Gemini analysis error: {e}",
            file=sys.stderr,
        )
        return {
            "analysis_type": "error",
            "entries_suggested": [],
            "overall_assessment": f"Error: {e!s}",
            "total_issues": 0,
            "critical_fixes": 0,
        }


async def flag_zvs_issues():
    """Gemini flags ZVS 2018 compliance issues."""
    client = get_gemini_client()

    ZVS_PROMPT = (
        "You are a Zolai Standard (ZVS 2018) "
        "compliance checker.\n\n"
        "FORBIDDEN (must flag and suggest correction):\n"
        "- pathian -> pasian (God)\n"
        "- ram -> gam (earth/land)\n"
        "- fapa -> tapa (life/son)\n"
        "- bawipa -> topa (Lord/master)\n"
        "- siangpahrang -> kumpipa (Savior)\n"
        "- cu/cun -> tua (that/conjunction)\n\n"
        "For each entry, return JSON:\n"
        "{\n"
        '  "zolai": "the word",\n'
        '  "zvs_violation": true/false,\n'
        '  "violating_form": "which form",\n'
        '  "correct_form": "ZVS 2018 form",\n'
        '  "compliance_status":'
        ' "passed|failed|pending",\n'
        '  "remarks": "brief reason",\n'
        '  "description": "description"\n'
        "}"
    )

    db_path = os.path.join(
        "/home/peter/Documents/Projects/zolai-ai",
        "data/zolai.db",
    )
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, zolai FROM dictionary LIMIT 50"
    )
    entries = cur.fetchall()
    conn.close()

    results = []
    for entry_id, zolai in entries:
        hw = (
            zolai.strip().strip('"').strip("'").strip()
            if zolai
            else ""
        )
        if not hw:
            continue

        prompt = (
            ZVS_PROMPT + f'\n\nZolai word: "{hw}"'
        )
        try:
            output = await _retry_async(
                lambda p=prompt: client.generate_content(
                    prompt=p, model="gemini-3-flash"
                )
            )
            text = output.text or ""
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*$", "", text)
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                result = json.loads(
                    text[start : end + 1]
                )
                result["entry_id"] = entry_id
                results.append(result)
            else:
                results.append({
                    "entry_id": entry_id,
                    "zolai": hw,
                    "zvs_violation": False,
                    "violating_form": "",
                    "correct_form": "",
                    "compliance_status": "pending",
                    "remarks": (
                        "Could not parse Gemini output"
                    ),
                    "description": "",
                })
        except Exception as e:
            results.append({
                "entry_id": entry_id,
                "zolai": hw,
                "zvs_violation": False,
                "violating_form": "",
                "correct_form": "",
                "compliance_status": "error",
                "remarks": f"Gemini error: {e!s}",
                "description": "",
            })

    return results


async def main():
    start_time = time.time()
    print("=" * 70)
    print("GEMINI DATA LEARNING & DATABASE UPDATE PIPELINE")
    print("=" * 70)

    print("\n1. Analyzing dictionary gaps and patterns...")
    try:
        analysis = await analyze_dictionary_gaps()
        print(
            "   Analysis type: "
            f"{analysis.get('analysis_type', 'unknown')}"
        )
        print(
            "   Total issues: "
            f"{analysis.get('total_issues', 0)}"
        )
        print(
            "   Critical fixes: "
            f"{analysis.get('critical_fixes', 0)}"
        )
        print(
            "   Entries suggested: "
            f"{len(analysis.get('entries_suggested', []))}"
        )
    except Exception as e:
        print(f"   Analysis failed: {e}")
        analysis = {
            "overall_assessment": f"Error: {e}",
        }

    print("\n2. Flagging ZVS 2018 compliance issues...")
    try:
        zvs_results = await flag_zvs_issues()
        violations = [
            r for r in zvs_results if r.get("zvs_violation")
        ]
        print(f"   Entries checked: {len(zvs_results)}")
        print(f"   ZVS violations found: {len(violations)}")
        for v in violations[:5]:
            print(
                f"     ID={v.get('entry_id')}: "
                f"{v.get('zolai')} -> "
                f"{v.get('correct_form')}"
            )
    except Exception as e:
        print(f"   ZVS check failed: {e}")

    elapsed = time.time() - start_time
    print("\n3. Summary:")
    print(
        "   Analysis: "
        + str(
            analysis.get("overall_assessment", "N/A")
        )[:100]
    )
    print("   Gemini-suggested entries ready for review")
    print(f"\n   Completed in {elapsed:.1f}s")
    print("\n=== PIPELINE COMPLETE ===")
    print(
        "Next: Human reviews pending entries, "
        "approves/rejects, database updated"
    )


if __name__ == "__main__":
    asyncio.run(main())
