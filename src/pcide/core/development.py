"""Shared project factory and explicit development/build contracts."""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

from .paths import atomic_write_json

SCRIPT_LANGUAGES = frozenset({'python', 'zhxb', 'javascript', 'typescript'})
TOOL_NAMES = ('python', 'node', 'cc', 'cxx', 'cmake', 'dotnet', 'unity', 'godot')
TARGETS = {
    'script-standalone': ('脚本独立 EXE', '携带所需脚本运行时；保持现有字节码增量打包。'),
    'script-system': ('脚本使用系统环境', '仅交付源码和轻量启动器；目标电脑需安装 Python/Node，窗口项目还需 PySide6。'),
    'native-system': ('原生编译 / 系统 CRT', 'C/C++ 原生机器码；使用系统运行库，按需链接。'),
    'native-static': ('原生编译 / 静态 CRT', 'C/C++ 静态链接可用 CRT，优化体积；Windows 系统 DLL 仍是操作系统依赖。'),
    'cmake': ('CMake 增量构建', '使用系统 CMake 和工程定义的工具链；保留构建目录，最多 4 个并行任务。'),
    'dotnet-system': ('.NET 使用系统运行时', '框架依赖发布，不复制 .NET 运行时；目标机需匹配的 .NET。'),
    'dotnet-aot': ('.NET Native AOT', '编译为本机代码，裁剪并偏向体积；需已安装 AOT 工具与包。'),
    'web': ('网页资源发布', '只复制网页源码与资源，使用浏览器运行，不附带浏览器。'),
    'unity': ('Unity Windows 构建', '由外部 Unity Editor 构建；需许可证和 Windows Build Support。'),
    'godot': ('Godot Windows 导出', '由外部 Godot 导出；需已安装 Windows 导出模板。'),
}

@dataclass(frozen=True)
class Template:
    id: str
    label: str
    kind: str
    language: str
    mode: str
    entry: str
    targets: tuple[str, ...]
    description: str

TEMPLATES = tuple(
    Template(f'{lang}-{mode}', f'{label} · {title}', kind, lang, mode, f'src/main.{ext}',
             ('script-standalone', 'script-system'), description)
    for lang, label, ext in [('python', 'Python', 'py'), ('zhxb', '中文源码', 'zhxb'),
                             ('javascript', 'JavaScript', 'js'), ('typescript', 'TypeScript', 'ts')]
    for mode, title, kind, description in [('script', '脚本/自动化', 'script', '代码、调试、支持库和流程。'),
                                          ('form', '窗口软件', 'desktop', '可视化窗口、事件、后台任务和 AI 表单写入。')]
) + (
    Template('c-console', 'C · 控制台工具', 'native', 'c', 'code', 'src/main.c', ('native-static', 'native-system'), '小型本机工具，依赖系统编译器。'),
    Template('cpp-console', 'C++ · 控制台软件', 'native', 'cpp', 'code', 'src/main.cpp', ('native-static', 'native-system'), '标准库、线程、可复用模块与原生机器码。'),
    Template('cpp-win32', 'C++ · Win32 窗口软件', 'desktop', 'cpp', 'code', 'src/main.cpp', ('native-static', 'native-system'), '直接使用 Windows API，不携带 Qt 或脚本环境。'),
    Template('cpp-cmake', 'C++ · CMake 工程', 'native', 'cpp', 'code', 'src/main.cpp', ('cmake',), '可扩展的多文件工程与保留缓存的增量构建。'),
    Template('csharp-console', 'C# · 控制台软件', 'managed', 'csharp', 'code', 'src/Program.cs', ('dotnet-system', 'dotnet-aot'), '系统 .NET 发布或 Native AOT。'),
    Template('csharp-winforms', 'C# · Windows Forms', 'desktop', 'csharp', 'code', 'src/Program.cs', ('dotnet-system',), '原生桌面窗口；此模板不开放 WinForms Native AOT。'),
    Template('web-app', 'HTML/JS · 网页应用与小游戏', 'web', 'html', 'code', 'src/index.html', ('web',), '浏览器应用、Canvas 游戏和无需打包环境的资源发布。'),
    Template('unity-2d', 'Unity · 2D 游戏', 'game', 'csharp', 'engine', 'Assets/Scripts/GameController.cs', ('unity',), 'Unity 负责场景/物理/渲染，IDE 编辑 C# 并驱动外部引擎。'),
    Template('unity-3d', 'Unity · 3D 游戏', 'game', 'csharp', 'engine', 'Assets/Scripts/GameController.cs', ('unity',), '含场景生成与 Windows 构建脚本；Unity 首次导入需本机依赖。'),
    Template('godot-2d', 'Godot · 2D 游戏', 'game', 'gdscript', 'engine', 'src/main.gd', ('godot',), '完整 project.godot、场景、GDScript 和导出预设。'),
    Template('godot-3d', 'Godot · 3D 游戏', 'game', 'gdscript', 'engine', 'src/main.gd', ('godot',), '包含摄像机、光源、场景和 Windows 导出预设。'),
)
TEMPLATE_MAP = {item.id: item for item in TEMPLATES}

def template_for(project):
    raw = project.manifest.get('development', {})
    return TEMPLATE_MAP[raw.get('template', project.manifest['language'] + '-form')]

def validate_development(raw, language):
    if raw is None:
        if language not in SCRIPT_LANGUAGES:
            raise ValueError('通用软件工程必须声明 development 模板')
        raw = {'version': 1, 'template': language + '-form'}
    if not isinstance(raw, dict) or type(raw.get('version', 1)) is not int or raw.get('version', 1) != 1:
        raise ValueError('开发配置版本无效')
    if set(raw) - {'version', 'template', 'target', 'configuration', 'jobs', 'tools', 'engine_root'}:
        raise ValueError('开发配置包含未知字段')
    template = TEMPLATE_MAP.get(raw.get('template', ''))
    if template is None or template.language != language:
        raise ValueError('工程模板与语言不匹配')
    target = raw.get('target', template.targets[0])
    if target not in template.targets:
        raise ValueError('此工程不支持选择的编译方式')
    jobs = raw.get('jobs', min(4, os.cpu_count() or 1))
    if type(jobs) is not int or not 1 <= jobs <= 4 or raw.get('configuration', 'Release') not in {'Debug', 'Release'}:
        raise ValueError('并行数应为 1..4，配置应为 Debug/Release')
    if target in {'script-standalone','script-system','web','unity'} and raw.get('configuration','Release')!='Release':
        raise ValueError('此发布目标仅支持Release；脚本F4/引擎编辑器提供调试')
    tools = raw.get('tools', {})
    if not isinstance(tools, dict) or set(tools) - set(TOOL_NAMES):
        raise ValueError('工具配置名称无效')
    for path in tools.values():
        if not isinstance(path, str) or not Path(path).is_absolute() or '\x00' in path or Path(path).suffix.lower() != '.exe':
            raise ValueError('工具路径必须是完整 .exe 路径')
    engine_root = raw.get('engine_root', '')
    if not isinstance(engine_root, str) or engine_root and (template.mode != 'engine' or not Path(engine_root).is_absolute() or '\x00' in engine_root):
        raise ValueError('引擎工程路径无效')
    return {'version': 1, 'template': template.id, 'target': target, 'configuration': raw.get('configuration', 'Release'),
            'jobs': jobs, 'tools': dict(tools), 'engine_root': engine_root}

def create_project(paths, name, template_id):
    from .project import DEFAULT_FORM, Project, valid_file_name
    template = TEMPLATE_MAP.get(template_id)
    if template is None or not valid_file_name(name):
        raise ValueError('项目名称或模板无效')
    root = paths.project(name)
    if root.is_symlink() or not root.resolve().is_relative_to(paths.projects.resolve()) or root.exists() and any(root.iterdir()):
        raise ValueError('目标工程必须是项目目录内的空目录')
    dev = validate_development({'version': 1, 'template': template.id}, template.language)
    if template.language in SCRIPT_LANGUAGES:
        project = Project.create(paths, name, template.language)
        project.manifest['development'] = dev
        if template.mode == 'script':
            form = copy.deepcopy(DEFAULT_FORM)
            form['form']['events'] = {}
            project.save_form(form)
            project.save_flow({'version':1,'nodes':[],'edges':[]})
            source = { 'python': 'print("工具已就绪")\n', 'zhxb': '.版本 2\n.子程序 主程序\n输出("工具已就绪")\n',
                       'javascript': 'console.log("工具已就绪");\n', 'typescript': 'const message: string = "工具已就绪";\nconsole.log(message);\n'}[template.language]
            project.entry_path.write_text(source, encoding='utf-8')
    else:
        project = Project(root, {'schema': 1, 'name': root.name, 'language': template.language, 'entry': template.entry,
            'modules': [], 'plugins': [], 'permissions': [], 'execution': {'timeout_seconds': 120, 'max_output_lines': 5000}, 'development': dev})
        for folder in ('.pcide', 'src', 'resources'):
            (root / folder).mkdir(parents=True, exist_ok=True)
        for relative, content in template_files(template).items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8', newline='\n')
    if template.kind=='game':
        engine='unity' if template.id.startswith('unity') else 'godot'
        project.manifest['platform']['capabilities']['game'].update(enabled=True,backends=[engine])
    project.save_manifest()
    (root / 'README.md').write_text(f'# {name}\n\n{template.label}\n\n{template.description}\n\n'
        'F5 运行，编译菜单选择发布方式，停止按钮取消任务；环境与引擎菜单可配置已有系统工具。\n'
        '修改源码后再次运行/构建即为迭代。引擎工程可在外部编辑器修改并通过“重新载入磁盘内容”同步。\n', encoding='utf-8')
    return project

def template_files(template):
    if template.id.startswith('unity-'):
        from .engines import unity_files
        return unity_files(template.id.endswith('3d'))
    if template.id.startswith('godot-'):
        from .engines import godot_files
        return godot_files(template.id.endswith('3d'))
    if template.language == 'c':
        return {template.entry: '#include <stdio.h>\nint main(void) { puts("Native tool ready"); return 0; }\n'}
    if template.id == 'cpp-win32':
        return {template.entry: '#define UNICODE\n#include <windows.h>\nint WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {\n    MessageBoxW(nullptr, L"原生窗口已就绪", L"PCIDE", MB_OK);\n    return 0;\n}\n'}
    if template.language == 'cpp':
        files = {template.entry: '#include <iostream>\nint main() { std::cout << "Native software ready\\n"; }\n'}
        if template.id == 'cpp-cmake':
            files['CMakeLists.txt'] = ('cmake_minimum_required(VERSION 3.16)\nproject(PCIDEApp LANGUAGES CXX)\n'
                'set(CMAKE_CXX_STANDARD 17)\nfile(GLOB_RECURSE APP_SOURCES CONFIGURE_DEPENDS src/*.cpp)\n'
                'add_executable(app ${APP_SOURCES})\nset_target_properties(app PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")\n')
        return files
    if template.language == 'csharp':
        window = template.id == 'csharp-winforms'
        source = ('using System;\nusing System.Windows.Forms;\ninternal static class Program {\n    [STAThread]\n    static void Main() {\n'
                  '        Application.EnableVisualStyles();\n        using var form = new Form { Text = "PCIDE", Width = 640, Height = 400 };\n'
                  '        form.Controls.Add(new Label { Text = "窗口已就绪", AutoSize = true, Left = 30, Top = 30 });\n'
                  '        Application.Run(form);\n    }\n}\n') if window else 'using System;\nConsole.WriteLine("Managed software ready");\n'
        return {template.entry: source, 'app.csproj': '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n'
            f'    <OutputType>{"WinExe" if window else "Exe"}</OutputType>\n    <TargetFramework>{"net8.0-windows" if window else "net8.0"}</TargetFramework>\n'
            '    <ImplicitUsings>enable</ImplicitUsings>\n    <Nullable>enable</Nullable>\n'
            + ('    <UseWindowsForms>true</UseWindowsForms>\n' if window else '') + '  </PropertyGroup>\n</Project>\n',
            'NuGet.Config': '<configuration><packageSources><clear /></packageSources></configuration>\n'}
    return {template.entry: '<!doctype html>\n<html lang="zh-CN"><meta charset="utf-8"><title>PCIDE 应用</title>\n'
        '<style>body{font:18px system-ui;margin:3rem}button{padding:1rem}</style>\n<h1>网页应用</h1>\n'
        '<button id="run">点击运行</button><p id="status">就绪</p>\n<script>\nlet count=0;\n'
        'document.querySelector("#run").onclick=()=>document.querySelector("#status").textContent=`已点击 ${++count} 次`;\n</script></html>\n'}
