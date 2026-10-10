from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .paths import Paths, node_runtime
from .processes import ChildLog, ProcessJob, child_environment, host_command, write_protocol
from .project import Project


@dataclass
class DebugState:
    status: str = "idle"
    pid: int | None = None
    breakpoints: set[int] = field(default_factory=set)
    variables: dict[str, str] = field(default_factory=dict)
    call_stack: list[dict] = field(default_factory=list)
    exit_code: int | None = None
    error: str = ""


class ScriptRunner:
    def __init__(self):
        self.process = None
        self.job = None
        self.state = DebugState()
        self.thread = None
        self.session = ""
        self.lock = threading.RLock()
        self.lines = []
        self.messages = []
        self.stop_requested = False
        self.trace_path = None
        self.log_reader = None

    @property
    def active(self):
        return self.state.status == "starting" or bool(self.thread and self.thread.is_alive())

    def start(self, project, on_line=None, on_done=None, timeout=None, on_message=None,
              debug=False, breakpoints=None, keep_alive=False, events=None):
        if project.manifest['language'] not in {'python','zhxb','javascript','typescript'}:
            raise ValueError('脚本运行器只支持四种脚本语言；通用软件使用系统工具/引擎入口')
        with self.lock:
            if self.active:
                raise RuntimeError("script session already active")
            self.state = DebugState(status="starting")
            self.session = uuid.uuid4().hex
            self.stop_requested = False
            self.thread = threading.Thread(target=self._run, name="pcide-script-supervisor", daemon=False,
                 args=(project, on_line, on_done, timeout, on_message, debug, breakpoints or {}, keep_alive, events or []))
            self.thread.start()

    def _run(self, project, on_line, on_done, timeout, on_message, debug, breakpoints, keep_alive, events):
        session = self.session
        paths = Paths().ensure()
        cache = paths.cache / "sessions"
        cache.mkdir(parents=True, exist_ok=True)
        self.trace_path = cache / f"{session}.jsonl"
        stderr_path = paths.logs / f"script-{session}.log"
        timeout = float(timeout or project.manifest.get("execution", {}).get("timeout_seconds", 60))
        max_lines = int(project.manifest.get("execution", {}).get("max_output_lines", 5000))
        self.lines, self.messages = [], []
        timer = None
        log_exceeded = threading.Event()
        code = 1
        try:
            if project.manifest["language"] in {"python", "zhxb"}:
                command = host_command("worker", "vision" if "vision" in project.manifest.get("modules", []) else "basic")
            else:
                node = node_runtime()
                if not node:
                    raise RuntimeError("Node runtime not configured")
                worker = "worker_bytecode.cjs" if project.entry_path.suffix == ".jsc" else "worker_js.cjs"
                command = [node, str(Path(__file__).with_name(worker))]
            env = child_environment()
            with stderr_path.open("w", encoding="utf-8") as stderr, self.trace_path.open("w", encoding="utf-8") as trace:
                self.process = subprocess.Popen(command, cwd=project.root, env=env, text=True, encoding="utf-8",
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.job = ProcessJob(self.process)
                def log_limit():
                    self.state.error = "script stderr log limit exceeded"
                    log_exceeded.set()
                    if self.job:
                        self.job.close()
                self.log_reader = ChildLog(self.process.stderr, stderr, log_limit)
                self.state.pid, self.state.status = self.process.pid, "running"
                request = {"project": str(project.root), "session": session, "debug": debug,
                           "breakpoints": breakpoints, "keep_alive": keep_alive, "events": events}
                write_protocol(self.process, json.dumps(request), self.job.close)
                if self.stop_requested:
                    self.stop()
                def timed_out():
                    if self.process and self.process.poll() is None:
                        self.state.error = "script timeout"
                        self.state.status = "timeout"
                        self.job.close()
                timer = threading.Timer(timeout, timed_out)
                timer.daemon = True
                timer.start()
                while line := self.process.stdout.readline(65537):
                    if len(line) > 65536:
                        raise RuntimeError("script output record limit exceeded")
                    record = json.loads(line)
                    if record.get("session") != session:
                        continue
                    if len(self.messages) >= max_lines:
                        raise RuntimeError("script output limit exceeded")
                    self.messages.append(record)
                    trace.write(json.dumps(record, ensure_ascii=False) + "\n")
                    trace.flush()
                    kind = record.get("kind")
                    if kind in {"stdout", "stderr"}:
                        self.lines.append(record["text"])
                        if on_line:
                            on_line(record["text"])
                    elif kind == "paused":
                        self.state.status = "paused"
                        self.state.variables, self.state.call_stack = record.get("variables", {}), record.get("stack", [])
                    elif kind == "resumed":
                        self.state.status = "running"
                    elif kind == "error":
                        self.state.error = record.get("message", "worker error")
                    if on_message:
                        on_message(record)
                code = self.process.wait(timeout=3)
                self.log_reader.close()
                if self.log_reader.error and not self.state.error:
                    self.state.error = "script log failed: " + self.log_reader.error
                self.log_reader = None
                if log_exceeded.is_set():
                    code = 1
                if self.state.status == "timeout":
                    code = 124
                elif self.stop_requested:
                    code = 130
                self.state.exit_code = code
                self.state.status = "completed" if code == 0 else "stopped" if code == 130 else "timeout" if code == 124 else "failed"
                if code and not self.state.error and code != 130:
                    self.state.error = stderr_path.read_text(encoding="utf-8")[-8192:] or f"worker exited {code}"
        except BaseException as exc:
            self.state.error, self.state.status = str(exc), "failed"
            self.state.exit_code = code
        finally:
            if timer:
                timer.cancel()
            if self.job:
                self.job.close()
                self.job = None
            if self.process:
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
                for stream in (self.process.stdin, self.process.stdout):
                    if stream:
                        stream.close()
                if self.log_reader:
                    self.log_reader.close()
                    self.log_reader = None
                self.process = None
            if on_done:
                on_done(code, self.state)

    def send(self, command, **values):
        with self.lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("script session is not running")
            payload = json.dumps({"session": self.session, "command": command, **values})
            write_protocol(self.process, payload, self.job.close)

    def event(self, handler, payload=None):
        request_id = uuid.uuid4().hex
        self.send("event", handler=handler, payload=payload or {}, request_id=request_id)
        return request_id

    def stop(self):
        self.stop_requested = True
        if self.process and self.process.poll() is None:
            try:
                self.send("stop")
            except (OSError, RuntimeError):
                pass
            if self.job:
                self.job.close()
            return True
        return False

    def wait(self, timeout=5):
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout)
            if self.thread.is_alive():
                raise TimeoutError("script supervisor did not exit")

    def run_sync(self, project, timeout=60, events=None, debug=False, on_message=None):
        self.start(project, timeout=timeout, events=events, debug=debug, on_message=on_message)
        self.wait(timeout + 8)
        return self.state.exit_code if self.state.exit_code is not None else 1, "".join(self.lines), self.state

    @staticmethod
    def replay(path):
        records = []
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                if len(records) >= 5000:
                    raise ValueError("replay limit exceeded")
                records.append(json.loads(line))
        return records
