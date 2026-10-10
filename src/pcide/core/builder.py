from __future__ import annotations

import hashlib
import json
import os
import py_compile
import importlib.util
import marshal
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .paths import BUILD_BYTECODE_CACHE_LIMIT, IDE_VERSION, Paths, atomic_write_json, read_json, sha256_file
from .project import Project
from .package import verify_package

FORBIDDEN_SOURCE = {".py", ".pyi", ".pyx", ".zhxb", ".c", ".cpp", ".h", ".java", ".cs", ".ts", ".js", ".cjs", ".mjs"}
FORBIDDEN_PARTS = {"site-packages", "pip", "pytest", ".venv", "sdk", "downloads", "__pycache__"}
# Bump when the standalone archive layout/compression policy changes so an
# existing artifact cannot be mistaken for one produced by the new packager.
PACKAGING_FORMAT_VERSION = 2

# Customer imports are dynamic, so the frozen hosts explicitly include this
# reviewed general-purpose standard-library surface. External packages still
# use the existing isolated plugin/module contracts.
STANDARD_LIBRARY_IMPORTS = (
    'array', 'base64', 'bisect', 'bz2', 'configparser', 'csv', 'decimal', 'difflib',
    'fractions', 'functools', 'gzip', 'hashlib', 'heapq', 'html.parser', 'http.client',
    'http.server', 'ipaddress', 'itertools', 'logging.handlers', 'lzma', 'math', 'mmap',
    'pathlib', 'pickle', 'queue', 'random', 're', 'selectors', 'shutil', 'socket',
    'sqlite3', 'ssl', 'statistics', 'string', 'struct', 'tarfile', 'threading', 'time',
    'unittest', 'urllib.parse', 'urllib.request', 'uuid', 'xml.etree.ElementTree', 'zipfile', 'zlib',
)

RUNTIME_SOURCE_NAMES = ("paths.py", "project.py", "runner.py", "processes.py", "worker.py", "plugins.py", "compiler.py",
    "plugin_host.py", "dll.py", "dll_host.py", "data.py", "routines.py", "routine_signatures.py", "source.py", "project_sources.py",
    "modules.py", "i18n.py", "runtime_api.py", "package.py", "automation.py", "dex_bridge.py", "flow.py",
    "development.py", "platform.py", "control_catalog.py", "tasks.py", "menus.py")


class BuildError(RuntimeError):
    pass


def valid_bytecode_cache(path):
    stamp = read_json(path.with_suffix(path.suffix + ".json"), {})
    return path.is_file() and stamp.get("sha256") == sha256_file(path)


def record_bytecode_cache(path):
    atomic_write_json(path.with_suffix(path.suffix + ".json"), {"sha256": sha256_file(path)})


def runtime_fingerprint(paths, profile="basic"):
    if getattr(sys, "frozen", False):
        directory = "project-runtime" if profile == "basic" else f"project-runtime-{profile}"
        manifest = read_json(paths.resources / "runtime/prebuilt" / directory / "runtime.json", {})
        return manifest.get("fingerprint", "")
    runtime_names = RUNTIME_SOURCE_NAMES
    if profile == "vision":
        runtime_names += ("vision.py", "label_io.py")
    if profile == "node":
        runtime_names += ("worker_bytecode.cjs", "worker_js.cjs", "compile_js.cjs", "source_contract.cjs")
    files = [paths.src / "pcide/core" / name for name in runtime_names]
    files += [paths.src / "pcide" / "runtime" / "launcher.py", paths.src / "pcide" / "runtime_api.py",
              paths.src / "pcide" / "ui" / "form_runtime.py"]
    digest = hashlib.sha256((IDE_VERSION + sys.implementation.cache_tag + profile + json.dumps(STANDARD_LIBRARY_IMPORTS)).encode())
    for path in sorted(files):
        digest.update(str(path.relative_to(paths.src)).encode())
        digest.update(sha256_file(path).encode())
    return digest.hexdigest()


class BuildManager:
    def __init__(self, paths):
        self.paths = paths.ensure()

    def build(self, project, mode="standalone", cancel=None, force=False):
        if project.manifest['language'] not in {'python', 'zhxb', 'javascript', 'typescript'}:
            raise BuildError('通用软件工程应使用 BuildService 的原生/引擎构建入口')
        def check_cancel():
            if cancel is not None and cancel.is_set():
                raise BuildError('构建已取消')
        check_cancel()
        if os.name != "nt":
            raise BuildError("Windows EXE builds require Windows")
        if mode not in {"directory", "standalone"}:
            raise BuildError("supported EXE modes: standalone and diagnostic directory")
        if not project.entry_path.is_file():
            raise BuildError("project entry missing")
        modules = set(project.manifest.get("modules", []))
        if modules - {"vision"}:
            raise BuildError(f"unknown prebuilt runtime modules: {sorted(modules - {'vision'})}")
        profile = "node" if project.manifest["language"] not in {"python", "zhxb"} else "vision" if "vision" in modules else "basic"
        if profile == "node" and modules:
            raise BuildError("Node runtime does not support the Python vision module")
        directory = "project-runtime" if profile == "basic" else f"project-runtime-{profile}"
        runtime_dir = self.paths.resources / "runtime" / "prebuilt" / directory
        runtime_manifest = read_json(runtime_dir / "runtime.json")
        expected = runtime_fingerprint(self.paths, profile)
        if not runtime_manifest or runtime_manifest.get("fingerprint") != expected:
            raise BuildError("precompiled project runtime missing/stale; run tools/freeze_runtime.py")
        base_exe = runtime_dir / ("PCIDE.Single.exe" if mode == "standalone" else "PCIDE.Runtime.exe")
        if not base_exe.is_file():
            raise BuildError("precompiled runtime EXE missing")
        if not verify_package(runtime_dir, "runtime.json"):
            raise BuildError("precompiled runtime files failed hash verification")
        inputs = project.input_files_for_build()
        from .modules import load_modules
        load_modules(project)
        identities = {p.relative_to(project.root).as_posix(): sha256_file(p) for p in inputs}
        stamp = {"inputs": identities, "runtime": expected, "mode": mode,
                 "packaging": PACKAGING_FORMAT_VERSION}
        fingerprint = hashlib.sha256(json.dumps(stamp, sort_keys=True).encode()).hexdigest()
        target = self.paths.artifacts / project.root.name
        previous = read_json(target / "build.json", {})
        if not force and previous.get("fingerprint") == fingerprint and self.verify(target):
            return {"ok": True, "cache_hit": True, "changed_files": 0, "mode": mode,
                    "artifact": str(target / (project.root.name + ".exe")), "fingerprint": fingerprint}
        stage = self.paths.artifacts / ("_staging-" + uuid.uuid4().hex)
        backup = self.paths.artifacts / ("_backup-" + uuid.uuid4().hex)
        cache = self.paths.build_cache / "bytecode"
        cache.mkdir(parents=True, exist_ok=True)
        changed = []
        form = project.load_form()
        handlers = set()
        for window_path in project.window_paths():
            window_form = project.load_window(window_path)
            handlers.update(window_form["form"].get("events", {}).values())
            handlers.update(h for c in window_form["controls"] for h in c["events"].values())
        handlers = sorted(handlers)
        modified_inputs = [name for name, digest in identities.items() if previous.get("inputs", {}).get(name) != digest]
        removed_inputs = sorted(set(previous.get("inputs", {})) - set(identities))
        try:
            if mode == "directory" and target.is_dir() and previous.get("runtime") == expected and previous.get("mode") == mode and self.verify(target):
                shutil.copytree(target, stage)
            elif mode == "standalone":
                stage.mkdir()
            else:
                shutil.copytree(runtime_dir, stage, ignore=shutil.ignore_patterns("PCIDE.Single.exe"))
                (stage / "PCIDE.Runtime.exe").rename(stage / (project.root.name + ".exe"))
                (stage / "runtime.json").unlink()
            payload = stage / "payload"
            payload.mkdir(parents=True, exist_ok=True)
            outputs = {}
            for source in inputs:
                check_cancel()
                relative = source.relative_to(project.root)
                digest = identities[relative.as_posix()]
                if source.suffix in {".py", ".zhxb"}:
                    destination = payload / relative.with_suffix(".pyc")
                    identity = hashlib.sha256((relative.as_posix() + digest + expected + identities.get('.pcide/data.json', '') + identities.get('.pcide/routines.json', '')).encode()).hexdigest()
                    bytecode = cache / (identity + "-" + sys.implementation.cache_tag + ".pyc")
                    if force or not valid_bytecode_cache(bytecode):
                        if source.is_relative_to(project.root / "src"):
                            from .source import compile_source
                            code = compile_source(source.read_text(encoding="utf-8"), relative.as_posix(),
                                                  metadata=read_json(project.ide_dir / 'routines.json', {}),
                                                  data=project.load_data(), file=relative.as_posix())
                            bytecode.write_bytes(importlib.util.MAGIC_NUMBER + (1).to_bytes(4, 'little') + bytes.fromhex(digest[:16]) + marshal.dumps(code))
                        else:
                            py_compile.compile(str(source), cfile=str(bytecode), dfile=relative.as_posix(), doraise=True)
                        record_bytecode_cache(bytecode)
                    material = bytecode
                elif source.suffix.lower() in {".js", ".ts"} and source.is_relative_to(project.root / "src"):
                    destination = payload / relative.with_suffix(".jsc")
                    identity = hashlib.sha256((relative.as_posix() + digest + json.dumps(handlers) + expected + identities.get('.pcide/data.json', '') + identities.get('.pcide/routines.json', '')).encode()).hexdigest()
                    bytecode = cache / (identity + ".jsc")
                    if force or not valid_bytecode_cache(bytecode):
                        from .paths import node_runtime
                        command = [node_runtime(), str(self.paths.resources / "pcide/core/compile_js.cjs") if getattr(sys, "frozen", False) else str(Path(__file__).with_name("compile_js.cjs")),
                                   str(source), str(bytecode), str(self.paths.resources / "sdk/typescript/package/lib/typescript.js"),
                                   str(self.paths.resources / "third_party/bytenode/index.cjs"), project.manifest["language"], json.dumps(handlers), str(project.root)]
                        from .processes import run_bounded
                        run_bounded(command, cwd=project.root, timeout=30, cancel=cancel,
                                    log_path=self.paths.logs / ("compile-js-" + uuid.uuid4().hex + ".log"))
                        record_bytecode_cache(bytecode)
                    material = bytecode
                elif source.suffix.lower() in FORBIDDEN_SOURCE:
                    raise BuildError(f"source file cannot enter customer payload: {relative}")
                else:
                    destination, material = payload / relative, source
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists() or sha256_file(destination) != sha256_file(material):
                    shutil.copy2(material, destination)
                    changed.append(relative.as_posix())
                outputs[destination.relative_to(payload).as_posix()] = True
            manifest = copy_manifest(project)
            manifest["entry"] = Path(manifest["entry"]).with_suffix(".pyc" if manifest["language"] in {"python", "zhxb"} else ".jsc").as_posix()
            atomic_write_json(payload / ".pcide" / "project.json", manifest)
            public = []
            from .compiler import parse
            for source in project.scripts():
                if source.suffix == '.zhxb':
                    public += [{'public': True, 'file': source.relative_to(project.root).as_posix(), 'sourceName': procedure.name}
                               for procedure in parse(source.read_text(encoding='utf-8')).procedures if procedure.public]
            atomic_write_json(payload / '.pcide/public.json', public)
            outputs['.pcide/public.json'] = True
            for plugin_path in (payload / "plugins").glob("*/plugin.json") if (payload / "plugins").exists() else []:
                plugin = read_json(plugin_path)
                if plugin["kind"] == "python" and Path(plugin["entry"]).suffix == ".py":
                    plugin["entry"] = Path(plugin["entry"]).with_suffix(".pyc").as_posix()
                    atomic_write_json(plugin_path, plugin)
            for old_file in list(payload.rglob("*")):
                if old_file.is_file() and old_file.relative_to(payload).as_posix() not in outputs:
                    old_file.unlink()
            uses_dotnet = any(read_json(path).get("kind") == "dotnet" for path in (payload / "plugins").glob("*/plugin.json"))
            if uses_dotnet:
                module = self.paths.resources / "runtime/modules/dotnet-host"
                if not (module / "Pcide.DotNetHost.exe").is_file():
                    raise BuildError("self-contained .NET plugin host unavailable")
                shutil.copytree(module, payload / "runtime/modules/dotnet-host", dirs_exist_ok=True)
            self.scan(stage)
            if mode == "standalone":
                packaged_files = {p.relative_to(stage).as_posix(): sha256_file(p) for p in payload.rglob("*") if p.is_file()}
                bundle = self.paths.build_cache / ("bundle-" + uuid.uuid4().hex)
                bundle.mkdir()
                try:
                    atomic_write_json(stage / "package.json", {"files": packaged_files})
                    from .archive_bundle import embed_payload
                    embed_payload(base_exe, stage, bundle / (project.root.name + ".exe"), bundle)
                    shutil.rmtree(payload)
                    (stage / "package.json").unlink()
                    shutil.move(str(bundle / (project.root.name + ".exe")), stage)
                finally:
                    shutil.rmtree(bundle)
            hashes = {p.relative_to(stage).as_posix(): sha256_file(p) for p in stage.rglob("*") if p.is_file() and p.name != "build.json"}
            atomic_write_json(stage / "build.json", {"version": 1, "fingerprint": fingerprint,
                "runtime": expected, "mode": mode, "inputs": identities, "files": hashes, "changed": changed})
            check_cancel()
            if target.exists():
                target.rename(backup)
            stage.rename(target)
            if backup.exists():
                shutil.rmtree(backup)
            return {"ok": True, "cache_hit": False, "changed_files": len(modified_inputs) + len(removed_inputs), "changed": modified_inputs,
                    "removed": removed_inputs,
                    "mode": mode, "artifact": str(target / (project.root.name + ".exe")), "fingerprint": fingerprint}
        except Exception:
            if backup.exists() and not target.exists():
                backup.rename(target)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)
            cached_files = sorted(cache.glob("*"), key=lambda p: p.stat().st_mtime)
            cache_bytes = sum(p.stat().st_size for p in cached_files if p.is_file())
            for path in cached_files:
                if cache_bytes <= BUILD_BYTECODE_CACHE_LIMIT:
                    break
                if path.is_file():
                    cache_bytes -= path.stat().st_size
                    path.unlink()

    @staticmethod
    def scan(root):
        violations = []
        for path in root.rglob("*"):
            if path.is_symlink() or any(part in FORBIDDEN_PARTS for part in path.relative_to(root).parts):
                violations.append(str(path))
            reviewed_host = path.suffix == ".cjs" and "payload" not in path.relative_to(root).parts
            if path.is_file() and path.suffix.lower() in FORBIDDEN_SOURCE and not reviewed_host:
                violations.append(str(path))
        if violations:
            raise BuildError(f"forbidden source/development material in package: {violations[:10]}")
        return True

    @staticmethod
    def verify(root):
        return verify_package(root)


def copy_manifest(project):
    return json.loads(json.dumps(project.manifest))
