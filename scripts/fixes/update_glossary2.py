path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix they pronouns
content = content.replace(
    "u=they (casual)",
    "hihte=they (respectful/older), amaute=they (standard), huate=they (those)\nU=elder (not they!), nau=younger"
)

# Fix nek vs ne
content = content.replace(
    "nek=eat/consume (1CO 8:4,8:7), nekna=eating",
    "nek=eat something specific (with object: sa a nek=eat meat)\nne=eat/drink (general: an ne tui dawnin=eating and drinking)"
)

# Fix nasep vs kammal
content = content.replace(
    "kammal=work/deed",
    "nasep=work/service (1CH 6:31-33)\nkammal=deed/action/commandment (1CH 16:15)"
)

# Fix khin = past simple / experiential
content = content.replace(
    "khin=experiential",
    "khin=past simple / experiential (a pai khin hi=he went/has gone)\nUsed for past actions completed"
)

# Fix past tense examples
content = content.replace(
    "Past: Agreement+Verb+ta+hi -> Ka pai ta hi (I went)",
    "Past: Agreement+Verb+khin+hi -> Ka pai khin hi (I went)\nCompleted: Agreement+Verb+ta+hi -> Ka pai ta hi (it is done)"
)

# Fix they examples
content = content.replace(
    'amaute=they (emphatic), u=they (casual)',
    'hihte=they (respectful/older), amaute=they (standard), huate=they (those)\nU=elder, nau=younger'
)

# Fix "do you eat" example
content = content.replace(
    "Question: Agreement+Verb+hiam -> Na pai hiam? (Do you go?)",
    "Question: Agreement+Verb+hiam -> Na pai hiam? (Do you go?)\nNote: 'Do you eat' = Na ne hiam? (use ne, NOT nek)"
)

with open(path, "w") as f:
    f.write(content)
print("Glossary updated with all corrections")
