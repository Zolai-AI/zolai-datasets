import os

d = "/home/peter/Documents/Projects/zolai-ai/data/raw/Zomi Worship Collective/"
files = sorted(os.listdir(d))
batch = files[100:120]

for i, fname in enumerate(batch, start=101):
    path = os.path.join(d, fname)
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    lines = content.split('\n')
    title = None
    for line in lines:
        if line.startswith('Title:'):
            title = line.split(':', 1)[1].strip()
            break
    if not title:
        title = fname.replace('.txt', '')
    # Extract first 5 non-empty lines after title
    preview = []
    after_title = False
    for line in lines:
        if line.startswith('Title:'):
            after_title = True
            continue
        if after_title and line.strip():
            preview.append(line.strip())
            if len(preview) >= 5:
                break
    print(f"{i}. {title}")
    for p in preview:
        print(f"   {p}")
    print()
