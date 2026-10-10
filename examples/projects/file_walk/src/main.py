from pathlib import Path
files=[]
for p in Path("src").rglob("*"):
    if p.is_file(): files.append(p.name)
    if len(files)>=100: break
print(sorted(files))
