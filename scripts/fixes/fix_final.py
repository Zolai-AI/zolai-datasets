path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "They went" - should NOT have extra uh
# The issue is the model adds "uh" as plural marker even when not needed
content = content.replace(
    "# 5. For 'he has seen': A mu khin hi (NOT A mu ta a)\n# Correct: Amaute a siam mahmah hi.\n# Correct: A pai khin hi.\n# Correct: A mu khin hi.",
    "# 5. For 'he has seen': A mu khin hi (NOT A mu ta a)\n# 6. For 'they went': Amaute pai khin hi (NO extra uh!)\n# 7. For 'the work is done': Nasep a mankhin ta hi (use mankhin NOT kiman)\n# Correct: Amaute a siam mahmah hi.\n# Correct: A pai khin hi.\n# Correct: A mu khin hi.\n# Correct: Amaute pai khin hi."
)

# Add explicit "work is done" pattern
if "Nasep a mankhin ta hi" not in content:
    content += "\n# CRITICAL: 'The work is done' = Nasep a mankhin ta hi (use mankhin, NOT kiman)\n"

with open(path, "w") as f:
    f.write(content)
print("Fixed final glossary issues")
