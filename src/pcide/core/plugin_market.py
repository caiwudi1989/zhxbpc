"""Offline-first plugin catalog and installation contract."""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import uuid
import zipfile
import re
from pathlib import Path
from typing import Any

class MarketError(ValueError): pass


def _plugin_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", value):
        raise MarketError("插件 ID 非法")
    return value

def validate_catalog(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("plugins"), list):
        raise MarketError("插件市场清单版本不支持")
    ids = set(); plugins = []
    for item in value["plugins"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", item["id"]) or item["id"] in ids:
            raise MarketError("插件 ID 非法或重复")
        if not isinstance(item.get("version"), str) or not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64 or any(char not in "0123456789abcdefABCDEF" for char in item["sha256"]):
            raise MarketError("插件版本或 SHA-256 无效")
        ids.add(item["id"]); plugins.append(dict(item))
    return {"version": 1, "plugins": plugins}

def install_archive(catalog_item: dict[str, Any], archive: str | Path, target_root: str | Path) -> Path:
    item = validate_catalog({"version": 1, "plugins": [catalog_item]})["plugins"][0]
    source = Path(archive).resolve(); target_root = Path(target_root).resolve()
    if not source.is_file() or source.is_symlink(): raise MarketError("插件包不存在")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest.lower() != item["sha256"].lower(): raise MarketError("插件包校验失败")
    if source.suffix.lower() not in {".zip", ".pcplugin"}: raise MarketError("插件包格式不支持")
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / item["id"]
    if target.exists():
        raise MarketError("插件已安装")
    staging = target_root / (".pcplugin-" + uuid.uuid4().hex)
    staging.mkdir()
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > 2000 or sum(member.file_size for member in members) > 128 * 1024 * 1024:
                raise MarketError("插件包大小或文件数量超过限制")
            seen: set[str] = set()
            for member in members:
                # Zip uses POSIX separators, but Windows archives frequently
                # contain backslashes. Normalize both before checking escape.
                name = member.filename.replace("\\", "/")
                parts = [part for part in name.split("/") if part]
                key = "/".join(parts).casefold()
                if not parts or name.startswith("/") or ":" in parts[0] or ".." in parts or key in seen:
                    raise MarketError("插件包包含越界或重复路径")
                seen.add(key)
                mode = (member.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise MarketError("插件包不能包含符号链接")
                destination = (staging / "/".join(parts)).resolve()
                if not destination.is_relative_to(staging.resolve()):
                    raise MarketError("插件包包含越界路径")
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source_handle, destination.open("wb") as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
        (staging / "catalog.json").write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.replace(target)
        return target
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def uninstall_plugin(plugin_id: str, target_root: str | Path) -> None:
    """Remove one installed plugin after validating its ID."""
    plugin_id = _plugin_id(plugin_id)
    root = Path(target_root).resolve()
    target = (root / plugin_id).resolve()
    if not target.is_relative_to(root) or not target.is_dir() or target.is_symlink():
        raise MarketError("插件未安装")
    shutil.rmtree(target)


def upgrade_archive(catalog_item: dict[str, Any], archive: str | Path, target_root: str | Path) -> Path:
    """Install an upgrade while retaining one verified rollback copy."""
    item = validate_catalog({"version": 1, "plugins": [catalog_item]})["plugins"][0]
    plugin_id = _plugin_id(item["id"])
    root = Path(target_root).resolve()
    target = (root / plugin_id).resolve()
    if not target.is_relative_to(root) or not target.is_dir() or target.is_symlink():
        raise MarketError("插件未安装")
    rollback_root = root / ".pcplugin-rollback"
    rollback_root.mkdir(parents=True, exist_ok=True)
    backup = rollback_root / plugin_id
    if backup.exists():
        if backup.is_dir() and not backup.is_symlink():
            shutil.rmtree(backup)
        else:
            backup.unlink()
    target.rename(backup)
    try:
        return install_archive(item, archive, root)
    except Exception:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        backup.rename(target)
        raise


def rollback_plugin(plugin_id: str, target_root: str | Path) -> Path:
    """Restore the last package saved by :func:`upgrade_archive`."""
    plugin_id = _plugin_id(plugin_id)
    root = Path(target_root).resolve()
    target = (root / plugin_id).resolve()
    backup = (root / ".pcplugin-rollback" / plugin_id).resolve()
    if not target.is_relative_to(root) or not backup.is_relative_to(root) or not backup.is_dir() or backup.is_symlink():
        raise MarketError("没有可回滚的插件版本")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise MarketError("当前插件目录无效")
        shutil.rmtree(target)
    backup.rename(target)
    return target
