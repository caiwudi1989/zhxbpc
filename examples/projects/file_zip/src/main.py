from pathlib import Path
from zipfile import ZipFile
p=Path("resources/sample.zip")
with ZipFile(p,"w") as z:
    z.writestr("readme.txt","hello")
with ZipFile(p) as z:
    print(z.read("readme.txt").decode())
