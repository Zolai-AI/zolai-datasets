path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix sing definition
content = content.replace(
    "sing=tree/wood (NOT music!, NOT intensifier)",
    "sing=wood (material, NOT tree!)"
)

# Add singkung if not there
if "singkung" not in content:
    content = content.replace(
        "sing=wood (material, NOT tree!)",
        "sing=wood (material, NOT tree!)\nsingkung=tree (living plant)"
    )

# Fix ta definition - it's completive/realized aspect, not just past
content = content.replace(
    "hi=present/declarative, ta=past, ding=future",
    "hi=present/declarative, ta=completive/realized (action completed or happening now), ding=future"
)

# Add ta compound examples
if "hoih ta" not in content:
    content = content.replace(
        "# === INTENSIFIERS ===",
        "# === ta COMPLETIVE/REALIZED ASPECT ===\n# ta marks action as completed or realized in the moment\n# hoih ta=enough/completed, man ta=truly/finished, dam ta=healed, bawl ta=done/made\n# Examples: 'na dam ta in'=be healed (now), 'aman takpi'=truly/truly finished\n\n# === INTENSIFIERS ==="
    )

with open(path, "w") as f:
    f.write(content)
print("Glossary updated with ta aspect + sing/singkung")
