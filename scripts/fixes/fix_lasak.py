path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Fix lasak definition
content = content.replace(
    "lasa=sing/song, lasak=sing (verb), lasakna=singing/song (1CH 6:31-32)",
    "lasa=sing/song, lasak=sing (verb) OR take something, lasakna=singing/song (1CH 6:31-32)"
)

with open(path, "w") as f:
    f.write(content)
print("Added lasak = take something")
