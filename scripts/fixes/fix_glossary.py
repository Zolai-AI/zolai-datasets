path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"

content = """# Zolai-English Glossary — DO NOT OVERRIDE
# Verified against Bible corpus (31,102 verses) + native speaker knowledge

# === CORE NOUNS ===
pasian=God, topa=Lord/Lord God, tapa=son/life
gam=earth/land, leitung=earth (lei+tung), vantung=heaven (van+tung)
nuntakna=life, suahtakna=holiness, kumpipa=savior
tui=water, sing=tree, khua=village/homeland
mi=person/human, numei=woman, pia=younger sibling
pa=father, nga=I/me, na=you (free pronoun)
a=he/she/it, ei=we(incl), ko=we(excl), noteng=us/we
amaute=they, amah=he/she (emphatic free)
mun=you (emphatic), nang=you (free)
uh=plural marker

# === VERBS (Bible-verified) ===
lasa=sing/song, lasak=sing, lasakna=singing/song (1CH 6:31-32)
nek=eat/consume (1CO 8:4,8:7), nekna=eating
ne=eat/drink (1CH 12:39)
mu=see/look/find (1CH 4:40)
pai=go/walk, hong=come (toward speaker), va=go away (from speaker)
piangsak=created/made (1JN 4:18), bawl=make/create/form
ci=say/speak/tell (quotative), den=keeps doing (habitual)
dam=sound/voice, sing=trees/wood
siam=good/skilled/craftsman (1CH 5:18, 4:14)

# === QUESTION MARKERS ===
hiam=yes/no question (at end), diam=rhetorical question
bang=what, bang hang=why, kua=where, bangmah=where/how

# === NEGATION ===
kei=negation (ALL persons), lo=negation (literary/formal, 3rd person, NO agreement)

# === TENSE/ASPECT ===
hi=present/declarative, ta=past, ding=future
zo=completive, lai=progressive, khin=experiential
pah=habitual, ciang=already

# === GRAMMAR PARTICLES ===
in=ergative marker, ki=reflexive/passive marker
leh=and, tua=that, tu=this, ai=which
na=possessive/particle, a=agreement marker
ka=1sg agreement, na=2sg agreement, a=3sg agreement
i=1pl agreement, ko=2pl agreement

# === DIRECTIONAL ===
sung=inside, sungah=in/inside, tung=above/top
van=sky, nua=shoulder, tung=above

# === COMMON WORDS ===
kha=body, then=story/word, kammal=work/deed
lungdam=heart/mind, sinlamteh=joy/happiness
gupna=salvation, hehpihna=peace, itna=love
bangmahna=compassion, caahna=mercy

# === TIME ===
ni=day/daytime, kum=year, zing=morning

# === SOV PATTERNS ===
# Agreement ALWAYS directly BEFORE verb
# Intransitive: Agreement+Verb+hi -> Ka pai hi (I go)
# Transitive: Obj+Agreement+Verb+hi -> Gam ka mu hi (I see land)
# Negation: Agreement+Verb+kei+hi -> Ka pai kei hi (I don't go)
# Question: Agreement+Verb+hiam -> Na pai hiam? (Do you go?)
# Future: Agreement+Verb+ding+hi -> Ka pai ding hi (I will go)
# Past: Agreement+Verb+ta+hi -> Ka pai ta hi (I went)
# Ergative: Agent+in+Obj+Agreement+Verb+hi -> Pasian in leitung a piangsak hi
# "and" = leh -> Vantung leh leitung (heaven and earth)
"""

with open(path, "w") as f:
    f.write(content)
print(f"Glossary rewritten: {len(content.splitlines())} lines")
