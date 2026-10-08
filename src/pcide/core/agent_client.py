"""Small OpenAI-compatible chat client used by the PC IDE Agent.

The client deliberately speaks the public chat-completions/tool-calls shape so
DeepSeek, local OpenAI-compatible servers and other providers can be selected
without importing any provider SDK into the IDE.
"""
from __future__ import annotations

import json
import math
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .agent import AgentError, ToolSpec

@dataclass(frozen=True)
class ChatReply:
    content: str
    tool_calls: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] | None = None

class AgentClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout_seconds: float = 120.0, isolated: bool = False):
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.model = str(model or "")
        timeout = float(timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0:
            raise AgentError("AI 请求超时无效")
        self.timeout_seconds = max(0.1, min(timeout, 600.0))
        self.isolated = isolated
        self._cancel = threading.Event()
        self._job = None
        if not self.base_url.startswith(("http://", "https://")) or not self.model or len(self.model) > 256:
            raise AgentError("AI 服务地址和模型不能为空")
        if any(character.isspace() for character in self.base_url) or len(self.base_url) > 2048:
            raise AgentError("AI 服务地址无效")
        parsed = urllib.parse.urlparse(self.base_url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise AgentError("AI 服务地址无效")

    def _endpoint(self) -> str:
        return self.base_url if self.base_url.endswith("/chat/completions") else self.base_url + "/chat/completions"

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *, temperature: float = 0.1) -> ChatReply:
        functions = []
        for tool in tools:
            functions.append({"type": "function", "function": {
                "name": tool.name, "description": tool.description,
                "parameters": tool.parameters or {"type": "object", "properties": {}, "additionalProperties": False},
            }})
        if not isinstance(messages, list) or len(messages) > 256:
            raise AgentError("AI 消息数量超过限制")
        payload = {"model": self.model, "messages": messages, "temperature": max(0.0, min(float(temperature), 1.0)),
                   "tools": functions, "tool_choice": "auto", "stream": False}
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(raw) > 8 * 1024 * 1024:
            raise AgentError("AI 请求上下文超过 8MB")
        if self._cancel.is_set():
            raise AgentError("AI 请求已取消")
        body = self._isolated_body(payload) if self.isolated else http_body(self._endpoint(), self.api_key, raw, self.timeout_seconds)
        if len(body) > 16 * 1024 * 1024:
            raise AgentError("AI 响应超过 16MB")
        try:
            data = json.loads(body.decode("utf-8"))
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AgentError("AI 响应格式无效") from exc
        if not isinstance(message, dict) or not isinstance(message.get("tool_calls") or [], list):
            raise AgentError("AI 工具响应格式无效")
        calls = tuple(message.get("tool_calls") or ())
        if len(calls) > 128 or any(not isinstance(call, dict) or not isinstance(call.get("function"), dict) or not isinstance(call.get("id"), str) for call in calls):
            raise AgentError("AI 工具响应数量或格式无效")
        content = message.get("content") or ""
        return ChatReply(str(content), tuple(calls), data)

    def cancel(self):
        self._cancel.set()
        if self._job:
            self._job.close()

    def _isolated_body(self, payload):
        from .processes import ProcessJob, child_environment, host_command
        request = json.dumps({"endpoint": self._endpoint(), "api_key": self.api_key,
                              "payload": payload, "timeout": self.timeout_seconds}, ensure_ascii=False).encode("utf-8")
        process = subprocess.Popen(host_command("agent_http"), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=child_environment(),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        job = None
        try:
            job = ProcessJob(process)
            self._job = job
            if self._cancel.is_set():
                raise AgentError("AI 请求已取消")
            stdout, stderr = process.communicate(request, timeout=self.timeout_seconds + 5)
            if self._cancel.is_set():
                raise AgentError("AI 请求已取消")
            if process.returncode:
                raise AgentError("AI 服务请求失败: " + stderr.decode("utf-8", errors="replace")[:2000])
            return stdout
        except subprocess.TimeoutExpired as exc:
            raise AgentError("AI 服务请求超时") from exc
        finally:
            self._job = None
            if job:
                job.close()
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream:
                    stream.close()

    @staticmethod
    def health(base_url: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
        endpoint = str(base_url or "").rstrip("/")
        if endpoint.endswith("/chat/completions"):
            endpoint = endpoint[:-len("/chat/completions")]
        request = urllib.request.Request(endpoint + "/models", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(1.0, min(float(timeout_seconds), 15.0))) as response:
                return {"ok": 200 <= response.status < 300, "status": response.status}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def http_body(endpoint: str, api_key: str, raw: bytes, timeout: float) -> bytes:
    """Bounded transport shared by the client and its owned HTTP child host."""
    request = urllib.request.Request(endpoint, data=raw, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {api_key}"} if api_key else {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(16 * 1024 * 1024 + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AgentError(f"AI 服务请求失败: {exc}") from exc
    if len(body) > 16 * 1024 * 1024:
        raise AgentError("AI 响应超过 16MB")
    return body
