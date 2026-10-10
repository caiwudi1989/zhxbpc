"""Small, deterministic API exposed to generated Python projects."""
from __future__ import annotations

import json
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from contextlib import closing


class _PluginProxy:
    """Worker-owned library calls; every call closes its isolated host."""
    def call(self, plugin_id, capability, params=None, timeout=5):
        from .plugins import PluginRegistry
        from .project import Project
        if type(timeout) not in {int,float} or not 0.05 <= timeout <= 60:
            raise ValueError('支持库超时必须为 0.05 到 60 秒')
        project=Project.open(Path.cwd())
        registry=PluginRegistry(project.root,project.manifest.get('permissions',[]))
        try:
            registry.load(plugin_id,timeout=timeout)
            return registry.call(plugin_id,capability,params,timeout=timeout)['result']
        finally:
            registry.close()


plugins = _PluginProxy()

from . import tasks


class _UiProxy:
    """Event-safe UI update proxy. The host can consume the JSON messages."""
    def __init__(self):
        self.transport = None

    def set(self, control_id: str, **properties: Any) -> dict[str, Any]:
        if not isinstance(control_id, str) or len(control_id) > 128:
            raise ValueError("invalid control id")
        message = {"kind": "ui.set", "id": control_id, "properties": properties}
        if self.transport:
            self.transport(message.copy())
        return message

    def open(self, window_id: str) -> dict[str, Any]:
        if not isinstance(window_id, str) or not window_id.strip() or len(window_id) > 256:
            raise ValueError("invalid window id")
        message = {"kind": "ui.window.open", "window": window_id}
        if self.transport:
            self.transport(message.copy())
        return message

    def close(self, window_id: str) -> dict[str, Any]:
        if not isinstance(window_id, str) or not window_id.strip() or len(window_id) > 256:
            raise ValueError("invalid window id")
        message = {"kind": "ui.window.close", "window": window_id}
        if self.transport:
            self.transport(message.copy())
        return message

    def emit(self, control_id: str, event: str, **payload: Any) -> dict[str, Any]:
        message = {"kind": "ui.event", "id": control_id, "event": event, "payload": payload}
        if self.transport:
            self.transport(message.copy())
        return message


ui = _UiProxy()


from .dll import dll

class _DatabaseProxy:
    def connect(self, path: str = "database/app.sqlite"):
        raw = str(path or "").replace("\\", "/")
        target = Path(raw)
        if target.is_absolute() or ".." in target.parts or not raw or len(raw) > 260 or "\x00" in raw or ":" in raw:
            raise ValueError("数据库路径必须是项目内相对路径")
        target.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(target), timeout=10)
    def query(self, connection, sql: str, params=()):
        if not isinstance(sql, str) or len(sql) > 100_000:
            raise ValueError("SQL 过长")
        with closing(connection.execute(sql, tuple(params))) as cursor:
            rows = cursor.fetchmany(10_000)
        return [dict(row) if isinstance(row, sqlite3.Row) else tuple(row) for row in rows]
    def execute(self, connection, sql: str, params=()):
        if not isinstance(sql, str) or len(sql) > 100_000:
            raise ValueError("SQL 过长")
        with closing(connection.execute(sql, tuple(params))) as cursor:
            connection.commit()
            return {"rowcount": cursor.rowcount, "lastrowid": cursor.lastrowid}

db = _DatabaseProxy()

class _NetworkProxy:
    def request(self, url: str, method: str = "GET", body=None, timeout: float = 30):
        parsed = urllib.parse.urlparse(str(url))
        method = str(method).upper()
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None or parsed.username or parsed.password or method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise ValueError("网络请求只允许 HTTP/HTTPS")
        try:
            timeout = float(timeout)
            if not math.isfinite(timeout) or not 0 < timeout <= 60:
                raise ValueError('网络超时必须为有限的 0..60 秒')
        except (TypeError, ValueError) as exc:
            raise ValueError("网络请求超时无效") from exc
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        if payload is not None and len(payload) > 4 * 1024 * 1024:
            raise ValueError("请求体超过 4MB")
        request = urllib.request.Request(str(url), data=payload, method=method, headers={"Content-Type": "application/json"} if payload else {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError("响应超过 4MB")
                text = raw.decode("utf-8", errors="replace")
                try: content = json.loads(text)
                except ValueError: content = text
                return {"status": response.status, "data": content}
        except urllib.error.HTTPError as exc:
            try:
                return {"status": exc.code, "error": str(exc)}
            finally:
                exc.close()

network = _NetworkProxy()

class _GameProxy:
    def emit(self, event: str, **payload):
        if not isinstance(event, str) or not event.strip() or len(event) > 128:
            raise ValueError("游戏事件名非法")
        message = {"kind": "game.event", "event": event, "payload": payload}
        if ui.transport:
            ui.transport(message.copy())
        return message

game = _GameProxy()


def ocr_mock(image: Any, text: str = "OK") -> dict[str, Any]:
    return {"kind": "ocr", "source": str(image), "items": [{"text": text, "confidence": 0.99,
            "box": [0, 0, 80, 28]}], "simulated": True}


def yolo_mock(image: Any, label: str = "button") -> dict[str, Any]:
    return {"kind": "yolo", "source": str(image), "detections": [{"label": label, "confidence": 0.95,
            "box": [10, 10, 100, 60]}], "simulated": True}


def screenshot_mock(name: str = "screen") -> dict[str, Any]:
    return {"kind": "screenshot", "name": name, "timestamp": time.time(), "simulated": True}
