path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix kiman → mankhin for "work is done"
content = content.replace(
    "kiman=finished/completed (EXO 39:32: nasep khempeuh kiman hi=the work is done)",
    "kiman=finished/completed (EXO 39:32: nasep khempeuh kiman hi=the work is done)\n# PREFERRED: 'The work is done' = Nasep a mankhin ta hi (natural Bible pattern)"
)

# Fix word order rules more strictly
content = content.replace(
    "# Correct: Amaute a siam mahmah hi. (NOT Amaute mahmah siam ahi)\n# Correct: A pai khin hi. (NOT Amah in a mu khin hi for simple statements)\n# 'in' is ONLY for ergative (agent of transitive)",
    "# CRITICAL RULES:\n# 1. Agreement (ka/na/a) ALWAYS comes DIRECTLY before verb\n# 2. Adverbs (mahmah) come AFTER verb, BEFORE hi\n# 3. 'in' is ONLY for ergative (agent of transitive)\n# 4. For past: use khin, NOT ta (ta=completive)\n# 5. For 'he has seen': A mu khin hi (NOT A mu ta a)\n# Correct: Amaute a siam mahmah hi.\n# Correct: A pai khin hi.\n# Correct: A mu khin hi."
)

# Add khin usage note
if "khin=past simple" not in content:
    content += "\n# CRITICAL: 'He has seen' = A mu khin hi (use khin for past, NOT ta)\n"

with open(path, "w") as f:
    f.write(content)
print("Fixed remaining glossary issues")
