path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Remove ALL references to uh = they
content = content.replace("uh=plural marker (3rd person), OR \"they\"", "uh=plural marker (3rd person, e.g. mi+te+uh=people-PL-PL)\nhihte=they (respectful/older)\namaute=they (standard)\nhuate=they (those)")

# Also fix any "uh" in examples that mean "they"
content = content.replace("bawl uh a\"=they are making", "bawl uh a\"=they are making (uh is PL marker)")

with open(path, "w") as f:
    f.write(content)
print("Fixed uh definition")
