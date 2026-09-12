import pathlib

router_path = pathlib.Path("/home/ubuntu/pcore/pcore-brain/pcore_brain/router.py")
with open(router_path) as f:
    content = f.read()

# Add pathlib import
if "import pathlib" not in content:
    content = content.replace(
        "import re\n",
        "import pathlib\nimport re\n",
        1,
    )
    print("Added pathlib import")
else:
    print("pathlib already imported")

# Fix the glossary function to use os.path instead (more reliable)
old_func = '''def _load_zolai_glossary() -> str:
    """Load the Zolai-English glossary from context file."""
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE
    glossary_path = pathlib.Path(__file__).resolve().parent.parent / "context" / "zolai_glossary.txt"
    try:
        _GLOSSARY_CACHE = glossary_path.read_text().strip()
    except Exception:
        _GLOSSARY_CACHE = "(glossary unavailable)"
    return _GLOSSARY_CACHE'''

new_func = '''def _load_zolai_glossary() -> str:
    """Load the Zolai-English glossary from context file."""
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE
    import os as _os
    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _path = _os.path.join(_base, "context", "zolai_glossary.txt")
    try:
        with open(_path) as _f:
            _GLOSSARY_CACHE = _f.read().strip()
    except Exception:
        _GLOSSARY_CACHE = "(glossary unavailable)"
    return _GLOSSARY_CACHE'''

content = content.replace(old_func, new_func, 1)
print("Fixed glossary function")

with open(router_path, "w") as f:
    f.write(content)
print("Saved!")
