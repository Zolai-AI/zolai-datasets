import pathlib

router_path = pathlib.Path("/home/ubuntu/pcore/pcore-brain/pcore_brain/router.py")
with open(router_path) as f:
    lines = f.readlines()

# Find start and end of TASK_ZOLAI entry
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "cfg.TASK_ZOLAI:" in line and start_idx is None:
        start_idx = i
    if start_idx is not None and end_idx is None and i > start_idx:
        # Look for the line with just "),"
        stripped = line.strip()
        if stripped == "),":
            end_idx = i
            break

if start_idx is None or end_idx is None:
    print(f"ERROR: start={start_idx} end={end_idx}")
    import sys; sys.exit(1)

print(f"Found TASK_ZOLAI at lines {start_idx+1}-{end_idx+1}")

new_block = [
    '    cfg.TASK_ZOLAI: (\n',
    '        "CRITICAL ZOLAI GRAMMAR \\u2014 YOU MUST FOLLOW EXACTLY:\\n\\n"\n',
    '        "1. NEGATION: The ONLY standard negation particle is kei. Works for ALL persons.\\n"\n',
    '           "   Ka pai kei hi. (I don\'t go) | Na pai kei hi. (You don\'t go) | A pai kei hi. (He doesn\'t go)\\n"\n',
    '           "   lo is literary/formal only, NO agreement: Pai lo hi. NEVER: A pai lo hi.\\n"\n',
    '           "   NEVER use si as negation.\\n\\n"\n',
    '        "2. WORD ORDER (SOV): Agreement comes DIRECTLY before verb.\\n"\n',
    '           "   Intransitive: Pai ka hi. | Transitive: Gam ka mu hi.\\n"\n',
    '           "   Agreement: ka=I, na=you, a=he/she, i=we, ko=we(excl)\\n\\n"\n',
    '        "3. QUESTIONS: hiam=yes/no, bang hang=why, bang=what, kua=where\\n"\n',
    '           "   Na pai hiam? | Bang hang pai na hiam? | Na ne bang hiam?\\n\\n"\n',
    '        "4. TENSE: hi=present, ta=past, ding=future, zo=completive, lai=progressive\\n\\n"\n',
    '        "5. ZVS 2018: Pasian=God(NOT pathian), leitung=earth(NOT ram/lebung),\\n"\n',
    '           "   tapa=life(NOT fapa), topa=Lord(NOT bawipa), kumpipa=savior(NOT siangpahrang),\\n"\n',
    '           "   suahtakna=holiness(NOT suah), nuntakna=life(NOT nunnak), tua=that(NOT cu/cun)\\n\\n"\n',
    '        "6. ALWAYS use correct forms. Provide Bible verse examples.\\n\\n"\n',
    '        "=== ZOLAI WORD GLOSSARY (DO NOT OVERRIDE) ===\\n"\n',
    '        + _load_zolai_glossary()\n',
    '        + "\\n\\nUse the glossary above for ALL translations."\n',
    '    ),\n',
]

new_lines = lines[:start_idx] + new_block + lines[end_idx+1:]
with open(router_path, "w") as f:
    f.writelines(new_lines)
print(f"Replaced lines {start_idx+1}-{end_idx+1} with {len(new_block)} new lines")
print("Done!")
