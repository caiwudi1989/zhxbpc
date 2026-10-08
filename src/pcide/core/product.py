"""Product-level subsystem contracts for the zhxbpc platform.

These descriptors are intentionally data-only. UI panels, compilers and child
hosts consume them through the same registry, so adding a provider does not
require changing the project schema or loading third-party code in-process.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform import CAPABILITY_KINDS, validate_platform

@dataclass(frozen=True)
class Subsystem:
    kind: str
    label: str
    contract: str
    default_provider: str
    stages: tuple[str, ...]

SUBSYSTEMS = (
    Subsystem("database", "数据库设计器", "schema-v1", "sqlite", ("schema", "binding", "crud")),
    Subsystem("api", "API 中心", "api-v1", "http", ("request", "model", "error")),
    Subsystem("script", "zhxb Script", "script-v1", "python", ("load", "debug", "reload")),
    Subsystem("ai", "zhxb AI Runtime", "ai-v1", "onnx", ("inference", "vision", "pipeline")),
    Subsystem("game", "Game SDK", "game-v1", "unity", ("scene", "render", "input", "build")),
    Subsystem("compiler", "中文编译器", "compiler-v1", "runtime", ("lex", "parse", "ir", "emit")),
    Subsystem("agent", "IDE Agent", "agent-v1", "local", ("inspect", "generate", "verify")),
    Subsystem("runtime", "zhxbcore Runtime", "runtime-v1", "basic", ("window", "io", "lifecycle")),
)

def subsystem_catalog() -> list[dict[str, Any]]:
    return [{"kind": s.kind, "label": s.label, "contract": s.contract,
             "default_provider": s.default_provider, "stages": list(s.stages)} for s in SUBSYSTEMS]

def resolve_subsystems(platform: dict[str, Any] | None) -> list[dict[str, Any]]:
    config = validate_platform(platform)
    enabled = config["capabilities"]
    return [{**entry, "enabled": bool(enabled[entry["kind"]].get("enabled")),
             "providers": list(enabled[entry["kind"]].get("providers", []))}
            for entry in subsystem_catalog()]

def capability_summary(platform: dict[str, Any] | None) -> dict[str, int]:
    rows = resolve_subsystems(platform)
    return {"total": len(rows), "enabled": sum(row["enabled"] for row in rows),
            "disabled": sum(not row["enabled"] for row in rows), "providers": len(validate_platform(platform)["providers"])}
