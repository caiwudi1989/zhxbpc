"""One bounded HTTP request in an owned child; credentials travel via stdin."""
from __future__ import annotations

import json
import sys

from .agent_client import AgentClient, http_body


def main():
    try:
        raw = sys.stdin.buffer.read(9 * 1024 * 1024 + 1)
        if len(raw) > 9 * 1024 * 1024:
            raise ValueError("AI 请求超过输入上限")
        request = json.loads(raw)
        client = AgentClient(request["endpoint"], request.get("api_key", ""), "http-worker", timeout_seconds=request["timeout"])
        payload = json.dumps(request["payload"], ensure_ascii=False).encode("utf-8")
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("AI 请求上下文超过 8MB")
        sys.stdout.buffer.write(http_body(client._endpoint(), client.api_key, payload, client.timeout_seconds))
        sys.stdout.buffer.flush()
        return 0
    except Exception as exc:
        sys.stderr.write(str(exc)[:2000])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
