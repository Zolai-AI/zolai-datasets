path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add sanggam forms
content = content.replace(
    "u=elder brother/sister (1JN 2:9: a u a nau=his brother), nau=younger brother/sister",
    "u=elder brother/sister (1JN 2:9), nau=younger brother/sister, sanggam=brother/companion (560x Bible), sanggampa=his brother (217x), sanggamte=brothers plural (214x), sanggamnu=sister (84x)"
)

content = content.replace(
    "ute=brothers (plural, 1CO 1:10), naute=younger siblings (plural), ute naute=brothers and sisters (1PE 2:17)",
    "ute=brothers (plural, 1CO 1:10), naute=younger siblings (plural), ute naute=brothers and sisters (1PE 2:17), sanggamte=brothers/companions (plural, 214x Bible)"
)

# Update love patterns to include sanggam
content = content.replace(
    "# 9. For 'they love their brother':",
    """# 9. For 'they love their brother':
#    a. sanggam: Amaute a sanggam a it hi. (general brother/companion)
#    b. u (elder): Amaute a u a nau a it hi. (1JN 2:10)
#    c. sanggamte (plural): Amaute a sanggamte a it hi."""
)

with open(path, "w") as f:
    f.write(content)
print("Added sanggam to glossary")
