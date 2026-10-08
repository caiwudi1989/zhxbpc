"""Extensible zhxbpc platform capability contract.

The IDE keeps product areas declarative so future providers can be added without
changing the project schema or embedding a vendor SDK in the editor process.
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

PLATFORM_SCHEMA = 1
CAPABILITY_KINDS = {"database", "api", "script", "ai", "game", "compiler", "agent", "runtime"}
DEFAULT_CAPABILITIES = {
    "database": {"enabled": True, "providers": ["sqlite"]},
    "api": {"enabled": True, "protocols": ["http", "https", "websocket"]},
    "script": {"enabled": True, "engines": ["python", "javascript", "typescript", "zhxb"]},
    "ai": {"enabled": False, "backends": ["onnx", "opencv"]},
    "game": {"enabled": False, "backends": ["unity", "opengl"]},
    "compiler": {"enabled": True, "modes": ["development", "standard", "release"]},
    "agent": {"enabled": False, "roles": ["architect", "code", "ui", "database", "test"]},
    "runtime": {"enabled": True, "profiles": ["basic"]},
}

def default_platform() -> dict[str, Any]:
    return {"version": PLATFORM_SCHEMA, "capabilities": {k: dict(v) for k, v in DEFAULT_CAPABILITIES.items()}, "providers": []}

def validate_platform(value: Any) -> dict[str, Any]:
    if value is None:
        return default_platform()
    if not isinstance(value, dict) or value.get("version") != PLATFORM_SCHEMA:
        raise ValueError("unsupported platform schema")
    caps = value.get("capabilities", {})
    if not isinstance(caps, dict) or set(caps) - CAPABILITY_KINDS:
        raise ValueError("invalid platform capability")
    normalized = default_platform()
    for kind, config in caps.items():
        if not isinstance(config, dict) or type(config.get("enabled", True)) is not bool:
            raise ValueError(f"invalid {kind} capability")
        for key, items in config.items():
            if key != "enabled" and (not isinstance(items, list) or any(not isinstance(x, str) or not x for x in items)):
                raise ValueError(f"invalid {kind}.{key}")
        normalized["capabilities"][kind].update(config)
    providers = value.get("providers", [])
    if not isinstance(providers, list):
        raise ValueError("platform providers must be an array")
    seen = set()
    for provider in providers:
        if not isinstance(provider, dict) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", str(provider.get("id", ""))):
            raise ValueError("invalid platform provider ID")
        if provider["id"] in seen:
            raise ValueError("duplicate platform provider ID")
        seen.add(provider["id"])
        if provider.get("kind") not in CAPABILITY_KINDS or not isinstance(provider.get("version", "1.0.0"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", provider.get("version", "1.0.0")):
            raise ValueError("invalid platform provider")
        normalized["providers"].append(dict(provider))
    return normalized

def discover_providers(root: str | Path) -> list[dict[str, Any]]:
    """Read provider manifests without importing or executing provider code."""
    base = Path(root).resolve() / "providers"
    if not base.is_dir():
        return []
    found = []
    for manifest in sorted(base.glob("*/provider.json")):
        if manifest.is_symlink():
            continue
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            raw.setdefault("version", "1.0.0")
            raw.setdefault("manifest", manifest.relative_to(Path(root).resolve()).as_posix())
            candidate = validate_platform({"version": 1, "providers": [raw]})["providers"][0]
            found.append(candidate)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return found
