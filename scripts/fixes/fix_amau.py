path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix "they love their brother" pattern - remove extra amau
content = content.replace(
    "# 9. For 'they love their brother':\n#    a. Singular object: Amaute a u a nau a it hi. (1JN 2:10)\n#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)\n#    NOTE: Always use ute naute (NOT just ute) for 'brothers'",
    """# 9. For 'they love their brother':
#    a. Singular object: Amaute a u a nau a it hi. (1JN 2:10)
#    b. Plural object: Amaute ute naute a it hi. (1PE 2:17)
#    c. Future: Amaute a u a nau a it ding hi. (1JN 5:21)
#    d. Negative: Amaute a u a nau a it lo hi. (1JN 3:10)
#    e. Emphatic: Amaute aute ki-it hi. (1TH 4:9)
#    - it = love (verb), itna = love (noun), ki-it = love each other (reflexive)
#    - a u a nau a it = loves his brother (Bible pattern)
#    - ute naute = brothers and sisters (plural)
#    - DO NOT add extra 'amau' after Amaute!"""
)

with open(path, "w") as f:
    f.write(content)
print("Fixed amau issue")
