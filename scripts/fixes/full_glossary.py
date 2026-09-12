content = """# Zolai-English Glossary — Verified against Bible corpus (31,102 verses)
# Polysemous words have MULTIPLE meanings listed

# === HIGH-FREQUENCY PARTICLES (polysemous) ===
in=ergative marker (agent of transitive), OR "in/to" (directional)
leh=and (conjunction), OR return/reciprocate (context-dependent)
na=possessive particle (your/my), OR quotative connector ("na cih"=that/saying), OR "new/fresh"
tawh=with (comitative), OR key, OR "free-hand" (multiple meanings)
kei=negation "not" (ALL persons), OR "I/me" (1st person pronoun in dialect)
lo=literary negation (NO agreement after verb, standalone only)
ahi=copula "is/am/are/was" (context-dependent)
ci=say/speak/tell (quotative verb, most frequent verb 1,048x)
hi=declarative particle (end of statement), OR "yes" (response)
uh=plural marker (3rd person), OR "they"
a=agreement marker (3rd sg before verb), OR possessive "his/her/its"
ka=1st person agreement (I), OR 1sg pronoun
na=2nd person agreement (you), OR possessive particle
ding=future marker "will", OR "direction/way"
ka=1st person agreement marker (before verb)

# === DIRECTIONAL PARTICLES ===
hong=toward speaker (come here), OR "toward/at" (directional)
va=away from speaker (go away), OR "down" (directional)
khia=exit/out, OR "open"
lut=enter/in, OR "descend"
kik=return/back, OR "again"
kiangah=toward/to (general directional)
tungah=above/on top of (directional)

# === VERBS (Bible-verified) ===
lasa=sing/song, lasak=sing (verb), lasakna=singing/song (1CH 6:31-32)
nek=eat/consume (1CO 8:4,8:7), nekna=eating
ne=eat/drink (1CH 12:39: "an ne tui dawnin"=eating and drinking)
mu=see/look/find (1CH 4:40: "nopna mun mu uh hi"=found pasture)
pai=go/walk, piak=go/leave
bawl=make/create/form (1CH 9:30: "bawl uh a"=they are making)
piangsak=created/made (1JN 4:18: "piangsak thei"=can be made)
ci=say/speak/tell (quotative)
dam=sound/voice, OR healthy/healed (polysemous: "na dam ta in"=be healed)
siam=good/skilled/craftsman (1CH 5:18: "gal a siam"=skillful in war)
gen=speak/talk, gena=speech
om=exist/be present/be located
hih=be/exist (copula)
pia=give, piah=give (directional)
ngah=get/receive/win
kiangah=toward/to (with directional)
ngen=beg/ask/request
sung=inside, sungah=in/inside

# === NOUNS ===
pasian=God, topa=Lord, tapa=son/life
gam=earth/land, leitung=earth (lei+tung), vantung=heaven (van+tung)
nuntakna=life, suahtakna=holiness, kumpipa=savior
tui=water, sing=tree/wood (NOT music!), khua=village/homeland
mi=person/human, numei=woman, num=man/male
pa=father, ma=mother, tapa=son
kha=body, then=story/word/thought
kammal=work/deed, lungdam=heart/mind
sinlamteh=joy, gupna=salvation, hehpihna=peace, itna=love
bangmahna=compassion, caahna=mercy
lah=book/document, laisiangtho=Bible
inn=house/household, biakinn=temple/church
kumpipa=savior, sangna=cross
ni=day/daytime, kum=year, zing=morning

# === QUESTION MARKERS ===
hiam=yes/no question (at end of sentence)
diam=rhetorical question (expected answer already known)
bang=what, bang hang=why, kua=where, bangmah=where/how

# === TIME/ASPECT ===
hi=present/declarative, ta=past, ding=future
zo=completive, lai=progressive, khin=experiential
pah=habitual, ciang=already (then/at that time as ciangin)

# === PRONOUNS ===
nga=I/me (free), na=you (free), amah=he/she/it (emphatic free)
mun=you (emphatic), nang=you (free form)
ei=we(incl), ko=we(excl), noteng=us/we
amaute=they (emphatic), u=they (casual)
ki=reflexive/passive marker

# === CONJUNCTIONS/CONNECTORS ===
leh=and, tua=that, tu=this, ai=which
ahih=but/however, banah=therefore
manin=so/thus, hangin=because/since
bangin=whereas/as, ciangin=when/after

# === SOV PATTERNS ===
# Agreement ALWAYS directly BEFORE verb
# Intransitive: Subject+Agreement+Verb+hi -> Ka pai hi (I go)
# Transitive: Object+Agreement+Verb+hi -> Gam ka mu hi (I see land)
# Negation: Agreement+Verb+kei+hi -> Ka pai kei hi (I don't go)
# Question: Agreement+Verb+hiam -> Na pai hiam? (Do you go?)
# Future: Agreement+Verb+ding+hi -> Ka pai ding hi (I will go)
# Past: Agreement+Verb+ta+hi -> Ka pai ta hi (I went)
# Ergative: Agent+in+Object+Agreement+Verb+hi -> Pasian in leitung a piangsak hi
# Quotative: ...," a ci hi -> ...," he/she said.
"""

with open("/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt", "w") as f:
    f.write(content)
print(f"Glossary rewritten: {len(content.splitlines())} lines")
