import hashlib
from pathlib import Path
p=Path("resources/hash.txt")
p.write_bytes(b"abc")
h=hashlib.sha256()
with p.open("rb") as f:
    for block in iter(lambda:f.read(8192),b""):
        h.update(block)
print(h.hexdigest())
