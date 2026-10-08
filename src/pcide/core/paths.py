from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

IDE_VERSION = "0.1.0"
BUILD_BYTECODE_CACHE_LIMIT = 512 * 1024 * 1024


class Paths:
    """Single source for source, runtime, cache, and output boundaries."""

    def __init__(self, root: str | Path | None = None) -> None:
        if getattr(sys, "frozen", False):
            executable_root = Path(sys.executable).resolve().parent
            config_path = executable_root / "PCIDE.config.json"
            config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
            fallback = executable_root / config.get("workspace", ".")
        else:
            fallback = Path(__file__).resolve().parents[3]
        configured = root or os.environ.get("PCIDE_ROOT") or fallback
        self.root = Path(configured).resolve()
        self.resources = Path(getattr(sys, "_MEIPASS", self.root))
        self.src = self.root / "src"
        self.docs = self.root / "docs"
        self.tests = self.root / "tests"
        self.projects = self.root / "projects"
        self.assets = self.root / "assets"
        self.runtime = self.root / "runtime"
        self.cache = self.root / "cache"
        self.build = self.root / "build"
        self.logs = self.cache / "logs"
        self.build_cache = self.cache / "build"
        self.artifacts = self.build / "artifacts"

    def ensure(self) -> "Paths":
        for path in (self.src, self.docs, self.tests, self.projects, self.assets,
                     self.runtime, self.cache, self.build, self.logs,
                     self.build_cache, self.artifacts):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def project(self, name: str) -> Path:
        safe = "".join(c for c in name.strip() if c.isalnum() or c in "-_ ").strip()
        safe = safe.replace(" ", "_") or "untitled"
        return self.projects / safe

    def rel(self, path: str | Path) -> str:
        return str(Path(path).resolve().relative_to(self.root))


def atomic_write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def read_json(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((p for p in paths if p.is_file()), key=lambda p: str(p).lower()):
        digest.update(str(path.name).encode("utf-8"))
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def python_runtime() -> str:
    configured = os.environ.get("PCIDE_PYTHON")
    local = Paths().runtime / "dev" / "Scripts" / "python.exe"
    return configured or (str(local) if local.is_file() else sys.executable)


def node_runtime() -> str | None:
    configured = os.environ.get("PCIDE_NODE")
    if configured and Path(configured).exists():
        return configured
    local = Paths().resources / "runtime" / "node" / "node.exe"
    if local.exists():
        return str(local)
    from shutil import which
    return which("node")
