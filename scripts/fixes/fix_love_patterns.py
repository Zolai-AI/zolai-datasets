path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Replace the old love pattern with Bible-verified patterns
old_love = """# 9. For 'they love their brother': Amaute a u itna khin hi
# (Simple, direct, avoids extra words)"""

new_love = """# 9. For 'they love their brother':
#    a. Singular object: Amaute a u a nau a it hi. (1JN 2:10)
#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)
#    c. Future: Amaute a u a nau a it ding hi. (1JN 5:21)
#    d. Negative: Amaute a u a nau a it lo hi. (1JN 3:10)
#    e. Emphatic: Amaute aute ki-it hi. (1TH 4:9)
#    - it = love (verb), itna = love (noun), ki-it = love each other (reflexive)
#    - a u a nau a it = loves his brother (Bible pattern)
#    - ute naute = brothers and sisters (plural)"""

content = content.replace(old_love, new_love)

# Also add a note about the "a u a nau a it" pattern
content = content.replace(
    "# IMPORTANT SOV PATTERN: Agreement marker ALWAYS directly before verb",
    """# IMPORTANT SOV PATTERN: Agreement marker ALWAYS directly before verb
# For 'love brother' use: a u a nau a it (NOT a u itna)"""
)

with open(path, "w") as f:
    f.write(content)
print("Applied love patterns from Bible")
