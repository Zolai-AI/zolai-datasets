#!/usr/bin/env python3
"""Phase 6: Song Collections — parse all Kaggle song collections into zolai_songs.

Idempotent: skips songs where (title, collection) already exists in DB.
"""
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
    """Extract number and title from 'A AW KA THEI (TDM - 204).txt'."""
    name = os.path.splitext(filename)[0]
    m = re.search(r"TDM\s*-\s*(\d+)", name)
    num = int(m.group(1)) if m else 0
    title = re.sub(r"\s*\(TDM\s*-\s*\d+\)\s*$", "", name).strip()
    return num, title


def _read_part_md(song_dir: str) -> str | None:
    """Read part-0001.md, stripping markdown wrapper."""
    part = os.path.join(song_dir, "part-0001.md")
    if not os.path.isfile(part):
        return None
    with open(part, encoding="utf-8", errors="replace") as f:
        raw = f.read()
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


def _extract_title_from_dir(
    dirname: str, prefix: str, num_strip: bool = False
) -> str:
    """Extract human-readable title from directory name."""
    slug = dirname[len(prefix):]
    slug = re.sub(r"_txt$", "", slug)
    if num_strip:
        slug = re.sub(r"^\d+_", "", slug)
    return slug.replace("_", " ").strip()


def _extract_number_from_dir(dirname: str, prefix: str) -> int:
    """Extract leading number from directory name after prefix."""
    slug = dirname[len(prefix):]
    m = re.match(r"^(\d+)", slug)
    return int(m.group(1)) if m else 0


def _load_existing(cur: sqlite3.Cursor) -> set[tuple[str, str]]:
    """Load all (title, collection) pairs already in DB."""
    cur.execute("SELECT title, collection FROM zolai_songs")
    return {(row[0], row[1]) for row in cur.fetchall()}


def _insert_if_new(
    cur: sqlite3.Cursor,
    seen: set[tuple[str, str]],
    collection: str,
    num: int,
    title: str,
    text: str,
    source: str,
) -> bool:
    """Insert song only if (title, collection) not already present."""
    key = (title, collection)
    if key in seen:
        return False
    cur.execute(
        """INSERT INTO zolai_songs
           (collection, song_number, title, text, source)
           VALUES (?, ?, ?, ?, ?)""",
        (collection, num, title, text, source),
    )
    seen.add(key)
    return True


# ---------------------------------------------------------------------------
# Tedim Labu
# ---------------------------------------------------------------------------
def integrate_tedim_labu(
    conn: sqlite3.Connection, songs_dir: str, seen: set[tuple[str, str]]
) -> int:
    """Parse Tedim Labu .txt files."""
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
        if _insert_if_new(cur, seen, "Tedim Labu", num, title, text,
                          "kaggle_tedim_labu"):
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Khanlawnna Late
# ---------------------------------------------------------------------------
def integrate_khanlawnna_late(
    conn: sqlite3.Connection, base_dir: str, seen: set[tuple[str, str]]
) -> int:
    """Parse Khanlawnna Late .md files into zolai_songs."""
    prefix = "literature_khanlawnna_late_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Khanlawnna Late dirs found in {base_dir}")
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
        m = re.search(r"Title:\s*(.+)", text)
        title = m.group(1).strip() if m else title_from_dir
        if _insert_if_new(cur, seen, "Khanlawnna Late", num, title, text,
                          "kaggle_khanlawnna_late"):
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Zomi Worship Collective
# ---------------------------------------------------------------------------
def integrate_zomi_worship(
    conn: sqlite3.Connection, base_dir: str, seen: set[tuple[str, str]]
) -> int:
    """Parse Zomi Worship Collective .md files into zolai_songs."""
    prefix = "literature_zomi_worship_collective_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Zomi Worship dirs found in {base_dir}")
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
        if _insert_if_new(cur, seen, "Zomi Worship Collective", i, title, text,
                          "kaggle_zomi_worship"):
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Gospel
# ---------------------------------------------------------------------------
def integrate_gospel(
    conn: sqlite3.Connection, base_dir: str, seen: set[tuple[str, str]]
) -> int:
    """Parse Gospel .md files into zolai_songs."""
    prefix = "literature_gospel_"
    pattern = os.path.join(base_dir, prefix + "*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        print(f"  No Gospel dirs found in {base_dir}")
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
        if _insert_if_new(cur, seen, "Gospel", num, title, text,
                          "kaggle_gospel"):
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

    before = cur.execute("SELECT count(*) FROM zolai_songs").fetchone()[0]
    seen = _load_existing(cur)
    print(f"Existing songs: {before} ({len(seen)} unique title+collection keys)")

    counts: list[tuple[str, int]] = []
    counts.append(("Tedim Labu",
                    integrate_tedim_labu(conn, songs_dir, seen)))
    counts.append(("Khanlawnna Late",
                    integrate_khanlawnna_late(conn, KAGGLE_ALL_ZOLAI, seen)))
    counts.append(("Zomi Worship Collective",
                    integrate_zomi_worship(conn, KAGGLE_ALL_ZOLAI, seen)))
    counts.append(("Gospel",
                    integrate_gospel(conn, KAGGLE_ALL_ZOLAI, seen)))

    for coll, cnt in counts:
        if cnt > 0:
            cur.execute(
                """INSERT INTO data_audit_log
                   (table_name, row_id, field, old_value, new_value,
                    changed_at, reason)
                   VALUES ('zolai_songs', 0, 'integrate_kaggle', '',
                           ?, datetime('now'), ?)""",
                ("", f"{coll}: {cnt} songs inserted"),
            )
    conn.commit()

    total = sum(c for _, c in counts)
    after = cur.execute("SELECT count(*) FROM zolai_songs").fetchone()[0]
    print("\nSong integration summary:")
    for coll, cnt in counts:
        print(f"  {coll}: {cnt} new")
    print(f"  Total: {total} new songs ({before} -> {after} in table)")

    conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    songs = sys.argv[2] if len(sys.argv) > 2 else SONGS_DIR
    integrate(db, songs)
