from __future__ import annotations

import ctypes
import os
import subprocess
import threading
from ctypes import wintypes


class ProcessJob:
    """Windows job owns a process tree; closing it kills all descendants."""

    def __init__(self, process, pid=None):
        self.process = process
        self.handle = None
        self.closed = False
        if os.name != "nt":
            return

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            if handle:
                kernel.CloseHandle(handle)
            raise OSError(ctypes.get_last_error(), "cannot configure child process job")
        process_handle = kernel.OpenProcess(0x0101, False, pid) if pid else wintypes.HANDLE(process._handle)
        assigned = process_handle and kernel.AssignProcessToJobObject(handle, process_handle)
        error = ctypes.get_last_error()
        if pid and process_handle:
            kernel.CloseHandle(process_handle)
        if not assigned:
            kernel.CloseHandle(handle)
            raise OSError(error, "cannot own child process tree")
        self.handle, self.kernel = handle, kernel

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        elif hasattr(self.process, "poll") and self.process.poll() is None:
            self.process.kill()


def host_command(mode: str, profile="basic") -> list[str]:
    import sys
    from .paths import python_runtime
    if getattr(sys, "frozen", False):
        from .paths import Paths
        directory = "project-runtime" if profile == "basic" else f"project-runtime-{profile}"
        console_host = Paths().resources / "runtime/prebuilt" / directory / "PCIDE.Runtime.exe"
        if console_host.is_file():
            return [str(console_host), f"--{mode}"]
        return [sys.executable, f"--{mode}"]
    return [python_runtime(), "-B", "-m", f"pcide.core.{mode}"]


def child_environment():
    import sys
    from pathlib import Path
    from .paths import Paths
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PCIDE_ROOT"] = str(Paths().root)
    typescript = Paths().resources / "sdk/typescript/package/lib/typescript.js"
    if typescript.is_file():
        env["PCIDE_TYPESCRIPT"] = str(typescript)
    dotnet_host = Paths().resources / "runtime/modules/dotnet-host/Pcide.DotNetHost.exe"
    if dotnet_host.is_file():
        env["PCIDE_DOTNET_HOST"] = str(dotnet_host)
    if not getattr(sys, "frozen", False):
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    return env


MAX_CHILD_LOG_CHARS = 1024 * 1024


class ChildLog:
    def __init__(self, stream, target, on_limit):
        self.stream, self.target, self.on_limit = stream, target, on_limit
        self.error = ""
        self.thread = threading.Thread(target=self._read, name="pcide-child-log", daemon=False)
        self.thread.start()

    def _read(self):
        remaining = MAX_CHILD_LOG_CHARS
        try:
            while chunk := self.stream.read(8192):
                self.target.write(chunk[:remaining])
                self.target.flush()
                remaining -= min(len(chunk), remaining)
                if not remaining:
                    self.on_limit()
                    return
        except (OSError, ValueError) as exc:
            self.error = str(exc)

    def close(self):
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("child log reader did not exit")
        self.stream.close()
