path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "they love their brothers" pattern
content = content.replace(
    "#    b. Plural object: Amaute ute a it hi. (1PE 2:17)",
    "#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)"
)

with open(path, "w") as f:
    f.write(content)
print("Fixed brothers pattern")
