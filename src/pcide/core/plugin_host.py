from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import json
import os
import struct
import sys
from pathlib import Path

from .plugins import PluginManifest, PROTOCOL_LIMIT


class NativePlugin:
    def __init__(self, entry):
        if os.name != "nt":
            raise RuntimeError("native plugin requires Windows")
        with entry.open("rb") as source:
            data = source.read(4096)
        if len(data) < 64 or data[:2] != b"MZ":
            raise ValueError("plugin is not a Windows PE library")
        offset = struct.unpack_from("<I", data, 0x3c)[0]
        if offset + 6 > len(data) or data[offset:offset + 4] != b"PE\x00\x00":
            raise ValueError("invalid PE header")
        machine = struct.unpack_from("<H", data, offset + 4)[0]
        if machine != 0x8664:
            raise ValueError("example native host requires x64 PE")
        self.search = os.add_dll_directory(str(entry.parent))
        # CDLL uses LoadLibraryEx; attribute lookup uses GetProcAddress.
        self.library = ctypes.CDLL(str(entry), winmode=0x1100)
        self.version = self.library.pcide_abi_version
        self.version.restype = ctypes.c_uint32
        if self.version() != 1:
            raise ValueError("unsupported C ABI")
        self.init = self.library.pcide_init
        self.init.restype = ctypes.c_int
        if self.init() != 0:
            raise RuntimeError("native plugin initialization failed")
        self.call = self.library.pcide_call
        self.call.argtypes = [ctypes.c_char_p]
        self.call.restype = ctypes.c_void_p
        self.shutdown = self.library.pcide_shutdown
        self.shutdown.argtypes = []
        self.shutdown.restype = None

    def invoke(self, request):
        pointer = self.call(json.dumps(request).encode("utf-8"))
        if not pointer:
            raise RuntimeError("native plugin returned null")
        # C ABI requires a NUL-terminated response owned by the plugin until
        # the next call. Copy while the call is serialized in this process.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        output = bytearray()
        for offset in range(PROTOCOL_LIMIT + 1):
            byte = ctypes.c_ubyte()
            if not kernel.ReadProcessMemory(kernel.GetCurrentProcess(), pointer + offset, ctypes.byref(byte), 1, None):
                raise ValueError("native response points to unreadable memory")
            if byte.value == 0:
                break
            output.append(byte.value)
        else:
            raise ValueError("native result too large/unterminated")
        response = output.decode("utf-8")
        result = json.loads(response)
        if not result.get("ok", True):
            raise RuntimeError(result.get("error", "native plugin failed"))
        return result

    def close(self):
        self.shutdown()
        self.search.close()
        # Do not call FreeLibrary. Process exit owns the native module.


def main():
    output = sys.stdout
    plugin = None
    manifest = None
    while line := sys.stdin.readline(PROTOCOL_LIMIT + 1):
        request_id = None
        try:
            if len(line) > PROTOCOL_LIMIT:
                raise ValueError("host request too large")
            request = json.loads(line)
            request_id = request["id"]
            command = request["command"]
            with contextlib.redirect_stdout(sys.stderr):
                if command == "load":
                    manifest = PluginManifest.from_dict(request["manifest"])
                    directory = Path(request["directory"]).resolve()
                    entry = (directory / manifest.entry).resolve()
                    if not entry.is_relative_to(directory):
                        raise ValueError("plugin entry escapes directory")
                    if manifest.kind == "native":
                        plugin = NativePlugin(entry)
                    elif manifest.kind == "python":
                        if manifest.python_abi != f"cp{sys.version_info.major}{sys.version_info.minor}":
                            raise ValueError("Python/pyd ABI does not match host")
                        sys.path.insert(0, str(directory))
                        spec = importlib.util.spec_from_file_location(entry.stem.split('.')[0], entry)
                        plugin = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin)
                        if not callable(getattr(plugin, "plugin_entry", None)):
                            raise ValueError("plugin_entry(request) required")
                    elif manifest.kind == "dex-remote":
                        from .dex_bridge import DexBridge
                        plugin = DexBridge(**json.loads(entry.read_text(encoding="utf-8")))
                        plugin.request("host.describe")
                    else:
                        raise ValueError("plugin requires a different host")
                    result = {"kind": manifest.kind, "plugin": manifest.id, "pid": os.getpid()}
                elif command == "call":
                    if manifest is None or request["capability"] not in manifest.capabilities:
                        raise ValueError("capability not registered")
                    if manifest.kind == "native":
                        result = plugin.invoke(request)
                    elif manifest.kind == "python":
                        result = plugin.plugin_entry(request)
                    else:
                        result = plugin.request(request["capability"], request.get("params", {}))
                elif command == "shutdown":
                    if manifest and manifest.kind == "native":
                        plugin.close()
                    elif callable(getattr(plugin, "plugin_shutdown", None)):
                        plugin.plugin_shutdown()
                    result = {"status": "closed"}
                else:
                    raise ValueError("unsupported plugin command")
            output.write(json.dumps({"id": request_id, "ok": True, "result": result}, ensure_ascii=True) + "\n")
            output.flush()
            if command == "shutdown":
                return 0
        except BaseException as exc:
            output.write(json.dumps({"id": request_id, "ok": False, "error": str(exc)}) + "\n")
            output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
