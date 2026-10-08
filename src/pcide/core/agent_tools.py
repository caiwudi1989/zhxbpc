"""Built-in bounded tools exposed to the coding Agent."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from .agent import AgentError, ToolSpec, WorkspaceGuard

_SKIP = {".git", "__pycache__", ".pytest_cache", "node_modules", "build", "cache", "runtime"}
_TEXT = {".py", ".js", ".ts", ".json", ".md", ".txt", ".form", ".flow", ".css", ".html", ".c", ".h"}

def project_tools(root: str | Path, approved_paths: set[str] | frozenset[str] = (), run_tests: Callable[[], dict[str, Any]] | None = None) -> tuple[ToolSpec, ...]:
    guard = WorkspaceGuard(root, approved_paths)
    root_path = guard.root

    def list_files(args: dict[str, Any]) -> dict[str, Any]:
        base = guard._relative(args.get("path", "."))
        directory = root_path / base
        if not directory.is_dir() or directory.is_symlink():
            raise AgentError("目录不存在")
        values = []
        for current, dirs, files in os.walk(directory):
            dirs[:] = [item for item in dirs if item not in _SKIP and not item.startswith(".")]
            for name in sorted(files):
                path = Path(current) / name
                rel = path.relative_to(root_path).as_posix()
                if path.suffix.lower() in _TEXT:
                    values.append(rel)
                if len(values) >= 500:
                    return {"files": values, "truncated": True}
        return {"files": values, "truncated": False}

    def search(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "")
        if not query or len(query) > 200:
            raise AgentError("搜索词不能为空且不能超过 200 字符")
        matches = []
        for item in list_files({"path": args.get("path", ".")})["files"]:
            try:
                lines = (root_path / item).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_no, line in enumerate(lines, 1):
                if query.casefold() in line.casefold():
                    matches.append({"path": item, "line": line_no, "text": line[:500]})
                    if len(matches) >= 100:
                        return {"matches": matches, "truncated": True}
        return {"matches": matches, "truncated": False}

    def read_file(args: dict[str, Any]) -> dict[str, Any]:
        return guard.read(str(args.get("path") or ""), min(int(args.get("limit", 200000)), 2 * 1024 * 1024))

    def write_file(args: dict[str, Any]) -> dict[str, Any]:
        return guard.write(str(args.get("path") or ""), str(args.get("content") or ""), create=bool(args.get("create")))

    def patch_file(args: dict[str, Any]) -> dict[str, Any]:
        rel = str(args.get("path") or "")
        current = guard.read(rel)["content"]
        find = str(args.get("find") or "")
        if not find:
            raise AgentError("替换目标不能为空")
        if current.count(find) != 1:
            raise AgentError("替换目标必须在文件中唯一出现一次")
        return guard.write(rel, current.replace(find, str(args.get("replace") or "")))

    def verify(_args: dict[str, Any]) -> dict[str, Any]:
        if run_tests is None:
            return {"ok": False, "error": "当前宿主未提供测试执行器"}
        result = run_tests()
        return result if isinstance(result, dict) else {"ok": False, "error": "测试执行器返回无效结果"}

    def inspect_project(_args: dict[str, Any]) -> dict[str, Any]:
        manifest = {}
        manifest_path = root_path / ".pcide" / "project.json"
        if manifest_path.is_file():
            import json
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    manifest = {key: raw.get(key) for key in ("name", "language", "entry", "modules", "platform") if key in raw}
            except (OSError, ValueError):
                manifest = {"error": "工程配置无法解析"}
        files = list_files({"path": "."})
        return {"manifest": manifest, "file_count": len(files["files"]), "truncated": files["truncated"],
                "windows": len(list((root_path / "ui").glob("*.form.json"))) if (root_path / "ui").is_dir() else 0}

    common = {"type": "object", "additionalProperties": False}
    return (
        ToolSpec("inspect_project", "读取项目摘要、语言、入口、平台能力和窗口数量", inspect_project, parameters={**common, "properties": {}}),
        ToolSpec("list_files", "列出项目内的文本文件", list_files, parameters={**common, "properties": {"path": {"type": "string"}}}),
        ToolSpec("search", "在项目源码中搜索文本", search, parameters={**common, "properties": {"query": {"type": "string"}, "path": {"type": "string"}}}),
        ToolSpec("read_file", "读取项目内文件；修改前必须先读取", read_file, parameters={**common, "required": ["path"], "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}}),
        ToolSpec("write_file", "写入已获批准的项目文件", write_file, mutating=True, requires_approval=True, parameters={**common, "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "create": {"type": "boolean"}}}),
        ToolSpec("patch_file", "对已读取文件做唯一文本替换", patch_file, mutating=True, requires_approval=True, parameters={**common, "required": ["path", "find", "replace"], "properties": {"path": {"type": "string"}, "find": {"type": "string"}, "replace": {"type": "string"}}}),
        ToolSpec("verify_project", "运行宿主提供的项目验证", verify, parameters={**common, "properties": {}}),
    )
