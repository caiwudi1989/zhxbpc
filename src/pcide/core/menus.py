"""Explicit, bounded menu definitions shared by the IDE and window runtime."""
from __future__ import annotations

import keyword

MENU_KEYS = {"id", "text", "kind", "enabled", "visible", "checkable", "checked", "shortcut", "handler", "children"}


def validate_menu(value):
    if not isinstance(value, list):
        raise ValueError("菜单内容必须是数组")
    identities, shortcuts = set(), set()
    count = 0

    def visit(items, depth):
        nonlocal count
        if depth > 8:
            raise ValueError("菜单最多嵌套 8 层")
        result = []
        for item in items:
            count += 1
            if count > 256:
                raise ValueError("菜单最多 256 项")
            if not isinstance(item, dict) or set(item) - MENU_KEYS:
                raise ValueError("菜单项包含不支持的字段")
            node = dict(item)
            identity = node.get("id", "")
            if not isinstance(identity, str) or len(identity) > 128 or not identity.isidentifier() or identity in identities:
                raise ValueError("菜单标识必须有效且不能重复")
            identities.add(identity)
            kind = node.setdefault("kind", "item")
            if not isinstance(kind, str) or kind not in {"menu", "item", "separator"}:
                raise ValueError("不支持的菜单类型")
            text = node.setdefault("text", "")
            if not isinstance(text, str) or len(text) > 256 or ("\n" in text) or (kind != "separator" and not text.strip()):
                raise ValueError("菜单标题不能为空或含换行")
            for key, default in (("enabled", True), ("visible", True), ("checkable", False), ("checked", False)):
                if type(node.setdefault(key, default)) is not bool:
                    raise ValueError("菜单状态必须是逻辑值")
            if node["checked"] and not node["checkable"]:
                raise ValueError("勾选状态需要启用可勾选")
            handler = node.setdefault("handler", "")
            if not isinstance(handler, str) or len(handler) > 128 or (handler and (not handler.isidentifier() or keyword.iskeyword(handler))):
                raise ValueError("菜单处理子程序名称无效")
            shortcut = node.setdefault("shortcut", "")
            if not isinstance(shortcut, str) or len(shortcut) > 64 or any(ord(c) < 32 for c in shortcut):
                raise ValueError("菜单快捷键格式无效")
            if shortcut:
                if shortcut.casefold() in shortcuts:
                    raise ValueError("菜单快捷键不能重复")
                shortcuts.add(shortcut.casefold())
            children = node.setdefault("children", [])
            if not isinstance(children, list) or (kind != "menu" and children):
                raise ValueError("只有子菜单能包含下级项目")
            if kind != "item" and (handler or shortcut or node["checkable"]):
                raise ValueError("处理子程序、快捷键和勾选只能用于菜单项")
            node["children"] = visit(children, depth + 1) if children else []
            result.append(node)
        return result

    return visit(value, 1)


def legacy_menu(items):
    if isinstance(items, str):
        items = [value.strip() for value in items.split("|") if value.strip()]
    return validate_menu([{"id": f"menu_{index + 1}", "text": str(text), "kind": "menu"} for index, text in enumerate(items)])

