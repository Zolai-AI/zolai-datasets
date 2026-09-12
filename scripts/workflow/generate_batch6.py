import os

d = "/home/peter/Documents/Projects/zolai-ai/data/raw/Zomi Worship Collective/"
files = sorted(os.listdir(d))
batch = files[100:120]

# Translation mapping (manually created based on Zolai knowledge)
translations = {
    "Kalvari Cross Kei-a Hi": "I Have the Calvary Cross",
    "Kam A Gen Zawh Hilo": "The Word Cannot Be Completed",
    "Kam Gen Zawh Hi Kei": "The Word Is Not Completed",
    "Kei In Kua": "I Am Called",
    "Kei Lel Hong It": "You Love Me Again",
    "Kei Lel": "You Again",
    "Kei Nang Aa": "You Alone",
    "Kei Nangawn Hong It Hi": "You Alone Love Me",
    "Kei Suakta Zo Ing": "You Have Set Me Free",
    "Kei Tungah Hoih Hi": "You Are Good on Top",
    "Keima Topa Zeisu Lamdang Honpa Hi": "My Lord Jesus Is the Good Shepherd",
    "Kha Siangtho Hong Leeng": "Holy Spirit You Lead",
    "Kha Siangtho Hong Ngai Ing": "Holy Spirit You Praise",
    "Kha Siangtho Tawh": "With Holy Spirit",
    "Kha Siangtho": "Holy Spirit",
    "Khe Khap": "Knock",
    "Khen Tuam Neilo Itna": "Endless Love",
    "Khengval": "Believe",
    "Khrist Hoihna": "Christ's Goodness",
    "Khuavak": "Light"
}

# Read each song and extract lyrics
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
        if line.strip():
            lyrics.append(line)
    songs.append({
        'title': title,
        'lyrics': '\n'.join(lyrics),
        'filename': fname,
        'translation': translations.get(title, title)
    })

# Generate markdown
output_lines = []
output_lines.append("# Zomi Worship Collective — Songs 101–120 Analysis")
output_lines.append("")
output_lines.append("**Source:** `data/raw/Zomi Worship Collective/` (alphabetical, songs 101-120)")
output_lines.append("**Date:** 2026-09-10")
output_lines.append("**ZVS 2018:** All examples use correct orthography — `pasian`, `gam`, `tapa`, `topa`, `kumpipa`, `tua`")
output_lines.append("")
output_lines.append("---")
output_lines.append("")

# Helper function to extract key lines (first 2-3 lines of verse/chorus)
def extract_key_lines(lyrics):
    lines = lyrics.split('\n')
    key_lines = []
    count = 0
    for line in lines:
        if line.startswith('Verse') or line.startswith('Chorus') or line.startswith('Bridge'):
            continue
        if line.strip() and count < 3:
            key_lines.append(line.strip())
            count += 1
    return key_lines

# Process each song
for i, song in enumerate(songs, start=101):
    output_lines.append(f"## Song {i}: {song['title']} — \"{song['translation']}\"")
    output_lines.append("")
    output_lines.append("**Lyrics:**")
    output_lines.append("```")
    output_lines.append(song['lyrics'])
    output_lines.append("```")
    output_lines.append("")
    
    # Key lines table (first 2-3 lines)
    key_lines = extract_key_lines(song['lyrics'])
    if key_lines:
        output_lines.append("**Key Lines:**")
        output_lines.append("")
        output_lines.append("| Line | Word | Gloss |")
        output_lines.append("|------|------|-------|")
        for line in key_lines:
            # Extract first two words as examples
            words = line.split()
            if len(words) >= 2:
                word1 = words[0]
                word2 = words[1] if len(words) > 1 else ""
                output_lines.append(f"| `{line}` | `{word1}` | [gloss] |")
                if word2:
                    output_lines.append(f"| | `{word2}` | [gloss] |")
            else:
                output_lines.append(f"| `{line}` | | |")
        output_lines.append("")
    
    # New vocabulary (placeholder - will be filled manually)
    output_lines.append("**New Vocab:** [to be filled]")
    output_lines.append("**Themes:** [to be filled]")
    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

# Summary table
output_lines.append("## Summary")
output_lines.append("")
output_lines.append("| # | Song | Translation | Key Themes |")
output_lines.append("|---|------|-------------|------------|")
for i, song in enumerate(songs, start=101):
    output_lines.append(f"| {i} | {song['title']} | {song['translation']} | [themes] |")
output_lines.append("")
output_lines.append("**Total new vocabulary:** [count] words across 20 songs")
output_lines.append("**Dominant themes:** [themes]")

# Write to file
output_path = "/home/peter/Documents/Projects/zolai-ai/zolai-wiki/grammar/song_analysis_zomi_worship_batch6.md"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))
print(f"Generated {output_path} with {len(output_lines)} lines")
