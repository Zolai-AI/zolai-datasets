path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "Nau a lasak hi" pattern - agreement must be before verb
content = content.replace(
    "lasa=sing/song, lasak=sing (verb) OR take something, lasakna=singing/song (1CH 6:31-32)",
    "lasa=sing/song, lasak=sing (verb) OR take something, lasakna=singing/song (1CH 6:31-32)\n# Pattern: Nau a lasak hi (She sings) — agreement 'a' before verb"
)

# Fix "They love their brother" pattern
content = content.replace(
    "# 7. For 'the work is done': Nasep a mankhin ta hi (use mankhin, NOT kiman)\n# Correct: Amaute a siam mahmah hi.\n# Correct: A pai khin hi.\n# Correct: A mu khin hi.\n# Correct: Amaute pai khin hi.",
    "# 7. For 'the work is done': Nasep a mankhin ta hi (use mankhin, NOT kiman)\n# 8. For 'the younger sister sings': Nau a lasak hi (agreement 'a' before verb)\n# 9. For 'they love their brother': Amaute a u it hi (simple, direct)\n# Correct: Amaute a siam mahmah hi.\n# Correct: A pai khin hi.\n# Correct: A mu khin hi.\n# Correct: Amaute pai khin hi."
)

with open(path, "w") as f:
    f.write(content)
print("Fixed last 2 translation issues")
