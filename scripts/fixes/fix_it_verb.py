path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add verb form "it" = love
content = content.replace(
    "sinlamteh=joy, gupna=salvation, hehpihna=peace, itna=love",
    "sinlamteh=joy, gupna=salvation, hehpihna=peace, it=love (verb), itna=love (noun), ki-it=love each other"
)

with open(path, "w") as f:
    f.write(content)
print("Added verb form 'it' = love")
