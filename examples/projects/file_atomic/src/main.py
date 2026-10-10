from pathlib import Path
import os
p=Path("resources/settings.txt")
t=p.with_suffix(".tmp")
try:
    t.write_text("version=2",encoding="utf-8")
    os.replace(t,p)
    print(p.read_text(encoding="utf-8"))
finally:
    t.unlink(missing_ok=True)
