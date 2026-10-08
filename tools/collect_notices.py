from __future__ import annotations
import importlib.metadata as metadata
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "docs/licenses"
target.mkdir(exist_ok=True)
inventory = []
for distribution in metadata.distributions():
    name, version = distribution.metadata.get("Name", "unknown"), distribution.version
    if name.lower() in {"pip", "setuptools", "wheel", "websockets"}:
        continue
    notices = []
    for entry in distribution.files or []:
        if ".." in entry.parts:
            continue
        filename = entry.name.lower()
        if not any(filename.startswith(prefix) for prefix in ("license", "copying", "notice", "copyright")):
            continue
        source = Path(distribution.locate_file(entry))
        if source.is_file():
            destination = target / name / Path(str(entry))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            notices.append(destination.relative_to(target).as_posix())
    inventory.append({"name": name, "version": version, "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"), "notices": notices})
(target / "packages.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
for source, name in ((root / "third_party/monaco/LICENSE.txt", "Monaco.txt"), (root / "third_party/bytenode/LICENSE", "Bytenode.txt")):
    shutil.copy2(source, target / name)
print("package notice inventory:", len(inventory), "distributions")
