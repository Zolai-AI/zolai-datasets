path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add word order rule at top
if "WORD ORDER" not in content:
    content = "# === CRITICAL WORD ORDER RULES ===\n# Agreement (ka/na/a) ALWAYS comes DIRECTLY before verb\n# Adverbs (mahmah) come AFTER verb, before hi\n# Correct: Amaute a siam mahmah hi. (NOT Amaute mahmah siam ahi)\n# Correct: A pai khin hi. (NOT Amah in a mu khin hi for simple statements)\n# 'in' is ONLY for ergative (agent of transitive)\n\n" + content

# Also add nasep a mankhin ta
if "nasep a mankhin" not in content:
    content += "\n# 'The work is done' = Nasep a mankhin ta hi (natural Bible pattern)\n"

with open(path, "w") as f:
    f.write(content)
print("Fixed word order rules")
