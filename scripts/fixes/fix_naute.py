path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "ute=brothers" to include "ute naute" pattern
content = content.replace(
    "ute=brothers (plural, 1CO 1:10), naute=younger siblings (plural)",
    "ute=brothers (plural, 1CO 1:10), naute=younger siblings (plural), ute naute=brothers and sisters (1PE 2:17)"
)

# Fix the "they love their brothers" pattern
content = content.replace(
    "#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)",
    "#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)\n#    NOTE: Always use ute naute (NOT just ute) for 'brothers'"
)

with open(path, "w") as f:
    f.write(content)
print("Fixed naute pattern")
