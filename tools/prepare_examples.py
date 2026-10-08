from __future__ import annotations
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths
from pcide.core.project import Project

paths = Paths(root).ensure()
for name, language in (("JavaScriptDemo", "javascript"), ("TypeScriptDemo", "typescript")):
    target = paths.project(name)
    project = Project.open(target) if (target / ".pcide/project.json").exists() else Project.create(paths, name, language)
    if name == "TypeScriptDemo" and "const typedValue" not in project.entry_path.read_text(encoding="utf-8"):
        project.entry_path.write_text("const typedValue: number = 42;\nconsole.log(typedValue);\n" + project.entry_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(project.root)
