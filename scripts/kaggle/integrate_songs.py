#!/usr/bin/env python3
"""Phase 6: Song Collections — parse all Kaggle song collections into zolai_songs."""
import glob
import os
import re
import sqlite3
import sys

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
SONGS_DIR = "/home/peter/Downloads/Kaggle/Linguistics/Zolai/Literature/Tedim Labu"
KAGGLE_ALL_ZOLAI = (
    "/home/peter/Downloads/Kaggle/resources/agent_knowledge/full_sources/all_zolai"
)


def parse_song_number(filename: str) -> tuple[int, str]:
    """Extract song number and title from filename like 'A AW KA THEI (TDM - 204).txt'"""
    name = os.path.splitext(filename)[0]
    m = re.search(r"TDM\s*-\s*(\d+)", name)
    num = int(m.group(1)) if m else 0
    title = re.sub(r"\s*\(TDM\s*-\s*\d+\)\s*$", "", name).strip()
    return num, title


def _read_part_md(song_dir: str) -> str | None:
    """Read part-0001.md from a song directory, stripping the markdown wrapper."""
    part = os.path.join(song_dir, "part-0001.md")
    if not os.path.isfile(part):
        return None
    with open(part, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    # Strip the '# Full source (part)' header and ``` fences
    lines = []
    in_code = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("# Full source"):
            continue
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped.startswith("#"):
            lines.append(line)
    text = "\n".join(lines).strip()
    return text if text else None


def _extract_title_from_dir(dirname: str, prefix: str, num_strip: bool = False) -> str:
    """Extract human-readable title from directory name.

    prefix examples: 'literature_khanlawnna_late_', 'literature_gospel_'
    If num_strip is True, remove leading '<number>_' from the slug.
    """
    slug = dirname[len(prefix):]
    # Remove trailing '_txt' if present
    slug = re.sub(r"_txt$", "", slug)
    # Optionally strip leading number
    if num_strip:
        slug = re.sub(r"^\d+_", "", slug)
    # Convert underscores to spaces
    title = slug.replace("_", " ").strip()
    return title


def _extract_number_from_dir(dirname: str, prefix: str) -> int:
    """Extract leading number from directory name after prefix."""
    slug = dirname[len(prefix):]
    m = re.match(r"^(\d+)", slug)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Tedim Labu
# ---------------------------------------------------------------------------
def integrate_tedim_labu(conn: sqlite3.Connection, songs_dir: str) -> int:
    """Parse Tedim Labu .txt files (existing)."""
    if not os.path.isdir(songs_dir):
        print(f"  Tedim Labu directory not found: {songs_dir}")
        return 0
    cur = conn.cursor()
    files = [f for f in os.listdir(songs_dir) if f.endswith(".txt")]
    print(f"  Found {len(files)} Tedim Labu files")
    inserted = 0
    for filename in sorted(files):
        num, title = parse_song_number(filename)
        filepath = os.path.join(songs_dir, filename)
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        if not text:
            continue
        cur.execute(
            """INSERT INTO zolai_songs (collection, song_number, title, text, source)
               VALUES (?, ?, ?, ?, ?)""",
            ("Tedim Labu", num, title, text, "kaggle_tedim_labu"),
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Khanlawnna Late
# ---------------------------------------------------------------------------
def integrate_khanlawnna_late(conn: sqlite3.Connection, base_dir: str) -> int:
    """Parse Khanlawnna Late .md files into zolai_songs."""
    prefix = "literature_khanlawnna_late_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Khanlawnna Late directories found in {base_dir}")
        return 0
    print(f"  Found {len(dirs)} Khanlawnna Late directories")
    cur = conn.cursor()
    inserted = 0
    for song_dir in dirs:
        dirname = os.path.basename(song_dir)
        num = _extract_number_from_dir(dirname, prefix)
        title_from_dir = _extract_title_from_dir(dirname, prefix, num_strip=True)
        text = _read_part_md(song_dir)
        if not text:
            continue
        # Prefer title from the file's Title: line
        m = re.search(r"Title:\s*(.+)", text)
        title = m.group(1).strip() if m else title_from_dir
        cur.execute(
            """INSERT INTO zolai_songs (collection, song_number, title, text, source)
               VALUES (?, ?, ?, ?, ?)""",
            ("Khanlawnna Late", num, title, text, "kaggle_khanlawnna_late"),
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Zomi Worship Collective
# ---------------------------------------------------------------------------
def integrate_zomi_worship(conn: sqlite3.Connection, base_dir: str) -> int:
    """Parse Zomi Worship Collective .md files into zolai_songs."""
    prefix = "literature_zomi_worship_collective_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Zomi Worship directories found in {base_dir}")
        return 0
    print(f"  Found {len(dirs)} Zomi Worship directories")
    cur = conn.cursor()
    inserted = 0
    for i, song_dir in enumerate(dirs, 1):
        dirname = os.path.basename(song_dir)
        title_from_dir = _extract_title_from_dir(dirname, prefix, num_strip=False)
        text = _read_part_md(song_dir)
        if not text:
            continue
        m = re.search(r"Title:\s*(.+)", text)
        title = m.group(1).strip() if m else title_from_dir
        cur.execute(
            """INSERT INTO zolai_songs (collection, song_number, title, text, source)
               VALUES (?, ?, ?, ?, ?)""",
            ("Zomi Worship Collective", i, title, text, "kaggle_zomi_worship"),
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Gospel
# ---------------------------------------------------------------------------
def integrate_gospel(conn: sqlite3.Connection, base_dir: str) -> int:
    """Parse Gospel .md files into zolai_songs."""
    prefix = "literature_gospel_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Gospel directories found in {base_dir}")
        return 0
    print(f"  Found {len(dirs)} Gospel directories")
    cur = conn.cursor()
    inserted = 0
    for song_dir in dirs:
        dirname = os.path.basename(song_dir)
        num = _extract_number_from_dir(dirname, prefix)
        title_from_dir = _extract_title_from_dir(dirname, prefix, num_strip=True)
        text = _read_part_md(song_dir)
        if not text:
            continue
        m = re.search(r"Title:\s*(.+)", text)
        title = m.group(1).strip() if m else title_from_dir
        cur.execute(
            """INSERT INTO zolai_songs (collection, song_number, title, text, source)
               VALUES (?, ?, ?, ?, ?)""",
            ("Gospel", num, title, text, "kaggle_gospel"),
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def integrate(db_path: str, songs_dir: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM zolai_songs")
    before = cur.fetchone()[0]

    counts: list[tuple[str, int]] = []

    # 1. Tedim Labu (existing)
    n = integrate_tedim_labu(conn, songs_dir)
    counts.append(("Tedim Labu", n))

    # 2. Khanlawnna Late
    n = integrate_khanlawnna_late(conn, KAGGLE_ALL_ZOLAI)
    counts.append(("Khanlawnna Late", n))

    # 3. Zomi Worship Collective
    n = integrate_zomi_worship(conn, KAGGLE_ALL_ZOLAI)
    counts.append(("Zomi Worship Collective", n))

    # 4. Gospel
    n = integrate_gospel(conn, KAGGLE_ALL_ZOLAI)
    counts.append(("Gospel", n))

    # Audit log
    for coll, cnt in counts:
        if cnt > 0:
            cur.execute(
                """INSERT INTO data_audit_log
                   (table_name, row_id, field, old_value, new_value, changed_at, reason)
                   VALUES ('zolai_songs', 0, 'integrate_kaggle', '',
                           ?, datetime('now'), ?)""",
                ("", f"{coll}: {cnt} songs inserted"),
            )
    conn.commit()

    total = sum(c for _, c in counts)
    print("\nSong integration summary:")
    for coll, cnt in counts:
        print(f"  {coll}: {cnt} songs")
    print(f"  Total: {total} new songs ({before} existing → {before + total} in table)")

    conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    songs = sys.argv[2] if len(sys.argv) > 2 else SONGS_DIR
    integrate(db, songs)
