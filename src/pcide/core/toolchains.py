"""Discover existing system tools without installing or downloading runtimes."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .development import TOOL_NAMES
from .paths import Paths, atomic_write_json, read_json

COMMANDS = {'python': ('python.exe',), 'node': ('node.exe',), 'cc': ('gcc.exe', 'clang.exe', 'cl.exe'),
            'cxx': ('g++.exe', 'clang++.exe', 'cl.exe'), 'cmake': ('cmake.exe',), 'dotnet': ('dotnet.exe',),
            'godot': ('godot.exe', 'godot4.exe', 'godot_console.exe'), 'unity': ('Unity.exe',)}

def load_workspace_tools(paths=None):
    from .development import validate_development
    paths = paths or Paths()
    raw = read_json(paths.runtime / 'toolchains.json', {'version': 1, 'tools': {}})
    if not isinstance(raw, dict) or type(raw.get('version')) is not int or raw.get('version') != 1 or set(raw) != {'version', 'tools'}:
        raise ValueError('工作区工具配置无效')
    return validate_development({'template': 'python-script', 'tools': raw['tools']}, 'python')['tools']

def save_workspace_tools(paths, tools):
    from .development import validate_development
    tools = validate_development({'template': 'python-script', 'tools': tools}, 'python')['tools']
    atomic_write_json(paths.runtime / 'toolchains.json', {'version': 1, 'tools': tools})

def discover_tools(project=None, paths=None):
    tools = project.manifest.get('development', {}).get('tools', {}) if project else {}
    defaults = load_workspace_tools(paths)
    found = {}
    for name in TOOL_NAMES:
        explicit = tools.get(name) or defaults.get(name)
        executable = explicit or next((path for cmd in COMMANDS[name] if (path := shutil.which(cmd))), '')
        origin = ('项目配置' if name in tools else '工作区配置') if explicit else '系统 PATH'
        if not executable and name in {'dotnet', 'unity'}:
            program = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))
            candidates = [program / 'dotnet/dotnet.exe'] if name == 'dotnet' else sorted((program / 'Unity/Hub/Editor').glob('*/Editor/Unity.exe'), reverse=True)
            executable = next((str(path) for path in candidates if path.is_file()), '')
            origin = '系统安装目录'
        path = Path(executable) if executable else None
        available = bool(path and path.is_file() and not path.is_symlink())
        if path and name == 'python' and 'windowsapps' in str(path).casefold():
            available = False
            origin = 'Windows 应用别名；请选择真实 Python'
        found[name] = {'path': str(path.resolve()) if available else executable or '', 'available': available, 'origin': origin}
    return found

def require_tool(project, name):
    record = discover_tools(project)[name]
    if not record['available']:
        raise RuntimeError(f'缺少已安装的 {name}；请在“环境与引擎”配置真实可执行文件。本功能不会下载工具。')
    return record['path']
