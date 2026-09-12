path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add mahmah = very/indeed and fix sing
if "mahmah" not in content:
    content = content.replace(
        "# === QUESTION MARKERS ===",
        "# === INTENSIFIERS ===\nmahmah=very/indeed (intensifier)\ntampi=many/much\nkim=not yet\n\n# === QUESTION MARKERS ==="
    )

# Fix sing definition
content = content.replace(
    "sing=tree/wood (NOT music!)",
    "sing=tree/wood (NOT music!, NOT intensifier)"
)

with open(path, "w") as f:
    f.write(content)
print("Added mahmah, fixed sing")
