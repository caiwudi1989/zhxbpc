import json
from pathlib import Path
p=Path("resources/data.json")
p.write_text(json.dumps({"名字":"软件","版本":1},ensure_ascii=False),encoding="utf-8")
print(json.loads(p.read_text(encoding="utf-8")))
