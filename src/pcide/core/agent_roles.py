"""Specialized IDE Agent roles sharing one bounded session/tool layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class AgentRole:
    id: str
    label: str
    system_prompt: str
    preferred_tools: tuple[str, ...]

ROLES = (
    AgentRole("architect", "架构 Agent", "分析模块边界、依赖和实施顺序。", ("inspect_project", "list_files", "search")),
    AgentRole("code", "代码 Agent", "读取现有实现后生成可验证的最小修改。", ("read_file", "search", "patch_file", "verify_project")),
    AgentRole("ui", "界面 Agent", "设计窗口、控件、属性和事件，并保持表单合同。", ("inspect_project", "read_file", "patch_file")),
    AgentRole("database", "数据库 Agent", "设计表结构、索引、关系并生成 CRUD。", ("inspect_project", "read_file", "write_file")),
    AgentRole("ai_model", "模型 Agent", "选择模型后端、设备和推理流水线。", ("inspect_project", "read_file", "verify_project")),
    AgentRole("test", "测试 Agent", "运行验证、分析错误并给出修复建议。", ("list_files", "search", "verify_project")),
)

def role_catalog() -> list[dict[str, Any]]:
    return [role.__dict__ | {"preferred_tools": list(role.preferred_tools)} for role in ROLES]
