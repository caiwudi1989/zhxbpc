"""Versioned API center contracts and safe request generation."""
from __future__ import annotations

import re
import json
import keyword
from dataclasses import dataclass
from typing import Any, Iterable

class ApiError(ValueError):
    pass


def function_name(identity):
    name = re.sub(r"[^A-Za-z0-9_]", "_", identity)
    reserved = {'await', 'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default',
                'delete', 'do', 'else', 'enum', 'export', 'extends', 'false', 'finally', 'for',
                'function', 'if', 'implements', 'import', 'in', 'instanceof', 'interface', 'let',
                'new', 'null', 'package', 'private', 'protected', 'public', 'return', 'static',
                'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof', 'var', 'void',
                'while', 'with', 'yield', 'eval', 'arguments'}
    if keyword.iskeyword(name) or name in reserved:
        raise ApiError('API 标识不能是生成语言的保留字')
    if name in {'network', 'apiRequest'}:
        raise ApiError('API 标识与生成客户端的传输函数冲突')
    return name

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
    if endpoint.method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "SEND", "RECEIVE"} or endpoint.protocol not in {"http", "https", "websocket", "tcp", "udp", "mqtt"}:
        raise ApiError("不支持的 API 方法或协议")
    if endpoint.protocol in {'http', 'https'} and endpoint.method in {'SEND', 'RECEIVE'}:
        raise ApiError('HTTP/HTTPS 不能使用 SEND/RECEIVE 方法')
    if endpoint.response_type not in {"json", "text", "bytes"}:
        raise ApiError("不支持的响应类型")
    if len(endpoint.path) > 2048 or not endpoint.path.startswith("/") or ".." in endpoint.path.split("/") or "\\" in endpoint.path or not 0 < endpoint.timeout_seconds <= 300:
        raise ApiError("API 路径或超时非法")
    return endpoint

def generate_client(endpoint: Endpoint, language: str = "python") -> str:
    ep = validate_endpoint(endpoint.__dict__)
    if language == "python":
        function = function_name(ep.id)
        if ep.protocol in {"http", "https"}:
            if ep.timeout_seconds > 60:
                raise ApiError('当前 Python/中文客户端的网络超时上限为 60 秒')
            return f"from pcide.runtime_api import network\n\ndef {function}(base_url, payload=None):\n    return network.request(base_url + {ep.path!r}, method={ep.method!r}, body=payload, timeout={ep.timeout_seconds})\n"
        return f"def {function}(_endpoint, _payload=None):\n    raise RuntimeError('协议 {ep.protocol} 需要对应的外部 transport provider')\n"
    if language in {"javascript", "typescript"}:
        function = function_name(ep.id)
        protocol, method, path = (json.dumps(value, ensure_ascii=False) for value in (ep.protocol, ep.method, ep.path))
        return f"export async function {function}(baseUrl, payload) {{ return apiRequest({protocol}, {method}, baseUrl + {path}, payload, {ep.timeout_seconds}); }}\n"
    raise ApiError("不支持的生成语言")


def generate_client_module(endpoints: Iterable[Endpoint], language: str = "python") -> str:
    """Generate one complete client module with shared transport/error code."""
    items = [validate_endpoint(endpoint.__dict__ if isinstance(endpoint, Endpoint) else endpoint) for endpoint in endpoints]
    if len(items) > 500 or len({item.id for item in items}) != len(items):
        raise ApiError("接口数量或 ID 重复")
    names = [function_name(item.id) for item in items]
    if len(set(names)) != len(names):
        raise ApiError('API 标识转换后的函数名不能重复')
    if language == "python":
        blocks = ["from pcide.runtime_api import network", ""]
        blocks.extend(generate_client(item, language).removeprefix("from pcide.runtime_api import network\n\n").rstrip() for item in items)
        return "\n\n".join(blocks) + "\n"
    if language not in {"javascript", "typescript"}:
        raise ApiError("不支持的生成语言")
    types = ": Promise<any>" if language == "typescript" else ""
    request_signature = "async function apiRequest(protocol: string, method: string, url: string, payload: any, timeout: number): Promise<any> {" if language == "typescript" else "async function apiRequest(protocol, method, url, payload, timeout) {"
    lines = [
        request_signature,
        "  if (protocol !== 'http' && protocol !== 'https') throw new Error('该协议需要外部 transport provider');",
        "  const controller = new AbortController();",
        "  const timer = setTimeout(() => controller.abort(), timeout * 1000);",
        "  try {",
        "    const response = await fetch(url, {method, signal: controller.signal, headers: payload == null ? {} : {'Content-Type': 'application/json'}, body: payload == null ? undefined : JSON.stringify(payload)});",
        "    const text = await response.text();",
        "    let data; try { data = text ? JSON.parse(text) : null; } catch (_) { data = text; }",
        "    if (!response.ok) { throw Object.assign(new Error(`HTTP ${response.status}`), {status: response.status, data}); }",
        "    return {status: response.status, data};",
        "  } finally { clearTimeout(timer); }",
        "}",
        "",
    ]
    for item in items:
        function = function_name(item.id)
        signature = f"baseUrl: string, payload?: any" if language == "typescript" else "baseUrl, payload"
        protocol, method, path = (json.dumps(value, ensure_ascii=False) for value in (item.protocol, item.method, item.path))
        lines.append(f"export async function {function}({signature}){types} {{ return apiRequest({protocol}, {method}, baseUrl + {path}, payload, {item.timeout_seconds}); }}")
    return "\n".join(lines) + "\n"
