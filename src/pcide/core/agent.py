"""Bounded, resumable AI coding-agent core for the PC IDE.

The module is provider-neutral: an LLM/OpenHands adapter supplies decisions,
while this layer owns sessions, tool contracts, workspace safety and the event
timeline. No model SDK is imported into the IDE process.
"""
from __future__ import annotations

import ast
import json
import threading
import os
import tempfile
import uuid
import hashlib
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

class AgentState(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class AgentError(RuntimeError):
    pass

@dataclass(frozen=True)
class AgentEvent:
    kind: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    mutating: bool = False
    requires_approval: bool = False
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False})

@dataclass(frozen=True)
class AgentTask:
    prompt: str
    project_root: str
    approved_paths: frozenset[str] = frozenset()
    max_steps: int = 32
    timeout_seconds: float = 900.0
    allow_writes: bool = False

@dataclass(frozen=True)
class AgentResult:
    session_id: str
    state: AgentState
    reply: str
    events: tuple[AgentEvent, ...]
    changes: tuple[dict[str, Any], ...] = ()

class WorkspaceGuard:
    def __init__(self, root: str | Path, approved_paths: set[str] | frozenset[str] = ()):
        self.root = Path(root).resolve()
        self.approved = {self._relative(item).casefold() for item in approved_paths}
        self.inspected: dict[str, str] = {}

    def _relative(self, value: str | Path) -> str:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise AgentError("路径必须是项目内相对路径")
        raw = Path(value)
        if raw.is_absolute() or ".." in raw.parts:
            raise AgentError("路径必须是项目内相对路径")
        from .project import valid_file_name
        if any(part != "." and not valid_file_name(part) for part in raw.parts):
            raise AgentError("路径包含非法文件名")
        candidate = self.root / raw
        for ancestor in (candidate, *candidate.parents):
            if ancestor == self.root:
                break
            if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
                raise AgentError("Agent 不允许通过链接访问文件")
        path = candidate.resolve()
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise AgentError("路径必须位于项目工作区") from exc

    def read(self, value: str | Path, limit: int = 2 * 1024 * 1024) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 2 * 1024 * 1024:
            raise AgentError("文件读取上限无效")
        rel = self._relative(value)
        path = self.root / rel
        if not path.is_file() or path.is_symlink():
            raise AgentError("只能读取工作区内的普通文件")
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise AgentError("文件超过 Agent 读取上限")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AgentError("Agent 只读取 UTF-8 文本文件") from exc
        self.inspected[rel.casefold()] = hashlib.sha256(raw).hexdigest()
        return {"path": rel, "content": text, "bytes": len(raw)}

    def write(self, value: str | Path, content: str, *, create: bool = False) -> dict[str, Any]:
        rel = self._relative(value)
        path = self.root / rel
        if rel.casefold() not in self.approved:
            raise AgentError("写入路径未获得用户确认")
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise AgentError("只能写入工作区内的普通文件")
        if path.exists() and rel.casefold() not in self.inspected:
            raise AgentError("修改已有文件前必须先 read")
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != self.inspected[rel.casefold()]:
            raise AgentError("文件读取后已经被修改，请重新读取再编辑")
        if not path.exists() and not create:
            raise AgentError("创建新文件必须显式指定 create")
        if not isinstance(content, str) or len(content.encode("utf-8")) > 2 * 1024 * 1024:
            raise AgentError("写入内容超过上限")
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=str(path))
            except SyntaxError as exc:
                raise AgentError(f"Python 语法错误: {exc}") from exc
        if path.suffix in {".json", ".form", ".flow"}:
            try:
                value = json.loads(content)
                if path.name.endswith(".form.json"):
                    from .project import validate_form
                    validate_form(value)
                elif path.name.endswith(".flow.json"):
                    from .flow import validate_flow
                    validate_flow(value)
                elif rel == ".pcide/project.json":
                    from .project import Project
                    Project(self.root, value)
                elif rel == "database/schema.json":
                    from .database import validate_schema
                    validate_schema(value)
            except ValueError as exc:
                raise AgentError(f"JSON 或项目合同无效: {exc}") from exc
        if path.suffix == ".zhxb":
            try:
                from .compiler import parse
                parse(content)
            except Exception as exc:
                raise AgentError(f"中文源码语法错误: {exc}") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.is_file()
        before = path.read_text(encoding="utf-8") if existed else ""
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".agent.tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        self.inspected[rel.casefold()] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {"path": rel, "created": not existed, "changed": before != content}

class AgentSession:
    def __init__(self, task: AgentTask, tools: list[ToolSpec] | None = None):
        if not isinstance(task.prompt, str) or not task.prompt.strip() or len(task.prompt) > 100000:
            raise AgentError("任务目标不能为空或超过 100000 字符")
        if type(task.max_steps) is not int or not 1 <= task.max_steps <= 128 or type(task.timeout_seconds) not in {int, float} or not math.isfinite(task.timeout_seconds) or not 0 < task.timeout_seconds <= 3600:
            raise AgentError("Agent 步骤或超时无效")
        self.id = uuid.uuid4().hex
        self.task = task
        self.state = AgentState.CREATED
        self.events: list[AgentEvent] = []
        self.changes: list[dict[str, Any]] = []
        self._cancel = threading.Event()
        self._tools = {tool.name: tool for tool in (tools or [])}
        self._guard = WorkspaceGuard(task.project_root, task.approved_paths)
        self._lock = threading.RLock()
        self.pending_approval: tuple[str, dict[str, Any]] | None = None
        self.on_event = None
        self._client = None
        self._tool_steps = 0

    def emit(self, kind: str, message: str = "", **data: Any) -> AgentEvent:
        event = AgentEvent(kind, message, data)
        with self._lock:
            self.events.append(event)
            self.events = self.events[-1000:]
        if self.on_event:
            self.on_event(event)
        return event

    def cancel(self) -> None:
        self._cancel.set()
        if self._client and hasattr(self._client, "cancel"):
            self._client.cancel()
        if self.state not in {AgentState.COMPLETED, AgentState.FAILED}:
            self.state = AgentState.CANCELLED
            self.emit("cancelled", "任务已取消")

    def execute_tool(self, name: str, arguments: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
        if self._cancel.is_set():
            raise AgentError("任务已取消")
        tool = self._tools.get(name)
        if tool is None:
            raise AgentError(f"未知工具: {name}")
        if (tool.requires_approval or tool.mutating) and not approved:
            self.state = AgentState.WAITING_APPROVAL
            self.pending_approval = (name, dict(arguments))
            self.emit("approval_required", f"工具需要确认: {name}", tool=name)
            raise AgentError("工具调用需要用户确认")
        if self._tool_steps >= self.task.max_steps:
            raise AgentError("Agent 工具调用超过步骤上限")
        self._tool_steps += 1
        self.state = AgentState.RUNNING
        self.emit("tool_start", name, tool=name, arguments=arguments)
        result = tool.handler(arguments)
        if not isinstance(result, dict):
            raise AgentError("工具必须返回对象")
        self.emit("tool_end", name, tool=name, result=result)
        if tool.mutating:
            self.changes.append(result)
        return result

    def approve_pending(self) -> dict[str, Any]:
        if self.pending_approval is None:
            raise AgentError("当前没有待确认的工具调用")
        name, arguments = self.pending_approval
        self.pending_approval = None
        return self.execute_tool(name, arguments, approved=True)

    def run(self, planner: Callable[[AgentTask, tuple[AgentEvent, ...]], list[dict[str, Any]]]) -> AgentResult:
        self.state = AgentState.PLANNING
        self.emit("plan_start", "正在分析需求")
        try:
            actions = planner(self.task, tuple(self.events))
            if not isinstance(actions, list) or len(actions) > self.task.max_steps:
                raise AgentError("Agent 计划超过步骤上限")
            self.emit("plan_ready", "计划已生成", steps=len(actions))
            for action in actions:
                if not isinstance(action, dict):
                    raise AgentError("计划步骤必须是对象")
                self.execute_tool(str(action.get("tool", "")), dict(action.get("arguments") or {}), approved=self.task.allow_writes)
            if self._cancel.is_set():
                raise AgentError("任务已取消")
            self.state = AgentState.COMPLETED
            self.emit("completed", "任务完成")
            return AgentResult(self.id, self.state, "任务完成", tuple(self.events), tuple(self.changes))
        except Exception as exc:
            if self.state not in {AgentState.CANCELLED, AgentState.WAITING_APPROVAL}:
                self.state = AgentState.FAILED
                self.emit("failed", str(exc))
            return AgentResult(self.id, self.state, str(exc), tuple(self.events), tuple(self.changes))

    def run_model(self, client: Any, *, system_prompt: str = "") -> AgentResult:
        """Run a bounded tool-calling loop against an OpenAI-compatible client."""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": self.task.prompt})
        self.state = AgentState.PLANNING
        self._client = client
        deadline = time.monotonic() + self.task.timeout_seconds
        timer = threading.Timer(self.task.timeout_seconds, self.cancel)
        timer.daemon = True
        timer.start()
        try:
            for step in range(self.task.max_steps):
                if self._cancel.is_set():
                    raise AgentError("任务已取消")
                self.emit("model_start", "正在请求模型", step=step + 1)
                reply = client.complete(messages, list(self._tools.values()))
                if time.monotonic() >= deadline:
                    raise AgentError("Agent 任务超时")
                if self._cancel.is_set():
                    raise AgentError("任务已取消")
                calls = list(reply.tool_calls)
                if not calls:
                    self.state = AgentState.COMPLETED
                    self.emit("completed", reply.content)
                    return AgentResult(self.id, self.state, reply.content, tuple(self.events), tuple(self.changes))
                assistant = {"role": "assistant", "content": reply.content or "", "tool_calls": calls}
                messages.append(assistant)
                for call in calls:
                    function = call.get("function") or {}
                    name = str(function.get("name") or "")
                    try:
                        args = json.loads(function.get("arguments") or "{}")
                    except (TypeError, ValueError) as exc:
                        raise AgentError(f"工具参数不是 JSON: {name}") from exc
                    if not isinstance(args, dict):
                        raise AgentError(f"工具参数必须是对象: {name}")
                    try:
                        output = self.execute_tool(name, args, approved=self.task.allow_writes)
                    except (AgentError, OSError, ValueError, TypeError) as exc:
                        if self.state == AgentState.WAITING_APPROVAL:
                            return AgentResult(self.id, self.state, str(exc), tuple(self.events), tuple(self.changes))
                        output = {"ok": False, "error": str(exc)}
                    messages.append({"role": "tool", "tool_call_id": str(call.get("id") or uuid.uuid4().hex),
                                     "name": name, "content": json.dumps(output, ensure_ascii=False)})
            raise AgentError("模型工具调用超过步骤上限")
        except Exception as exc:
            if self.state != AgentState.CANCELLED:
                self.state = AgentState.FAILED
                self.emit("failed", str(exc))
            return AgentResult(self.id, self.state, str(exc), tuple(self.events), tuple(self.changes))
        finally:
            timer.cancel()
            self._client = None

    @property
    def guard(self) -> WorkspaceGuard:
        return self._guard
