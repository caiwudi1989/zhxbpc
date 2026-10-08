from __future__ import annotations

import bdb
import ctypes
import importlib.machinery
import json
import os
import queue
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

from .project import Project

MAX_RECORD = 65536
COMMAND_POLL_INTERVAL = 0.05
READER_JOIN_TIMEOUT = 1
ERROR_BROKEN_PIPE = 109


class CommandInput:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.pending = bytearray()
        if os.name == "nt":
            import msvcrt
            self.handle = msvcrt.get_osfhandle(self.fd)
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                                    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                                                    ctypes.POINTER(wintypes.DWORD)]
            self.kernel.PeekNamedPipe.restype = wintypes.BOOL

    def readline(self, cancel=None):
        while True:
            newline = self.pending.find(b"\n")
            if newline >= 0:
                if newline + 1 > MAX_RECORD:
                    raise ValueError("command limit exceeded")
                line = bytes(self.pending[:newline + 1])
                del self.pending[:newline + 1]
                return line.decode("utf-8")
            if len(self.pending) > MAX_RECORD:
                raise ValueError("command limit exceeded")
            if cancel and cancel.is_set():
                return ""
            available = MAX_RECORD + 1 - len(self.pending)
            if os.name == "nt":
                count = wintypes.DWORD()
                if not self.kernel.PeekNamedPipe(wintypes.HANDLE(self.handle), None, 0, None, ctypes.byref(count), None):
                    error = ctypes.get_last_error()
                    if error == ERROR_BROKEN_PIPE:
                        break
                    raise OSError(error, "PeekNamedPipe failed")
                count = count.value
                if not count:
                    if cancel:
                        cancel.wait(COMMAND_POLL_INTERVAL)
                    else:
                        time.sleep(COMMAND_POLL_INTERVAL)
                    continue
                available = min(available, count)
            # A blocked CRT pipe read prevents native extension initialization
            # on Windows. Only read the bytes PeekNamedPipe reported available.
            chunk = os.read(self.fd, available)
            if not chunk:
                break
            self.pending.extend(chunk)
        line = bytes(self.pending)
        self.pending.clear()
        return line.decode("utf-8")


class Worker:
    def __init__(self, request, command_input):
        self.request = request
        self.project = Project.open(request["project"])
        self.session = request["session"]
        self.raw_output = sys.stdout
        self.lock = threading.Lock()
        self.commands = queue.Queue(maxsize=64)
        self.cancel = threading.Event()
        self.input = command_input
        self.input_error = ""
        self.namespace = {"__name__": "__main__", "__file__": str(self.project.entry_path)}
        self.debugger = Debugger(self)
        self.reader = None
        for path, lines in request.get("breakpoints", {}).items():
            for line in lines:
                error = self.debugger.set_break(path, int(line))
                if error:
                    raise ValueError(error)

    def send(self, kind, **values):
        record = json.dumps({"session": self.session, "kind": kind, **values}, ensure_ascii=True, default=str)
        if len(record) > MAX_RECORD:
            raise ValueError("worker record limit exceeded")
        with self.lock:
            self.raw_output.write(record + "\n")
            self.raw_output.flush()

    def read_commands(self):
        try:
            while line := self.input.readline(self.cancel):
                if len(line) > MAX_RECORD:
                    raise ValueError("command limit exceeded")
                command = json.loads(line)
                if command.get("session") != self.session:
                    continue
                if command.get("command") == "stop":
                    self.cancel.set()
                else:
                    try:
                        self.commands.put_nowait(command)
                    except queue.Full:
                        self.send("error", message="worker command queue full", request_id=command.get("request_id"))
            self.cancel.set()
        except Exception as exc:
            self.input_error = str(exc)
            self.send("error", message=str(exc))
            self.cancel.set()

    def start_reader(self):
        if self.reader is None:
            self.reader = threading.Thread(target=self.read_commands, name="worker-command-reader", daemon=False)
            self.reader.start()

    def invoke(self, handler, payload=None):
        callback = self.namespace.get(handler)
        if not callable(callback):
            raise ValueError(f"event handler not found: {handler}")
        if self.request.get("debug"):
            self.debugger.runcall(callback, payload or {})
        else:
            callback(payload or {})

    def run(self):
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout = Output(self, "stdout")
        sys.stderr = Output(self, "stderr")
        from .runtime_api import ui
        ui.transport = lambda message: self.send(message.pop("kind"), **message)
        sys.path.insert(0, str(self.project.root / "src"))
        sys.path.insert(0, str(self.project.root))
        try:
            entry = self.project.entry_path
            if entry.suffix == ".pyc":
                loader = importlib.machinery.SourcelessFileLoader("__main__", str(entry))
                code = loader.get_code("__main__")
            elif self.project.manifest.get("language") == "zhxb":
                from .compiler import emit_python
                code = compile(emit_python(entry.read_text(encoding="utf-8")), str(entry), "exec")
            else:
                code = compile(entry.read_text(encoding="utf-8"), str(entry), "exec")
            if self.request.get("debug"):
                self.debugger.run(code, self.namespace, self.namespace)
            else:
                exec(code, self.namespace, self.namespace)
            if self.request.get("keep_alive"):
                self.start_reader()
            if self.cancel.is_set():
                return 1 if self.input_error else 130
            self.send("ready")
            if self.project.manifest.get("language") == "zhxb":
                self.invoke("__zhxb_entrypoint__")
            for handler in self.request.get("events", []):
                self.invoke(handler)
            if self.request.get("keep_alive"):
                while not self.cancel.is_set():
                    try:
                        command = self.commands.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if command.get("command") == "event":
                        try:
                            self.invoke(command["handler"], command.get("payload", {}))
                            self.send("event.done", request_id=command.get("request_id"))
                        except Exception as exc:
                            self.send("error", message=str(exc), request_id=command.get("request_id"), traceback=traceback.format_exc()[-8192:])
            if self.cancel.is_set():
                self.send("done", ok=False, cancelled=not bool(self.input_error))
                return 1 if self.input_error else 130
            self.send("done", ok=True)
            return 0
        except bdb.BdbQuit:
            self.send("done", ok=False, cancelled=True)
            return 130
        except BaseException as exc:
            self.send("error", message=str(exc), traceback=traceback.format_exc()[-8192:])
            self.send("done", ok=False)
            return 1
        finally:
            self.cancel.set()
            if self.reader:
                self.reader.join(READER_JOIN_TIMEOUT)
            sys.stdout, sys.stderr = original_stdout, original_stderr
            sys.settrace(None)
            self.namespace.clear()
            ui.transport = None
            if self.reader and self.reader.is_alive():
                raise RuntimeError("worker command reader did not exit")


class Output:
    encoding = "utf-8"
    def __init__(self, worker, channel):
        self.worker, self.channel = worker, channel

    def write(self, text):
        if text:
            self.worker.send(self.channel, text=str(text)[:8192])
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


class Debugger(bdb.Bdb):
    """Adapts the legacy trace breakpoint/locals contract onto Python bdb."""
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.enabled = bool(worker.request.get("debug"))

    def dispatch_line(self, frame):
        if self.worker.cancel.is_set():
            self.set_quit()
            raise bdb.BdbQuit()
        return super().dispatch_line(frame)

    def user_line(self, frame):
        path = Path(frame.f_code.co_filename).resolve()
        if not path.is_relative_to(self.worker.project.root) or not self.enabled:
            return
        self.worker.start_reader()
        stack = []
        current = frame
        while current and len(stack) < 32:
            stack.append({"file": current.f_code.co_filename, "line": current.f_lineno, "function": current.f_code.co_name})
            current = current.f_back
        values = {str(k): safe_repr(v) for k, v in list(frame.f_locals.items())[:100] if not str(k).startswith("__")}
        self.worker.send("paused", file=str(path), line=frame.f_lineno, variables=values, stack=stack)
        while not self.worker.cancel.is_set():
            try:
                command = self.worker.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            action = command.get("command")
            if action in {"continue", "step", "next", "out"}:
                if action == "continue":
                    self.set_continue()
                elif action == "step":
                    self.set_step()
                elif action == "next":
                    self.set_next(frame)
                else:
                    self.set_return(frame)
                self.worker.send("resumed")
                return
        self.set_quit()


def safe_repr(value):
    try:
        return repr(value)[:1000]
    except Exception:
        return f"<{type(value).__name__}>"


def main():
    command_input = CommandInput()
    request = json.loads(command_input.readline())
    return Worker(request, command_input).run()


if __name__ == "__main__":
    raise SystemExit(main())
