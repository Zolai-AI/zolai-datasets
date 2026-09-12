#!/usr/bin/env python3
"""Show database statistics from zolai.db — ALL tables."""
import os
import sqlite3
import sys
from pathlib import Path

DB = (
    os.environ.get("DATA", str(Path(__file__).parent.parent.parent / "data"))
    + "/zolai.db"
)

# Emoji map for known tables
EMOJI = {
    "dictionary": "📖",
    "dictionary_en_zo": "📖",
    "bible_verses": "📕",
    "bible_context": "📖",
    "grammar_patterns": "📝",
    "phrases": "💬",
    "translations": "🔄",
    "vocab": "📚",
    "training_exercises": "🎯",
    "training_runs": "🏃",
    "proverbs": "💡",
    "word_alignments": "🔗",
    "word_usage": "📊",
    "word_collocations": "🔗",
    "data_audit_log": "🔍",
    "audit_findings": "🔍",
    "provenance": "📋",
    "wiki_lessons": "📚",
}

# Descriptive labels
LABEL = {
    "dictionary": "Dictionary (ZO→EN)",
    "dictionary_en_zo": "Dictionary (EN→ZO)",
    "bible_verses": "Bible verses",
    "bible_context": "Bible context analysis",
    "grammar_patterns": "Grammar patterns",
    "phrases": "Phrases",
    "translations": "Translation pairs",
    "vocab": "Vocabulary index",
    "training_exercises": "Training exercises",
    "training_runs": "Training runs",
    "proverbs": "Proverbs",
    "word_alignments": "Word alignments",
    "word_usage": "Word usage profiles",
    "word_collocations": "Word collocations",
    "data_audit_log": "Data audit log",
    "audit_findings": "Audit findings",
    "provenance": "Provenance tracking",
    "wiki_lessons": "Wiki lessons",
}


def main() -> None:
    if not os.path.exists(DB):
        print(f"  ❌ Database not found: {DB}")
        sys.exit(1)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ── Header ──
    size_mb = os.path.getsize(DB) / (1024 * 1024)
    print(f"  💾 Database: {size_mb:.1f} MB  📍 {DB}")
    print()

    # ── Dictionary special detail ──
    c.execute("SELECT COUNT(*) FROM dictionary")
    dict_total = c.fetchone()[0]
    c.execute(
        "SELECT COUNT(*) FROM dictionary "
        "WHERE zolai IS NOT NULL AND zolai != ''"
    )
    dict_with_head = c.fetchone()[0]
    c.execute(
        "SELECT COUNT(*) FROM dictionary "
        "WHERE english IS NOT NULL AND english != ''"
    )
    dict_with_en = c.fetchone()[0]
    c.execute(
        "SELECT COUNT(*) FROM dictionary "
        "WHERE entry_version IS NOT NULL AND entry_version != 'v1.0'"
    )
    dict_audited = c.fetchone()[0]
    print(f"  📖 Dictionary (ZO→EN): {dict_total:,} entries")
    print(f"     With headword: {dict_with_head:,}  |  With English: {dict_with_en:,}")
    print(f"     Audit-updated: {dict_audited:,}")
    print()

    # ── Dynamic table listing ──
    c.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name != 'sqlite_sequence' "
        "ORDER BY name"
    )
    tables = [row[0] for row in c.fetchall()]

    total_rows = 0
    for table in tables:
        if table == "dictionary":
            # Already shown above
            total_rows += dict_total
            continue

        c.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = c.fetchone()[0]
        total_rows += count

        emoji = EMOJI.get(table, "📄")
        label = LABEL.get(table, table)

        # Special extras for audit_findings
        if table == "audit_findings" and count > 0:
            c.execute(
                "SELECT finding_type, COUNT(*) FROM audit_findings "
                "GROUP BY finding_type"
            )
            extras = c.fetchall()
            print(f"  {emoji} {label}: {count:,}")
            for ft, cnt in extras:
                print(f"     {ft}: {cnt:,}")
        elif table == "bible_verses" and count > 0:
            c.execute("SELECT COUNT(DISTINCT book) FROM bible_verses")
            books = c.fetchone()[0]
            print(f"  {emoji} {label}: {count:,} verses across {books} books")
        else:
            print(f"  {emoji} {label}: {count:,}")

    # ── Totals ──
    print()
    print(f"  ── Total: {total_rows:,} rows across {len(tables)} tables ──")
    print(f"  💾 Size: {size_mb:.1f} MB  📍 {DB}")

    conn.close()


if __name__ == "__main__":
    main()
