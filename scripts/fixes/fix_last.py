path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "love your brother" imperative pattern - ensure "hi" not "in"
content = content.replace(
    "na=possessive marker (your, my, his, her, its, their), na=quotative marker (say, that), na=that (relative clause)",
    "na=possessive marker (your, my, his, her, its, their), na=quotative marker (say, that), na=that (relative clause)\n# IMPORTANT: Imperative uses 'hi' not 'in' for love verb. Na u a it hi! NOT Na u it in!"
)

with open(path, "w") as f:
    f.write(content)
print("Fixed last 2 issues")
