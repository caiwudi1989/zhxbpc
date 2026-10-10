"""Versioned source modules with explicit exports and exact dependencies."""
from __future__ import annotations

import re
import keyword
from pathlib import Path

from .paths import read_json


def validate_modules(raw, root):
    if not isinstance(raw, dict) or type(raw.get("version", 1)) is not int or raw.get("version", 1) != 1 or not isinstance(raw.get("modules", []), list) or len(raw.get("modules", [])) > 128:
        raise ValueError("模块清单必须是 version=1、modules 数组")
    result = []
    used = set()
    for source in raw.get("modules", []):
        if not isinstance(source, dict):
            raise ValueError("模块记录必须是对象")
        identity, version, file = source.get("id"), source.get("version"), source.get("file")
        if not isinstance(identity, str) or not identity.isidentifier() or keyword.iskeyword(identity) or identity in used:
            raise ValueError("模块名称无效或重复")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("模块版本必须是 major.minor.patch")
        if not isinstance(file, str) or not file.startswith("src/") or "\\" in file or ":" in file or ".." in Path(file).parts or Path(file).suffix not in {".py", ".zhxb"}:
            raise ValueError("模块源码必须是 src 内的相对 Python/中文源码路径")
        path = Path(root) / file
        if not path.resolve().is_relative_to(Path(root).resolve()) or path.is_symlink() or not (path.is_file() or path.with_suffix(".pyc").is_file()):
            raise ValueError("模块源码缺失或越界")
        exports = source.get("exports", [])
        if not isinstance(exports, list) or len(exports) > 256 or any(not isinstance(name, str) or not name.isidentifier() for name in exports) or len(exports) != len(set(exports)):
            raise ValueError("模块公开接口必须是唯一标识符数组")
        if path.is_file():
            from .routines import scan
            available = {routine['sourceName'] for routine in scan(path.read_text(encoding='utf-8'), path.suffix)}
            if set(exports) - available:
                raise ValueError('模块公开接口不存在: ' + ','.join(sorted(set(exports)-available)))
        dependencies = source.get("dependencies", {})
        if not isinstance(dependencies, dict) or any(not isinstance(name, str) or not isinstance(value, str) for name, value in dependencies.items()):
            raise ValueError("模块依赖必须是名称到精确版本的对象")
        used.add(identity)
        result.append({"id": identity, "version": version, "file": file, "exports": exports, "dependencies": dependencies})
    index = {item["id"]: item for item in result}
    active, done = set(), set()
    def visit(identity):
        if identity in active:
            raise ValueError("模块依赖存在循环: " + identity)
        if identity in done:
            return
        active.add(identity)
        for dependency, version in index[identity]["dependencies"].items():
            if dependency not in index or index[dependency]["version"] != version:
                raise ValueError("模块依赖缺失或版本不符: " + dependency)
            visit(dependency)
        active.remove(identity)
        done.add(identity)
    for identity in index:
        visit(identity)
    return {"version": 1, "modules": result}


def load_modules(project):
    return validate_modules(read_json(project.ide_dir / "modules.json", {}), project.root)
