"""Versioned API center contracts and safe request generation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

class ApiError(ValueError):
    pass

@dataclass(frozen=True)
class Endpoint:
    id: str
    name: str
    method: str
    path: str
    protocol: str = "https"
    timeout_seconds: float = 30.0
    response_type: str = "json"

def validate_endpoint(value: dict[str, Any]) -> Endpoint:
    if not isinstance(value, dict):
        raise ApiError("API 接口必须是对象")
    try:
        timeout = float(value.get("timeout_seconds", 30))
    except (TypeError, ValueError) as exc:
        raise ApiError("API 超时必须是数字") from exc
    endpoint = Endpoint(str(value.get("id", "")), str(value.get("name", "")), str(value.get("method", "GET")).upper(), str(value.get("path", "")), str(value.get("protocol", "https")).lower(), timeout, str(value.get("response_type", "json")).lower())
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", endpoint.id) or not endpoint.name:
        raise ApiError("API 标识或名称非法")
    if endpoint.method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "SEND", "RECEIVE"} or endpoint.protocol not in {"http", "https", "websocket", "tcp", "udp", "mqtt"}:
        raise ApiError("不支持的 API 方法或协议")
    if endpoint.response_type not in {"json", "text", "bytes"}:
        raise ApiError("不支持的响应类型")
    if len(endpoint.path) > 2048 or not endpoint.path.startswith("/") or ".." in endpoint.path.split("/") or "\\" in endpoint.path or not 0 < endpoint.timeout_seconds <= 300:
        raise ApiError("API 路径或超时非法")
    return endpoint

def generate_client(endpoint: Endpoint, language: str = "python") -> str:
    ep = validate_endpoint(endpoint.__dict__)
    if language == "python":
        function = re.sub(r"[^A-Za-z0-9_]", "_", ep.id)
        if ep.protocol in {"http", "https"}:
            return f"from pcide.runtime_api import network\n\ndef {function}(base_url, payload=None):\n    return network.request(base_url + '{ep.path}', method='{ep.method}', body=payload, timeout={ep.timeout_seconds})\n"
        return f"def {function}(_endpoint, _payload=None):\n    raise RuntimeError('协议 {ep.protocol} 需要对应的外部 transport provider')\n"
    if language in {"javascript", "typescript"}:
        function = re.sub(r"[^A-Za-z0-9_]", "_", ep.id)
        return f"export async function {function}(baseUrl, payload) {{ return apiRequest('{ep.protocol}', '{ep.method}', baseUrl + '{ep.path}', payload); }}\n"
    raise ApiError("不支持的生成语言")


def generate_client_module(endpoints: Iterable[Endpoint], language: str = "python") -> str:
    """Generate one complete client module with shared transport/error code."""
    items = [validate_endpoint(endpoint.__dict__ if isinstance(endpoint, Endpoint) else endpoint) for endpoint in endpoints]
    if len(items) > 500 or len({item.id for item in items}) != len(items):
        raise ApiError("接口数量或 ID 重复")
    if language == "python":
        blocks = ["from pcide.runtime_api import network", ""]
        blocks.extend(generate_client(item, language).rstrip() for item in items)
        return "\n\n".join(blocks) + "\n"
    if language not in {"javascript", "typescript"}:
        raise ApiError("不支持的生成语言")
    types = ": Promise<any>" if language == "typescript" else ""
    request_signature = "async function apiRequest(protocol: string, method: string, url: string, payload?: any): Promise<any> {" if language == "typescript" else "async function apiRequest(protocol, method, url, payload) {"
    lines = [
        request_signature,
        "  if (protocol !== 'http' && protocol !== 'https') throw new Error('该协议需要外部 transport provider');",
        "  const response = await fetch(url, {method, headers: payload == null ? {} : {'Content-Type': 'application/json'}, body: payload == null ? undefined : JSON.stringify(payload)});",
        "  const text = await response.text();",
        "  let data; try { data = text ? JSON.parse(text) : null; } catch (_) { data = text; }",
        "  if (!response.ok) { throw Object.assign(new Error(`HTTP ${response.status}`), {status: response.status, data}); }",
        "  return {status: response.status, data};",
        "}",
        "",
    ]
    for item in items:
        function = re.sub(r"[^A-Za-z0-9_]", "_", item.id)
        signature = f"baseUrl: string, payload?: any" if language == "typescript" else "baseUrl, payload"
        lines.append(f"export async function {function}({signature}){types} {{ return apiRequest('{item.protocol}', '{item.method}', baseUrl + '{item.path}', payload); }}")
    return "\n".join(lines) + "\n"
