import os
import re

d = "/home/peter/Documents/Projects/zolai-ai/data/raw/Zomi Worship Collective/"
files = sorted(os.listdir(d))
batch = files[100:120]

songs = []
for fname in batch:
    path = os.path.join(d, fname)
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    lines = content.split('\n')
    # Extract title
    title = None
    for line in lines:
        if line.startswith('Title:'):
            title = line.split(':', 1)[1].strip()
            break
    if not title:
        title = fname.replace('.txt', '')
    # Extract lyrics (skip empty lines and metadata)
    lyrics_lines = []
    in_lyrics = False
    for line in lines:
        if line.startswith('Verse') or line.startswith('Chorus') or line.startswith('Bridge') or line.startswith('Pre-Chorus') or line.startswith('Outro') or line.startswith('Intro') or line.startswith('Ending'):
            in_lyrics = True
        if in_lyrics:
            if line.strip():
                lyrics_lines.append(line.strip())
    # If no lyrics found, use all non-empty lines after title
    if not lyrics_lines:
        after_title = False
        for line in lines:
            if line.startswith('Title:'):
                after_title = True
                continue
            if after_title and line.strip():
                lyrics_lines.append(line.strip())
    # Remove lines that look like metadata
    lyrics = []
    for line in lyrics_lines:
        if 'LyricsDownload' in line:
            continue
        if re.match(r'^[A-Za-z ]+$', line) and len(line) < 20:
            # Could be a section header, keep
            pass
        lyrics.append(line)
    songs.append({
        'title': title,
        'lyrics': '\n'.join(lyrics),
        'filename': fname
    })
    print(f"Processed {fname}: title='{title}', lyrics lines={len(lyrics)}")
