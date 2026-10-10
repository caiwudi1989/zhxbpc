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


def write_protocol(process, payload, on_timeout, timeout=3):
    """A full/stalled Windows pipe must not block the supervising/UI thread."""
    if len(payload) > 65536:
        raise ValueError('child request exceeds protocol limit')
    done = threading.Event()
    errors = []
    def write():
        try:
            process.stdin.write(payload + '\n')
            process.stdin.flush()
        except (OSError, ValueError) as exc:
            errors.append(exc)
        finally:
            done.set()
    writer = threading.Thread(target=write, name='pcide-protocol-writer', daemon=False)
    writer.start()
    if not done.wait(timeout):
        on_timeout()
        writer.join(3)
        raise TimeoutError('child input pipe timeout; host terminated')
    writer.join(3)
    if errors:
        raise errors[0]


class ChildLog:
    def __init__(self, stream, target, on_limit, on_output=None):
        self.stream, self.target, self.on_limit = stream, target, on_limit
        self.on_output = on_output
        self.error = ""
        self.thread = threading.Thread(target=self._read, name="pcide-child-log", daemon=False)
        self.thread.start()

    def _read(self):
        import codecs
        remaining = MAX_CHILD_LOG_CHARS
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        def publish(chunk):
            nonlocal remaining
            value = chunk[:remaining]
            self.target.write(value)
            self.target.flush()
            if self.on_output and value:self.on_output(value)
            remaining -= len(value)
            if not remaining:self.on_limit()
        try:
            # read1 returns available bytes; read(8192) can hide a short prompt
            # until process exit. Incremental decoding preserves split UTF-8.
            while chunk := self.stream.buffer.read1(8192):
                publish(decoder.decode(chunk))
                if not remaining:return
            publish(decoder.decode(b'',final=True))
        except (OSError, ValueError) as exc:
            self.error = str(exc)

    def close(self):
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("child log reader did not exit")
        self.stream.close()


def run_bounded(command, *, cwd, timeout, log_path, cancel=None, environment=None, input_lines=None, on_output=None):
    """Owned tool process with a bounded combined log and deadline."""
    import time
    from pathlib import Path
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(command, cwd=cwd, env=environment or child_environment(),
                               stdin=subprocess.PIPE if input_lines is not None else None, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    job = reader = None
    exceeded = threading.Event()
    try:
        job = ProcessJob(process)
        with log_path.open("w", encoding="utf-8") as log:
            def limit():
                exceeded.set()
                job.close()
            reader = ChildLog(process.stdout, log, limit, on_output)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise RuntimeError("child tool cancelled")
                if time.monotonic() >= deadline:
                    raise TimeoutError("child tool timeout")
                if input_lines is not None:
                    import queue
                    try:
                        line = input_lines.get_nowait()
                    except queue.Empty:
                        pass
                    else:
                        write_protocol(process, line, timeout=1, on_timeout=job.close)
                try:
                    process.wait(timeout=0.05)
                except subprocess.TimeoutExpired:
                    pass
            job.close()
            reader.close()
            reader = None
            if exceeded.is_set():
                raise RuntimeError("child tool output limit exceeded")
            if process.returncode:
                raise RuntimeError(f"child tool exited {process.returncode}; see {log_path}")
        return process.returncode
    finally:
        if job:
            job.close()
        elif process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        if reader:
            reader.close()
        if process.stdin:
            process.stdin.close()
