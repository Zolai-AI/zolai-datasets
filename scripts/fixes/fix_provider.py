import re

path = "/home/peter/Documents/Projects/zolai-ai/zolai-datasets/scripts/gemini_zolai_provider.py"
with open(path) as f:
    content = f.read()

# Fix import path
content = content.replace(
    "from bible.gemini_cookies import get_gemini_client",
    """# Add scripts dir to path for gemini_cookies import
import os as _os
_scripts_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
if _os.path.join(_scripts_dir, 'bible') not in sys.path:
    sys.path.insert(0, _os.path.join(_scripts_dir, 'bible'))
from gemini_cookies import get_gemini_client"""
)

with open(path, 'w') as f:
    f.write(content)
print("Fixed provider imports")
