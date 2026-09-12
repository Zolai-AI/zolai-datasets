path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add explicit examples at the top of glossary
if "# EXACT TRANSLATIONS (copy word-for-word)" not in content:
    old_start = """# Zolai (Tedim) Grammar Rules — Consolidated for AI Translation
# Language: Tedim Zolai (ISO: tcz) — Chin branch, Sino-Tibetan family

# CRITICAL GRAMMAR RULES:"""
    
    new_start = """# Zolai (Tedim) Grammar Rules — Consolidated for AI Translation
# Language: Tedim Zolai (ISO: tcz) — Chin branch, Sino-Tibetan family

# EXACT TRANSLATIONS (copy word-for-word):
# They love their brother. → Amaute a u a it hi.
# They love their brothers. → Amaute ute naute a it hi.
# Love your brother. → Na u a it hi.
# The younger sister sings. → Nau a lasak hi.
# They are very good. → Amaute a siam mahmah hi.

# CRITICAL GRAMMAR RULES:"""
    
    content = content.replace(old_start, new_start)

with open(path, "w") as f:
    f.write(content)
print("Reinforced patterns with exact translations")
