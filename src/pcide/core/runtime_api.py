"""Small, deterministic API exposed to generated Python projects."""
from __future__ import annotations

import time
from typing import Any


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


def ocr_mock(image: Any, text: str = "OK") -> dict[str, Any]:
    return {"kind": "ocr", "source": str(image), "items": [{"text": text, "confidence": 0.99,
            "box": [0, 0, 80, 28]}], "simulated": True}


def yolo_mock(image: Any, label: str = "button") -> dict[str, Any]:
    return {"kind": "yolo", "source": str(image), "detections": [{"label": label, "confidence": 0.95,
            "box": [10, 10, 100, 60]}], "simulated": True}


def screenshot_mock(name: str = "screen") -> dict[str, Any]:
    return {"kind": "screenshot", "name": name, "timestamp": time.time(), "simulated": True}
