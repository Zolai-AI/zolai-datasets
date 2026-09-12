path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

content = content.replace(
    "hiam=yes/no question marker at sentence end (not ze!)",
    "hiam=yes/no question marker at sentence end (formal), hia=yes/no question marker (informal/spoken)"
)

with open(path, "w") as f:
    f.write(content)
print("Added hia = informal question marker")
