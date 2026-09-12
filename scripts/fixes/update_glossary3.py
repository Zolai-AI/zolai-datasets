path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Clarify nek usage
content = content.replace(
    "nek=eat something specific (with object: sa a nek=eat meat)\nne=eat/drink (general: an ne tui dawnin=eating and drinking)",
    "nek=eat something specific (if you eat that: hih na nek leh)\nne=eat/drink (general: Na ne hiam?=Do you eat?, an ne tui dawnin=eating and drinking)\nNote: 'Do you eat' = Na ne hiam? NOT Na nek hiam?"
)

# Fix U definition more clearly
content = content.replace(
    "U=elder (not they!), nau=younger",
    "U=elder (NOT they!), nau=younger\nhihte=they (respectful/older), amaute=they (standard), huate=they (those)\nNote: NEVER use U for 'they'!"
)

# Fix any remaining "uh" or "U" they references
content = content.replace(
    "uh=they (casual)",
    "hihte/amaute/huate=they (NOT uh/U!)"
)

with open(path, "w") as f:
    f.write(content)
print("Glossary updated with nek clarification + U fix")
