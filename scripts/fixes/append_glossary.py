import os
path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
append = """
# SOV PATTERNS — Agreement BEFORE verb
# Intransitive: Agreement+Verb+hi -> Pai ka hi (I go)
# Transitive: Obj+Agreement+Verb+hi -> Gam ka mu hi (I see land)
# Negation: Agreement+Verb+kei+hi -> Ka pai kei hi (I don't go)
# Question: Agreement+Verb+hiam -> Na pai hiam? (Do you go?)
# Future: Agreement+Verb+ding+hi -> Ka pai ding hi (I will go)
# Past: Agreement+Verb+ta+hi -> Ka pai ta hi (I went)
# Ergative: Agent+in+Object+Agreement+Verb+hi -> Pasian in leitung a piangsak hi
# "and" = leh -> Vantung leh leitung (heaven and earth)
# "I" = ka, "you" = na, "he/she" = a, "we" = i/ko, "they" = amaute
# Agreement ALWAYS directly BEFORE verb, NEVER after verb
"""
with open(path, "a") as f:
    f.write(append)
print("SOV patterns appended!")
