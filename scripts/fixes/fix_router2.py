import pathlib

router_path = pathlib.Path("/home/ubuntu/pcore/pcore-brain/pcore_brain/router.py")
content = router_path.read_text()

# Find the broken ZOLAI entry and replace it entirely
old = '''    cfg.TASK_ZOLAI: (
        """CRITICAL ZOLAI GRAMMAR — YOU MUST FOLLOW EXACTLY:

1. NEGATION: The ONLY standard negation particle is kei. It works for ALL persons.
   - Ka pai kei hi. (I don't go)
   - Na pai kei hi. (You don't go)
   - A pai kei hi. (He doesn't go)
   - lo is literary/formal only, used alone WITHOUT agreement: Pai lo hi.
   - WRONG: A pai lo hi. (lo never takes `a`)
   - NEVER use si as negation. si is NOT a negation particle.

2. WORD ORDER (SOV):
   - Intransitive: Agreement + Verb → Pai ka hi. (I go)
   - Transitive: Object + Agreement + Verb → Gam ka mu hi. (I see the land)
   - Agreement markers: ka=I, na=you, a=he/she, i=we(incl), ko=we(excl)
   - Agreement comes DIRECTLY before the verb.

3. QUESTIONS:
   - Yes/no: hiam at end → Na pai hiam? (Do you go?)
   - Content: bang hang + verb + subject + hiam → Bang hang pai na hiam? (Why do you go?)
   - What: bang → Na ne bang hiam? (What do you eat?)

4. TENSE:
   - Present: hi → A pai hi.
   - Past: ta → A pai ta hi.
   - Future: ding → A pai ding hi.
   - NOT di/dih/dang (these are wrong)

5. ZVS 2018 CORRECT FORMS:
   - God=Pasian (NOT pathian)
   - earth=leitung (lei+tung, NOT lebung or ram)
   - life=nuntakna (NOT nunnak)
   - holiness=suahtakna (NOT suah)
   - savior=kumpipa (NOT siangpahrang)
   - that=tua (NOT cu/cun)

6. ALWAYS use these correct forms. NEVER use deprecated forms.
7. Provide Bible verse examples for all grammar points."


        "\\n\\n=== ZOLAI WORD GLOSSARY ===\\n"
        + _load_zolai_glossary()
        + "\\n\\nUse the glossary above for ALL translations. Never override these translations."
    )
    ),'''

new = '''    cfg.TASK_ZOLAI: (
        "CRITICAL ZOLAI GRAMMAR — YOU MUST FOLLOW EXACTLY:\\n\\n"
        "1. NEGATION: The ONLY standard negation particle is kei. It works for ALL persons.\\n"
        "   - Ka pai kei hi. (I don't go)\\n"
        "   - Na pai kei hi. (You don't go)\\n"
        "   - A pai kei hi. (He doesn't go)\\n"
        "   - lo is literary/formal only, used alone WITHOUT agreement: Pai lo hi.\\n"
        "   - WRONG: A pai lo hi. (lo never takes a)\\n"
        "   - NEVER use si as negation. si is NOT a negation particle.\\n\\n"
        "2. WORD ORDER (SOV):\\n"
        "   - Intransitive: Agreement + Verb -> Pai ka hi. (I go)\\n"
        "   - Transitive: Object + Agreement + Verb -> Gam ka mu hi. (I see the land)\\n"
        "   - Agreement markers: ka=I, na=you, a=he/she, i=we(incl), ko=we(excl)\\n"
        "   - Agreement comes DIRECTLY before the verb.\\n\\n"
        "3. QUESTIONS:\\n"
        "   - Yes/no: hiam at end -> Na pai hiam? (Do you go?)\\n"
        "   - Content: bang hang + verb + subject + hiam -> Bang hang pai na hiam? (Why?)\\n"
        "   - What: bang -> Na ne bang hiam? (What do you eat?)\\n\\n"
        "4. TENSE:\\n"
        "   - Present: hi -> A pai hi.\\n"
        "   - Past: ta -> A pai ta hi.\\n"
        "   - Future: ding -> A pai ding hi.\\n"
        "   - NOT di/dih/dang (these are wrong)\\n\\n"
        "5. ZVS 2018 CORRECT FORMS:\\n"
        "   - God=Pasian (NOT pathian)\\n"
        "   - earth=leitung (lei+tung, NOT lebung or ram)\\n"
        "   - life=nuntakna (NOT nunnak)\\n"
        "   - holiness=suahtakna (NOT suah)\\n"
        "   - savior=kumpipa (NOT siangpahrang)\\n"
        "   - that=tua (NOT cu/cun)\\n\\n"
        "6. ALWAYS use these correct forms. NEVER use deprecated forms.\\n"
        "7. Provide Bible verse examples for all grammar points.\\n\\n"
        "=== ZOLAI WORD GLOSSARY (DO NOT OVERRIDE) ===\\n"
        + _load_zolai_glossary()
        + "\\n\\nUse the glossary above for ALL translations. Never override these translations."
    ),'''

if old in content:
    content = content.replace(old, new, 1)
    print("Replaced TASK_ZOLAI entry")
else:
    print("ERROR: old text not found, dumping context...")
    # Find TASK_ZOLAI and show it
    idx = content.find("TASK_ZOLAI")
    if idx >= 0:
        print(repr(content[idx:idx+200]))

router_path.write_text(content)
print("Done!")
