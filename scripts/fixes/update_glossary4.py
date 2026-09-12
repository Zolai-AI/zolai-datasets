path = "/home/ubuntu/pcore/pcore-brain/context/zolai_glossary.txt"
with open(path) as f:
    content = f.read()

# Add kiman definition if not there
if "kiman" not in content:
    content += "\nkiman=finished/completed (EXO 39:32: nasep khempeuh kiman hi=the work is done)\n"

# Add mankhin definition if not there
if "mankhin" not in content:
    content += "\nmankhin=truly/completed (nasep a mankhin ta hi=the work is truly done)\n"

with open(path, "w") as f:
    f.write(content)
print("Glossary updated with kiman + mankhin")
