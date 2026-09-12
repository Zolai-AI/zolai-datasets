import pathlib

router_path = pathlib.Path("/home/ubuntu/pcore/pcore-brain/pcore_brain/router.py")
content = router_path.read_text()

# Add glossary loader function before _TASK_SYSTEMS
glossary_func = '''_GLOSSARY_CACHE: str | None = None

def _load_zolai_glossary() -> str:
    """Load the Zolai-English glossary from context file."""
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE
    glossary_path = pathlib.Path(__file__).resolve().parent.parent / "context" / "zolai_glossary.txt"
    try:
        _GLOSSARY_CACHE = glossary_path.read_text().strip()
    except Exception:
        _GLOSSARY_CACHE = "(glossary unavailable)"
    return _GLOSSARY_CACHE

'''

# Find _TASK_SYSTEMS and insert before it
import re
m = re.search(r'^_TASK_SYSTEMS', content, re.MULTILINE)
if m:
    content = content[:m.start()] + glossary_func + content[m.start():]
    print("Inserted glossary loader function")
else:
    print("ERROR: Could not find _TASK_SYSTEMS")

# Update the TASK_ZOLAI closing to append glossary
old_end = '7. Provide Bible verse examples for all grammar points."""'
new_end = '''7. Provide Bible verse examples for all grammar points."

        "\\n\\n=== ZOLAI WORD GLOSSARY ===\\n"
        + _load_zolai_glossary()
        + "\\n\\nUse the glossary above for ALL translations. Never override these translations."
    )'''
content = content.replace(old_end, new_end, 1)
print("Updated TASK_ZOLAI to include glossary injection")

router_path.write_text(content)
print("Done!")
