from contextlib import ExitStack
from pathlib import Path
for name in ["a","b"]: Path("resources/"+name+".txt").write_text(name,encoding="utf-8")
with ExitStack() as stack:
    files=[stack.enter_context(open("resources/"+n+".txt",encoding="utf-8")) for n in ["a","b"]]
    print([f.read() for f in files])
print(all(f.closed for f in files))
