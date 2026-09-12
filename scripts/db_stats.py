#!/usr/bin/env python3
"""Show database statistics from zolai.db."""
import sqlite3, os, sys
from pathlib import Path

DB = os.environ.get("DATA", str(Path(__file__).parent.parent.parent / "data")) + "/zolai.db"

try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM dictionary")
    dict_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dictionary WHERE zolai IS NOT NULL AND zolai != ''")
    dict_with_head = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dictionary WHERE english IS NOT NULL AND english != ''")
    dict_with_en = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dictionary WHERE entry_version IS NOT NULL AND entry_version != 'v1.0'")
    dict_audited = c.fetchone()[0]
    print(f"  📖 Dictionary: {dict_total:,} entries")
    print(f"     With headword: {dict_with_head:,} | With English: {dict_with_en:,}")
    print(f"     Audit-updated: {dict_audited:,}")
    print()

    c.execute("SELECT COUNT(*) FROM bible_verses")
    bible_verses = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT book) FROM bible_verses")
    bible_books = c.fetchone()[0]
    print(f"  📕 Bible: {bible_verses:,} verses across {bible_books} books")

    c.execute("SELECT COUNT(*) FROM word_alignments")
    print(f"  🔗 Word alignments: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM grammar_patterns")
    print(f"  📝 Grammar patterns: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM phrases")
    print(f"  💬 Phrases: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM translations")
    print(f"  🔄 Translation pairs: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM vocab")
    print(f"  📚 Vocabulary: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM training_exercises")
    print(f"  🎯 Training exercises: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM proverbs")
    print(f"  💡 Proverbs: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM audit_findings")
    audit = c.fetchone()[0]
    if audit > 0:
        c.execute("SELECT finding_type, COUNT(*) FROM audit_findings GROUP BY finding_type")
        print(f"  🔍 Audit findings: {audit:,}")
        for ft, cnt in c.fetchall():
            print(f"     {ft}: {cnt:,}")

    c.execute("SELECT COUNT(*) FROM word_usage")
    print(f"  📊 Word usage profiles: {c.fetchone()[0]:,}")

    c.execute("SELECT COUNT(*) FROM bible_context")
    print(f"  📖 Bible context analysis: {c.fetchone()[0]:,}")

    size_mb = os.path.getsize(DB) / (1024*1024)
    print(f"\n  💾 Database size: {size_mb:.1f} MB")
    print(f"  📍 Path: {DB}")
    conn.close()
except Exception as e:
    print(f"  ❌ Error: {e}")
