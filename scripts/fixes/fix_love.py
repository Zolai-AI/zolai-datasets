path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "they love their brother" pattern
content = content.replace(
    "# 9. For 'they love their brother': Amaute a u it hi (simple, direct)",
    "# 9. For 'they love their brother': Amaute a u it hi (simple, direct)\n# Pattern: Subject + a + object + verb + hi"
)

with open(path, "w") as f:
    f.write(content)
print("Fixed love pattern")
