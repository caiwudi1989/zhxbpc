from __future__ import annotations

import json
import os
import platform
import queue
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .paths import Paths, atomic_write_json, read_json
from .processes import ChildLog, ProcessJob, child_environment, host_command

ALLOWED_KINDS = {"python", "native", "dotnet", "dex-remote"}
PLUGIN_LIMIT = 4
PROTOCOL_LIMIT = 65536


class PluginError(RuntimeError):
    pass


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    kind: str
    entry: str
    capabilities: list[str]
    permissions: list[str]
    architecture: str = "any"
    lifecycle: str = "host-process"
    dependencies: dict[str, str] = field(default_factory=dict)
    api_version: int = 1
    abi: str = "json-v1"
    python_abi: str = "cp312"

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict):
            raise PluginError("plugin manifest must be an object")
        required = {"id", "name", "version", "kind", "entry", "capabilities", "permissions"}
        if required - set(raw):
            raise PluginError(f"missing manifest keys: {sorted(required - set(raw))}")
        if any(not isinstance(raw[key], str) or not raw[key] for key in ("id", "name", "version", "kind", "entry")):
            raise PluginError("plugin identity/name/version/kind/entry must be text")
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", str(raw["id"])):
            raise PluginError("invalid plugin ID")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(raw["version"])):
            raise PluginError("plugin version must be major.minor.patch")
        if raw["kind"] not in ALLOWED_KINDS or raw.get("api_version", 1) != 1:
            raise PluginError("unsupported plugin kind/API version")
        for key in ("capabilities", "permissions"):
            if not isinstance(raw[key], list) or any(not isinstance(v, str) or not v for v in raw[key]):
                raise PluginError(f"{key} must be an array of strings")
        if raw.get("architecture", "any") not in {"x64", "x86", "arm64", "any"}:
            raise PluginError("invalid plugin architecture")
        if not isinstance(raw.get("dependencies", {}), dict):
            raise PluginError("dependencies must map plugin ID to exact version")
        for dependency, version in raw.get("dependencies", {}).items():
            if not isinstance(dependency, str) or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise PluginError("dependency version must be exact major.minor.patch")
        if raw.get("lifecycle", "host-process") != "host-process":
            raise PluginError("unsupported plugin lifecycle")
        entry = Path(raw["entry"])
        if entry.is_absolute() or ".." in entry.parts:
            raise PluginError("plugin entry must stay in its directory")
        return cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw})

    def to_dict(self):
        return self.__dict__.copy()


class PluginSession:
    def __init__(self, manifest, directory, timeout):
        self.manifest = manifest
        self.responses = queue.Queue(maxsize=8)
        self.lock = threading.RLock()
        self.closed = False
        self.closing = False
        paths = Paths().ensure()
        self.log = (paths.logs / f"plugin-{manifest.id}-{uuid.uuid4().hex}.log").open("w", encoding="utf-8")
        if manifest.kind == "dotnet":
            bundled = directory.parent.parent / "runtime/modules/dotnet-host/Pcide.DotNetHost.exe"
            host = bundled if bundled.is_file() else Path(os.environ.get("PCIDE_DOTNET_HOST") or
                paths.resources / "runtime/modules/dotnet-host/Pcide.DotNetHost.exe")
            if not host.exists():
                self.log.close()
                raise PluginError(".NET host unavailable; run tools/build_hosts.py")
            command = [str(host)]
        else:
            command = host_command("plugin_host", "vision" if "vision.real" in manifest.permissions else "basic")
        self.process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", env=child_environment(), bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            self.job = ProcessJob(self.process)
            self.log_reader = ChildLog(self.process.stderr, self.log, self.job.close)
            self.reader = threading.Thread(target=self._read, name=f"plugin-{manifest.id}", daemon=False)
            self.reader.start()
            self.initial = self.request("load", timeout, manifest=manifest.to_dict(), directory=str(directory))
        except BaseException:
            self.close(graceful=False)
            raise

    def _read(self):
        try:
            while line := self.process.stdout.readline(PROTOCOL_LIMIT + 1):
                if len(line) > PROTOCOL_LIMIT:
                    raise PluginError("plugin output record exceeds limit")
                record = json.loads(line)
                self.responses.put(record, timeout=1)
        except Exception as exc:
            try:
                self.responses.put_nowait({"ok": False, "error": str(exc), "fatal": True})
            except queue.Full:
                pass
        finally:
            try:
                self.responses.put_nowait({"ok": False, "error": "plugin host disconnected", "fatal": True})
            except queue.Full:
                pass

    def request(self, command, timeout=5, **values):
        with self.lock:
            if self.closed or self.process.poll() is not None:
                raise PluginError("plugin host is not running")
            request_id = uuid.uuid4().hex
            payload = json.dumps({"id": request_id, "command": command, **values})
            if len(payload) > PROTOCOL_LIMIT:
                raise PluginError("plugin request exceeds limit")
            self.process.stdin.write(payload + "\n")
            self.process.stdin.flush()
            try:
                result = self.responses.get(timeout=timeout)
            except queue.Empty as exc:
                self.close(graceful=False)
                raise PluginError("plugin call timeout; host terminated") from exc
            if result.get("fatal"):
                self.close(graceful=False)
                raise PluginError(result["error"])
            if result.get("id") != request_id:
                self.close(graceful=False)
                raise PluginError("plugin response belongs to a different request")
            if not result.get("ok"):
                raise PluginError(result.get("error", "plugin call failed"))
            return result

    def close(self, graceful=True):
        if self.closed or self.closing:
            return
        self.closing = True
        if graceful and self.process.poll() is None:
            try:
                self.request("shutdown", timeout=1)
            except (PluginError, OSError, ValueError):
                pass
        self.closed = True
        if getattr(self, "job", None):
            self.job.close()
        elif self.process.poll() is None:
            self.process.kill()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if getattr(self, "reader", None) and self.reader is not threading.current_thread():
            self.reader.join(3)
        if getattr(self, "log_reader", None):
            self.log_reader.close()
        errors = []
        for stream in (self.process.stdin, self.process.stdout, self.log):
            if stream:
                try:
                    stream.close()
                except OSError as exc:
                    errors.append(str(exc))
        if errors:
            self.cleanup_error = "; ".join(errors)


class PluginRegistry:
    def __init__(self, project_root, allowed_permissions=None):
        self.root = Path(project_root).resolve()
        self.plugins = {}
        self.sessions = {}
        self.permissions = set(allowed_permissions if allowed_permissions is not None else ["vision.simulated", "native.example"])
        self.lock = threading.RLock()

    def discover(self):
        candidates = {}
        for path in sorted((self.root / "plugins").glob("*/plugin.json")):
            if not path.resolve().is_relative_to(self.root) or path.is_symlink() or path.parent.is_symlink():
                raise PluginError("plugin manifest escapes project")
            manifest = PluginManifest.from_dict(read_json(path))
            if manifest.id in candidates:
                raise PluginError(f"duplicate plugin ID: {manifest.id}")
            entry = (path.parent / manifest.entry).resolve()
            if not entry.is_relative_to(path.parent.resolve()) or not entry.is_file():
                raise PluginError(f"plugin entry missing/escapes directory: {manifest.id}")
            candidates[manifest.id] = (manifest, path.parent)
        self.plugins = candidates
        for manifest, directory in candidates.values():
            for dependency, version in manifest.dependencies.items():
                if dependency not in candidates or candidates[dependency][0].version != version:
                    raise PluginError(f"dependency unavailable: {manifest.id} -> {dependency}@{version}")
        return [m for m, _ in candidates.values()]

    def load(self, plugin_id, timeout=10):
        with self.lock:
            if plugin_id in self.sessions and not self.sessions[plugin_id].closed and self.sessions[plugin_id].process.poll() is None:
                return {**self.sessions[plugin_id].initial, "duplicate": True}
            self.discover()
            if plugin_id not in self.plugins:
                raise PluginError(f"plugin not found: {plugin_id}")
            manifest, directory = self.plugins[plugin_id]
            if set(manifest.permissions) - self.permissions:
                raise PluginError(f"plugin permissions not granted: {sorted(set(manifest.permissions) - self.permissions)}")
            host_arch = "x64" if platform.machine().lower() in {"amd64", "x86_64"} else "arm64" if platform.machine().lower() == "arm64" else "x86"
            if manifest.architecture not in {host_arch, "any"}:
                raise PluginError("plugin architecture does not match host")
            if len([s for s in self.sessions.values() if not s.closed]) >= PLUGIN_LIMIT:
                raise PluginError("plugin host limit reached")
            previous = self.sessions.pop(plugin_id, None)
            if previous:
                previous.close()
            session = PluginSession(manifest, directory, timeout)
            self.sessions[plugin_id] = session
            return session.initial

    def call(self, plugin_id, capability, params=None, timeout=5):
        self.load(plugin_id)
        manifest = self.plugins[plugin_id][0]
        if capability not in manifest.capabilities:
            raise PluginError("capability is not declared by plugin")
        return self.sessions[plugin_id].request("call", timeout, capability=capability, params=params or {})

    def unload(self, plugin_id):
        with self.lock:
            session = self.sessions.pop(plugin_id, None)
            if session:
                try:
                    if not session.closed and session.process.poll() is None:
                        session.request("shutdown", timeout=2)
                finally:
                    session.close()

    def close(self):
        with self.lock:
            for session in list(self.sessions.values()):
                session.close()
            self.sessions.clear()


def write_example_plugins(project_root):
    import shutil
    root = Path(project_root)
    examples = Paths().resources / "examples" / "plugins"
    for name in ("mock_vision", "native_math", "dotnet_math"):
        source = examples / name
        target = root / "plugins" / name
        if source.is_dir() and not target.exists():
            shutil.copytree(source, target)
        modules = Paths().resources / "runtime/modules" / name
        if modules.is_dir():
            for path in modules.rglob("*"):
                destination = target / path.relative_to(modules)
                if path.is_file() and not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)


def write_native_example(project_root):
    write_example_plugins(project_root)
