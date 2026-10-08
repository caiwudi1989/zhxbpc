"""Unity Game SDK bridge.

PCIDE owns Chinese project metadata and generated scripts; Unity owns rendering,
scene serialization, physics, animation and platform builds. The bridge only
touches an explicitly selected Unity project and never imports Unity assemblies
into the IDE process.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class UnityError(ValueError):
    pass

@dataclass(frozen=True)
class UnityProject:
    root: Path
    version: str
    assets: Path
    packages: Path
    settings: Path

def inspect_project(root: str | Path) -> UnityProject:
    path = Path(root).expanduser().resolve()
    assets, packages, settings = path / "Assets", path / "Packages", path / "ProjectSettings"
    if not all(item.is_dir() and not item.is_symlink() for item in (assets, packages, settings)):
        raise UnityError("选择的目录不是完整 Unity 工程（需要 Assets、Packages、ProjectSettings）")
    version = "unknown"
    version_file = settings / "ProjectVersion.txt"
    if version_file.is_file():
        match = re.search(r"m_EditorVersion:\s*([^\s]+)", version_file.read_text(encoding="utf-8", errors="replace"))
        if match: version = match.group(1)
    return UnityProject(path, version, assets, packages, settings)

def generate_monobehaviour(class_name: str, namespace: str = "ZhxbPc.Generated") -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", namespace):
        raise UnityError("Unity C# 类型名或命名空间非法")
    return f'''using UnityEngine;\n\nnamespace {namespace}\n{{\n    public sealed class {class_name} : MonoBehaviour\n    {{\n        [SerializeField] private string zhxbWindow = "MainForm";\n\n        private void Start()\n        {{\n            Debug.Log($"zhxbpc window ready: {{zhxbWindow}}");\n        }}\n\n        private void Update()\n        {{\n        }}\n    }}\n}}\n'''

def write_generated_script(project: UnityProject, class_name: str, content: str | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name):
        raise UnityError("Unity C# 类型名非法")
    if content is not None and (not isinstance(content, str) or len(content.encode("utf-8")) > 2 * 1024 * 1024):
        raise UnityError("Unity 脚本内容为空或超过 2MB")
    generated = (project.assets / "ZhxbPc" / "Generated").resolve()
    if not generated.is_relative_to(project.assets.resolve()):
        raise UnityError("生成目录越界")
    generated.mkdir(parents=True, exist_ok=True)
    target = generated / f"{class_name}.cs"
    if target.exists() and target.is_symlink():
        raise UnityError("生成目标不能是符号链接")
    target.write_text(content if content is not None else generate_monobehaviour(class_name), encoding="utf-8", newline="\n")
    return target

def scene_descriptor(project: UnityProject, scene_name: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", scene_name):
        raise UnityError("Unity 场景名非法")
    matches = sorted(p for p in project.assets.rglob(scene_name + ".unity") if p.is_file() and not p.is_symlink())
    return {"scene": scene_name, "exists": bool(matches), "paths": [p.relative_to(project.root).as_posix() for p in matches[:20]], "unity_version": project.version}

def bridge_manifest(project: UnityProject) -> dict[str, Any]:
    return {"version": 1, "provider": "unity", "unity_version": project.version,
            "assets_root": project.assets.relative_to(project.root).as_posix(),
            "generated_root": "Assets/ZhxbPc/Generated", "transport": "file-contract-v1"}
