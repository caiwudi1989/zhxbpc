from __future__ import annotations

import argparse
import ast
import copy
import json
import keyword
import os
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
    QSplitter, QStyle, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout, QWidget,
    QMainWindow, QMenu, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QCheckBox, QToolButton, QPushButton)

from pcide.core.paths import IDE_VERSION, Paths, atomic_write_json, read_json
from pcide.core.project import Project, ProjectError, validate_form, valid_file_name, valid_name
from pcide.core.runner import ScriptRunner
from pcide.ui.designer import FormDesigner, Toolbox
from pcide.ui.editor import CodeEditor, register_editor_scheme
from pcide.ui.flow_canvas import FlowCanvas
from pcide.ui.form_runtime import RuntimeForm, RuntimeWindowManager
from pcide.ui.properties import PropertyPanel

PAGE_HINTS = {
    "code": "编辑当前文件；Ctrl+S 保存，Ctrl+F 查找，Ctrl+H 替换，Ctrl+G 跳转。脚本子程序可编辑参数和局部变量。",
    "design": "从控件箱添加组件。多选后使用“设计 → 排列”，在属性页修改位置、尺寸及事件。窗口菜单在“设计 → 窗口菜单编辑器”编辑。",
    "flow": "双击节点修改编号、名称及参数；连线箭头表示执行方向。Delete 删除选中节点或连线，保存后可运行。",
    "debug": "暂停时查看变量和调用表。双击或回车跳转调用位置及断点；变量只读，断点变化用于下次调试启动。",
    "data": "按类别编辑变量、常量、类型和 DLL 定义；参数由调用方传入，局部变量在子程序内初始化。成员及参数通过对应按钮编辑。",
    "resources": "管理工程 resources 中的实际文件。可导入、搜索、预览、复制相对路径、重命名或删除；二进制文件不作为源码打开。",
    "vision": "导入图片后标注或识别；模型测试和训练依赖真实模型及配置。模拟结果只用于流程检查。",
    "output": "脚本、流程、编译与工具共用一份有界输出。可在下方清空或导出日志；原生/C#运行后可发送控制台输入。",
    "library": "选择条目查看说明、调用格式和示例；双击或拖放插入代码。加入、配置和帮助位于上方；EC/FNE专用桥接尚未实现。",
    "program": "双击文件、窗口、子程序或数据分类进入对应页面；右键提供添加、导入、重命名和删除。入口及内部配置受保护。",
    "properties": "选择窗口或组件后编辑真实属性；事件下拉框绑定处理子程序，双击设计组件可创建并进入事件代码。",
    "snippets": "当前开发语言的参考代码；可搜索、双击、拖放或右键查看完整说明，使用前填写工程中的实际参数。",
    "welcome": "选择开发类型、模板及发布目标，输入工程名称后新建；可打开已有工程、示例中心或配置已安装工具。",
}


class Signals(QObject):
    message = Signal(dict)
    done = Signal(str, int, str)
    task = Signal(str, object, str)
    tool = Signal(str, object)
    tool_output = Signal(str, str)


class Task(QRunnable):
    def __init__(self, token, function, signals):
        super().__init__()
        self.token, self.function, self.signals = token, function, signals

    def run(self):
        try:
            self.signals.task.emit(self.token, self.function(), "")
        except Exception as exc:
            self.signals.task.emit(self.token, None, str(exc))


class MainWindow(QMainWindow):
    def __init__(self, project, paths):
        super().__init__()
        self.paths = paths.ensure()
        self.project = project or self._default_project()
        self.current_form_path = self.project.form_path
        self.runner = ScriptRunner()
        from pcide.core.flow import FlowRunner
        from pcide.core.plugins import PluginRegistry
        self.flow_runner = FlowRunner()
        self.registry = PluginRegistry(self.project.root, self.project.manifest.get("permissions", []))
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.build_cancel = threading.Event()
        self.tool_sessions = {}
        self.last_artifact = None
        self.busy = False
        self.token = str(self.project.root)
        self.closing = False
        self._project_closed = False
        self.dirty = False
        self.current_control = ""
        self.breakpoints = {}
        self.runtime_form = None
        self.runtime_manager = None
        self.window_actions = []
        self.signals = Signals(self)
        self.signals.message.connect(self._runtime_message)
        self.signals.done.connect(self._runtime_done)
        self.signals.task.connect(self._task_done)
        self.signals.tool.connect(self._tool_done)
        self.signals.tool_output.connect(self._tool_output)
        self.resize(1500, 940)
        self.setMinimumSize(1060, 660)
        self._build_ui()
        self._load_project()

    def _default_project(self):
        target = self.paths.project("HelloAutomation")
        return Project.open(target) if (target / ".pcide" / "project.json").exists() else Project.create(self.paths, "HelloAutomation")

    def _action(self, text, callback, icon=None, shortcut=None):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(text)
        action.triggered.connect(callback)
        action.hovered.connect(lambda: self._set_hint(text, action.toolTip()))
        return action

    def _build_ui(self):
        toolbar = QToolBar("工具", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        style = QStyle.StandardPixmap
        actions = [
            self._action("新建项目", self.new_project, style.SP_FileIcon, "Ctrl+N"),
            self._action("打开项目", self.open_project, style.SP_DirOpenIcon, "Ctrl+O"),
            self._action("保存", self.save_all, style.SP_DialogSaveButton, "Ctrl+S"),
            self._action("运行", self.run_script, style.SP_MediaPlay, "F5"),
            self._action("调试", self.debug_script, style.SP_ComputerIcon, "F4"),
            self._action("停止", self.stop_script, style.SP_MediaStop, "Shift+F5"),
            self._action("预览", self.preview, style.SP_DesktopIcon),
            self._action("AI助手", self.open_ai_assistant, style.SP_DialogHelpButton, "Ctrl+Alt+A"),
            self._action("编译 / 静态编译", self.build, style.SP_DriveHDIcon, 'Ctrl+B'),
        ]
        for action in actions:
            toolbar.addAction(action)
        self.debug_action = actions[4]
        self.preview_action = actions[6]
        self._routine_actions = []
        self._debug_actions = [self.debug_action]
        self._engine_actions = []
        file_menu = self.menuBar().addMenu("项目")
        for action in actions[:3]:
            file_menu.addAction(action)
        file_menu.addAction(self._action("项目另存为", self.save_project_as, shortcut="Ctrl+Alt+Shift+S"))
        file_menu.addAction(self._action("导入项目", self.import_project))
        file_menu.addAction(self._action("重命名项目", self.rename_project))
        file_menu.addAction(self._action("关闭项目", self.close_project, shortcut="Ctrl+Alt+W"))
        file_menu.addAction(self._action("删除项目", self.delete_project))
        file_menu.addAction(self._action('欢迎页 / 开发类型',self.show_welcome))
        file_menu.addAction(self._action('重新载入磁盘内容',self.reload_project))
        file_menu.addAction(self._action('新建源码文件', self.new_source_file))
        compile_menu=self.menuBar().addMenu('编译')
        compile_menu.addAction(actions[-1])
        compile_menu.addAction(self._action('使用当前设置增量编译',self.quick_build,shortcut='Ctrl+Shift+B'))
        compile_menu.addAction(self._action('重新构建',lambda:self.quick_build(force=True)))
        compile_menu.addAction(self._action('取消编译 / 停止外部工具',self.cancel_tools))
        compile_menu.addAction(self._action('查看最近产物',self.show_build_artifact))
        code_menu = self.menuBar().addMenu("代码")
        code_menu.addAction(self._action("撤销", self.editor_undo, shortcut="Ctrl+Z"))
        code_menu.addAction(self._action("重做", self.editor_redo, shortcut="Ctrl+Y"))
        code_menu.addAction(self._action("查找", lambda: self.editor.show_find(False), shortcut="Ctrl+F"))
        code_menu.addAction(self._action("查找替换", lambda: self.editor.show_find(True), shortcut="Ctrl+H"))
        code_menu.addAction(self._action("替换当前文件", self.replace_in_editor))
        code_menu.addAction(self._action("保存当前文件为", self.save_editor_as, shortcut='Ctrl+Shift+S'))
        code_menu.addAction(self._action('关闭当前代码页',lambda:self._close_code_tab(self.tabs.currentIndex()),shortcut='Ctrl+W'))
        for title, callback, shortcut in (('编辑当前子程序参数', lambda:self.editor.request_parameters(), 'Ctrl+Alt+P'),
                                          ('添加当前子程序局部变量', lambda:self.editor.add_local(), 'Ctrl+Alt+V')):
            action = self._action(title, callback, shortcut=shortcut)
            self._routine_actions.append(action)
            code_menu.addAction(action)
        code_menu.addAction(self._action('全部收缩',lambda:self.editor.fold_all(True),shortcut='Ctrl+Alt+['))
        code_menu.addAction(self._action('全部展开',lambda:self.editor.fold_all(False),shortcut='Ctrl+Alt+]'))
        code_menu.addAction(self._action('注释/取消注释',lambda:self.editor.toggle_comment(),shortcut='Ctrl+/'))
        code_menu.addAction(self._action('切换设计/代码视图',self.switch_workspace,shortcut='Ctrl+E'))
        code_menu.addAction(self._action("跳转到行", self.goto_editor_line, shortcut="Ctrl+G"))
        edit_menu = self.menuBar().addMenu("设计")
        self.design_menu = edit_menu
        designer_shortcuts=[]
        for name, callback, shortcut in [
            ("撤销", lambda: self.designer.undo(), None),
            ("重做", lambda: self.designer.redo(), None),
            ("复制控件", lambda: self.designer.duplicate(), "Ctrl+D"),
            ("删除控件", lambda: self.designer.delete_selected(), "Delete")]:
            action=self._action(name, callback, shortcut=shortcut)
            if shortcut:
                action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                designer_shortcuts.append(action)
            edit_menu.addAction(action)
        for title, callback, shortcut in (("剪贴板复制控件", lambda: self.designer.copy_selected(), "Ctrl+C"),
                                          ("粘贴控件", lambda: self.designer.paste_controls(), "Ctrl+V"),
                                          ("选择全部控件", lambda: self.designer.select_all(), "Ctrl+A")):
            action = self._action(title, callback, shortcut=shortcut)
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            designer_shortcuts.append(action)
            edit_menu.addAction(action)
        from pcide.ui.designer import ARRANGEMENTS
        self.arrange_menu = QMenu("排列", edit_menu)
        edit_menu.addMenu(self.arrange_menu)
        arrange_menu = self.arrange_menu
        self._arrangement_actions = []
        for title, mode in ARRANGEMENTS:
            action = self._action(title, lambda _checked=False, value=mode: self.designer.align(value))
            action.setToolTip("同一父容器内排列所选控件；对齐及等大以工程顺序中的首个选中控件为参照。等间距需要至少三个控件。")
            self._arrangement_actions.append(action)
            arrange_menu.addAction(action)
        arrange_menu.addSeparator()
        for title, front in (("置于顶层", True), ("置于底层", False)):
            action = self._action(title, lambda _checked=False, value=front: self.designer.change_order(value))
            self._arrangement_actions.append(action)
            arrange_menu.addAction(action)
        edit_menu.addAction(self._action("窗口菜单编辑器", self.edit_window_menu, shortcut="Ctrl+Alt+M"))
        grid = self._action("显示网格", self.toggle_grid)
        grid.setCheckable(True)
        grid.setChecked(True)
        edit_menu.addAction(grid)
        snap = self._action("网格吸附", self.toggle_snap)
        snap.setCheckable(True)
        snap.setChecked(True)
        edit_menu.addAction(snap)
        debug_menu = self.menuBar().addMenu("调试")
        for action in actions[3:6]:
            debug_menu.addAction(action)
        for title, command, shortcut in (("继续", "continue", "F8"), ("单步进入", "step", "F11"),
                                         ("单步跳过", "next", "F10"), ("单步跳出", "out", "Shift+F11")):
            action = self._action(title, lambda _, cmd=command: self.debug_command(cmd), shortcut=shortcut)
            self._debug_actions.append(action)
            debug_menu.addAction(action)
        for action in (self._action("切换断点", lambda: self.editor.toggle_breakpoint_at_cursor(), shortcut="F9"),
                       self._action("回放最近会话", self.replay)):
            self._debug_actions.append(action)
            debug_menu.addAction(action)
        tools = self.menuBar().addMenu("扩展")
        tools.addAction(self._action("支持库配置", lambda: self.open_libraries(0)))
        tools.addAction(self._action("加入支持库/模块", lambda: self.open_libraries(1)))
        tools.addAction(self._action("支持库与模块使用帮助", lambda: self.open_libraries(2)))
        tools.addAction(self._action("安装插件包", self.install_plugin_archive))
        tools.addAction(self._action("示例插件", self.load_plugins))
        tools.addAction(self._action("卸载插件", self.unload_plugins))
        tools.addAction(self._action("DEX 浏览", self.browse_dex))
        tools.addAction(self._action("Android 远程主机", self.test_dex))
        environment_menu = self.menuBar().addMenu("环境")
        environment_menu.addAction(self._action("项目环境", self.show_environment))
        environment_menu.addAction(self._action('系统工具与游戏引擎',self.show_tools))
        engine_menu=self.menuBar().addMenu('游戏引擎')
        engine_menu.addAction(self._action('引擎配置 / 绑定已有工程',self.show_tools))
        engine_menu.addAction(self._action('接入已有 Unity 工程',self.connect_unity_project))
        engine_menu.addAction(self._action('接入已有 Godot 工程',lambda:self.connect_engine_project('godot')))
        for action in (self._action('打开当前引擎编辑器',lambda:self.launch_engine('editor')),
                       self._action('运行游戏 / Unity 编辑器',self.run_script),
                       self._action('构建 Windows 游戏',self.build),
                       self._action('停止引擎与游戏',self.cancel_tools)):
            self._engine_actions.append(action)
            engine_menu.addAction(action)
        environment_menu.addAction(self._action("重新扫描支持库", self._refresh_support_library))
        help_menu=self.menuBar().addMenu('帮助')
        help_menu.addAction(self._action('快捷键与操作说明',self.show_shortcuts,shortcut='F1'))
        help_menu.addAction(self._action('参数、局部变量与支持库',lambda:self.open_libraries(2)))
        help_menu.addAction(self._action('完整示例中心（100个）',self.open_examples))
        help_menu.addAction(self._action('软件、游戏、编译与迭代说明',self.show_development_help))
        help_menu.addAction(self._action('页面内容与操作说明', self.show_page_help))
        help_menu.addAction(self._action("查看当前提示", lambda: self.show_page("hint"), shortcut="Ctrl+Alt+H"))
        platform_menu = self.menuBar().addMenu("平台")
        platform_menu.addAction(self._action("平台能力", self.show_platform_capabilities))
        platform_menu.addAction(self._action("数据库设计器", self.open_database_designer))
        platform_menu.addAction(self._action("API 中心", self.open_api_center))
        ai_menu = self.menuBar().addMenu("AI")
        ai_menu.addAction(self._action("AI 编程助手", self.open_ai_assistant))
        self.window_menu = self.menuBar().addMenu("窗口")
        self.window_menu.addAction(self._action("新建窗口", self.new_window))
        self.window_menu.addAction(self._action("重命名当前窗口", self.rename_current_window))
        self.window_menu.addAction(self._action("删除当前窗口", self.delete_current_window))

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        self.toolbox = Toolbox()
        self.toolbox.itemDoubleClicked.connect(self._add_toolbox_item)
        self.left_catalog = QTabWidget()
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self.project_context_menu)
        self.project_tree.itemDoubleClicked.connect(self._open_program_item)
        self.program_tree = self.project_tree
        self.left_catalog.addTab(self.project_tree, "程序")
        self.routine_list = QTreeWidget()
        self.routine_list.setHeaderLabels(["名称", "类型"])
        self.routine_list.itemDoubleClicked.connect(self._open_routine)
        self.routine_list.setVisible(False)
        left_layout.addWidget(self.left_catalog)
        self.designer = FormDesigner()
        self.designer.arrangement_actions = self._arrangement_actions
        for action in designer_shortcuts:
            self.designer.addAction(action)
        self.designer.selected.connect(self.select_control)
        self.designer.changed.connect(self.mark_dirty)
        self.designer.event_requested.connect(self.goto_event)
        self.toolbox.controlRequested.connect(self.designer.add)
        self.editor = CodeEditor(self.paths)
        self.editor.changed.connect(lambda _: self.mark_dirty())
        self.editor.breakpoint.connect(self.toggle_breakpoint)
        self.editor.routine_metadata.connect(self._save_routine_metadata)
        self.editor.parameters_requested.connect(self.edit_routine_parameters)
        self.editor.cursor.connect(self.reverse_navigation)
        self.editor.error.connect(self.log)
        self.editor.document_loaded.connect(self._editor_document_loaded)
        self.editor.ready.connect(lambda: self._editor_document_loaded(self.editor.path or ''))
        self._editor_toolbar = QToolBar("代码编辑", self)
        self._editor_toolbar.setMovable(False)
        self._editor_toolbar.addAction(self._action("智能补全", self.trigger_completion, shortcut="Ctrl+Space"))
        self._editor_toolbar.addAction(self._action("折叠/展开区域", self.toggle_editor_fold, shortcut="Ctrl+K"))
        self._editor_toolbar.addAction(self._action("格式化当前文件", self.format_editor, shortcut="Ctrl+Shift+F"))
        chinese_view = self._action("中文子程序视图", self.toggle_chinese_editor)
        self.chinese_view_action = chinese_view
        chinese_view.setCheckable(True)
        chinese_view.setChecked(True)
        self._editor_toolbar.addAction(chinese_view)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._editor_toolbar)
        self.flow = FlowCanvas()
        self.flow.changed.connect(self.mark_dirty)
        self.flow.run_requested.connect(self.run_flow)
        self.flow.error.connect(self.log)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(2000)
        self.output_panel = QPlainTextEdit()
        self.output_panel.setReadOnly(True)
        self.output_panel.document().setMaximumBlockCount(2000)
        self.output.setDocument(self.output_panel.document())
        self.hint_panel = QPlainTextEdit()
        self.hint_panel.setReadOnly(True)
        self.hint_panel.setPlaceholderText("选择页面、命令或组件，查看当前操作说明。")
        self.status_tabs = QTabWidget()
        self.status_tabs.addTab(self.hint_panel, "提示")
        self.status_tabs.addTab(self.output_panel, "输出")
        self.status_tabs.setCurrentWidget(self.output_panel)
        self.variables = QTreeWidget()
        self.variables.setHeaderLabels(["变量", "值"])
        self.stack = QTreeWidget()
        self.stack.setHeaderLabels(["函数", "位置"])
        self.stack.itemDoubleClicked.connect(self.goto_stack)
        self.breakpoint_tree = QTreeWidget()
        self.breakpoint_tree.setHeaderLabels(['文件', '行号'])
        self.breakpoint_tree.setColumnWidth(0, 450)
        self.breakpoint_tree.itemDoubleClicked.connect(self.goto_breakpoint)
        for tree, callback in ((self.stack, self.goto_stack), (self.breakpoint_tree, self.goto_breakpoint)):
            for key in ("Return", "Enter"):
                shortcut = QShortcut(QKeySequence(key), tree)
                shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                shortcut.activated.connect(lambda target=tree, goto=callback:
                    goto(target.currentItem(), target.currentColumn()) if target.currentItem() else None)
        self.debug_status = QLabel('未运行；变量和调用表在脚本暂停时显示。')
        debug_split = QWidget()
        debug_layout = QVBoxLayout(debug_split)
        debug_bar = QHBoxLayout()
        debug_bar.addWidget(self.debug_status, 1)
        clear_breakpoints = QPushButton('清除断点')
        clear_breakpoints.setToolTip('断点变更用于下一次调试启动')
        clear_breakpoints.clicked.connect(self.clear_breakpoints)
        debug_bar.addWidget(clear_breakpoints)
        debug_layout.addLayout(debug_bar)
        self.debug_tabs = QTabWidget()
        self.debug_tabs.addTab(self.variables, '变量（只读）')
        self.debug_tabs.addTab(self.stack, '调用表')
        self.debug_tabs.addTab(self.breakpoint_tree, '断点')
        debug_layout.addWidget(self.debug_tabs)
        self.debug_host = debug_split
        from pcide.ui.vision_panel import VisionPanel
        from pcide.ui.data_panel import DataPanel
        self.vision = VisionPanel(self.project, self.paths)
        self.vision.message.connect(self.log)
        self.vision.execute_requested.connect(self.submit)
        self.data_panel = DataPanel(self.project)
        self.data_panel.changed.connect(self._save_program_data)
        self.data_panel.generated.connect(self._show_generated_data)
        from pcide.ui.resource_panel import ResourcePanel
        self.resources_panel = ResourcePanel(self.project)
        self.resources_panel.import_requested.connect(lambda: self._import_project_file(self.project.root / 'resources'))
        self.resources_panel.delete_requested.connect(self._delete_project_path)
        self.resources_panel.rename_requested.connect(self._rename_project_path)
        self.resources_panel.changed.connect(self._refresh_resources)
        from pcide.ui.catalog_tree import LibraryTree
        self.support_library = LibraryTree()
        self.support_library.setHeaderLabels(["支持库内容", "说明"])
        self.support_library.setColumnHidden(1, True)
        self.support_library.setColumnWidth(0,210)
        self.support_library.setAlternatingRowColors(True)
        self.support_library.itemDoubleClicked.connect(self._insert_library_item)
        self.support_library.customContextMenuRequested.connect(self._support_context_menu)
        self.support_library.currentItemChanged.connect(self._show_support_item_details)
        self.support_host = QWidget()
        support_layout = QVBoxLayout(self.support_host)
        support_layout.setContentsMargins(2, 2, 2, 2)
        support_bar = QHBoxLayout()
        for text, page in (("加入", 1), ("配置", 0), ("帮助", 2)):
            button = QToolButton(text=text)
            button.clicked.connect(lambda _, p=page: self.open_libraries(p))
            support_bar.addWidget(button)
        support_layout.addLayout(support_bar)
        self.support_search = QLineEdit()
        self.support_search.setPlaceholderText("搜索库、命令、类型或常量")
        self.support_search.textChanged.connect(self._filter_support_library)
        support_layout.addWidget(self.support_search)
        support_layout.addWidget(self.support_library)
        self.support_details = QPlainTextEdit()
        self.support_details.setReadOnly(True)
        self.support_details.setMaximumHeight(180)
        self.support_details.setPlaceholderText('选择命令、类型或常量，查看说明与调用格式')
        support_layout.addWidget(self.support_details)
        self.snippet_tree = LibraryTree()
        self.snippet_tree.setHeaderLabels(['代码片段', '说明'])
        self.snippet_tree.setColumnWidth(0, 180)
        self.snippet_tree.itemDoubleClicked.connect(self._insert_library_item)
        self.snippet_tree.customContextMenuRequested.connect(self._snippet_context_menu)
        self.snippet_tree.currentItemChanged.connect(self._show_support_item_details)
        self.snippet_host = QWidget()
        snippet_layout = QVBoxLayout(self.snippet_host)
        snippet_layout.setContentsMargins(2, 2, 2, 2)
        self.snippet_search = QLineEdit()
        self.snippet_search.setPlaceholderText('搜索当前语言代码片段')
        self.snippet_search.textChanged.connect(lambda text: self._filter_catalog_tree(self.snippet_tree, text))
        snippet_layout.addWidget(self.snippet_search)
        snippet_layout.addWidget(self.snippet_tree)
        self._refresh_support_library()
        self.right_tabs = QTabWidget()
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_code_tab)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._code_tab_menu)
        self.tabs.addTab(self.editor, "代码")
        self.tabs.addTab(self.flow, "流程")
        self.tabs.addTab(debug_split, "调试")
        self.tabs.addTab(self.output, "输出")
        self.tabs.addTab(self.vision, "视觉工作台")
        self.tabs.addTab(self.data_panel, "程序数据")
        self.tabs.addTab(self.resources_panel, '资源与外部文件')
        self.code_tabs = self.tabs
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setDocumentMode(True)
        self.workspace_tabs.addTab(self.designer, "界面设计")
        self.workspace_tabs.addTab(self.tabs, "代码工作区")
        from pcide.ui.development_dialogs import WelcomePage
        self.welcome = WelcomePage(self.paths,self)
        self.welcome.createRequested.connect(self.create_software_project)
        self.welcome.openRequested.connect(self.open_project_path)
        self.welcome.examplesRequested.connect(self.open_examples)
        self.welcome.toolsRequested.connect(self.show_tools)
        self.workspace_tabs.addTab(self.welcome,'欢迎')
        self.properties = PropertyPanel()
        self.properties.property_changed.connect(self.change_property)
        self.properties.form_changed.connect(self.change_form)
        self.properties.event_changed.connect(self.change_event)
        self.properties.event_requested.connect(self.goto_event)
        self.properties.selected.connect(self.designer.select)
        self.properties.menu_requested.connect(self.edit_window_menu)
        # Keep the tree for keyboard/drag insertion and expose a categorized
        # popup menu with standard icons for quick click-to-add workflows.
        toolbox_host = QWidget()
        toolbox_layout = QVBoxLayout(toolbox_host)
        toolbox_layout.setContentsMargins(2, 2, 2, 2)
        toolbox_bar = QHBoxLayout()
        toolbox_menu_button = QToolButton(text="控件菜单")
        toolbox_menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbox_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbox_menu_button.setMenu(self.toolbox.menu(toolbox_host))
        toolbox_bar.addWidget(toolbox_menu_button)
        toolbox_view_button = QToolButton(text="显示方式")
        toolbox_view_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbox_view_menu = QMenu(toolbox_view_button)
        text_mode = toolbox_view_menu.addAction("列表文字")
        icon_mode = toolbox_view_menu.addAction("图标列表")
        text_mode.triggered.connect(lambda: self.toolbox.set_display_mode("text"))
        icon_mode.triggered.connect(lambda: self.toolbox.set_display_mode("icon"))
        toolbox_view_button.setMenu(toolbox_view_menu)
        toolbox_bar.addWidget(toolbox_view_button)
        toolbox_bar.addStretch()
        toolbox_layout.addLayout(toolbox_bar)
        toolbox_layout.addWidget(self.toolbox)
        self.toolbox_host = toolbox_host
        self.right_tabs.addTab(toolbox_host, "控件箱")
        self.left_catalog.insertTab(0, self.support_host, "支持库")
        self.left_catalog.addTab(self.properties, "属性")
        self.left_catalog.addTab(self.snippet_host, "代码片段")
        self.left_catalog.setTabPosition(QTabWidget.TabPosition.South)
        self.pages = {
            'code': (self.editor, self.tabs, 'project', '代码编辑器'),
            'design': (self.designer, self.workspace_tabs, 'form', '界面设计'),
            'flow': (self.flow, self.tabs, 'script', '流程编辑器'),
            'debug': (self.debug_host, self.tabs, 'script', '调试 / 调用表 / 断点'),
            'data': (self.data_panel, self.tabs, 'script', '程序数据'),
            'resources': (self.resources_panel, self.tabs, 'project', '资源与外部文件'),
            'vision': (self.vision, self.tabs, 'script', '视觉工作台'),
            'output': (self.output, self.tabs, 'always', '输出'),
            'library': (self.support_host, self.left_catalog, 'project', '支持库'),
            'program': (self.project_tree, self.left_catalog, 'project', '程序夹'),
            'properties': (self.properties, self.left_catalog, 'form', '属性 / 事件 / 组件树'),
            'snippets': (self.snippet_host, self.left_catalog, 'snippets', '代码片段'),
            'welcome': (self.welcome, self.workspace_tabs, 'always', '欢迎页'),
            'hint': (self.hint_panel, self.status_tabs, 'always', '当前操作提示'),
        }
        self.view_menu = self.menuBar().addMenu('视图')
        self.page_actions = {}
        for key, (_, _, _, label) in self.pages.items():
            action = self._action(label, lambda _checked=False, page=key: self.show_page(page))
            self.page_actions[key] = action
            self.view_menu.addAction(action)
        self.data_summary = QTreeWidget()
        self.data_summary.setHeaderLabels(["变量 / 常量", "类型"])
        layout = QSplitter()
        layout.addWidget(left)
        layout.addWidget(self.workspace_tabs)
        layout.addWidget(self.right_tabs)
        layout.setSizes([280, 900, 310])
        output_box = QWidget()
        output_layout = QVBoxLayout(output_box)
        output_layout.setContentsMargins(4, 2, 4, 4)
        output_bar = QHBoxLayout()
        output_bar.addWidget(QLabel("提示 / 输出"), 1)
        for title, callback in (("清空输出", self.output.clear), ("导出日志", self.export_output)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            output_bar.addWidget(button)
        output_layout.addLayout(output_bar)
        output_layout.addWidget(self.status_tabs)
        console_row=QHBoxLayout()
        self.console_input=QLineEdit();self.console_input.setPlaceholderText('原生/C#控制台输入（F5运行后可发送；回车发送，Shift+F5停止）')
        self.console_input.setMaxLength(4096);self.console_input.setEnabled(False)
        self.console_input.returnPressed.connect(self.send_console_input)
        self.console_send=QPushButton('发送输入');self.console_send.setEnabled(False)
        self.console_send.clicked.connect(self.send_console_input)
        console_row.addWidget(self.console_input,1);console_row.addWidget(self.console_send)
        output_layout.addLayout(console_row)
        root_layout = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(layout)
        root_layout.addWidget(output_box)
        root_layout.setSizes([720, 180])
        self.setCentralWidget(root_layout)
        for tab_widget in (self.tabs, self.workspace_tabs, self.left_catalog, self.status_tabs):
            tab_widget.currentChanged.connect(lambda index, tabs=tab_widget: self._page_hint(tabs, index))
        self.statusBar().showMessage("就绪")
        self.project_label = QLabel()
        self.statusBar().addPermanentWidget(self.project_label)
        self.setStyleSheet("QMainWindow{background:#eef1f4} QMenuBar{background:#eef1f4;border-bottom:1px solid #c5ccd4} "
                          "QToolBar{spacing:4px;padding:2px;border-bottom:1px solid #c5ccd4;background:#f6f7f8} "
                          "QTreeWidget,QListWidget,QPlainTextEdit{border:1px solid #c2cad3;background:#fff} "
                          "QTabWidget::pane{border:1px solid #c2cad3;background:#fff} QTabBar::tab{padding:4px 12px} "
                          "QSplitter::handle{background:#cbd2da}")

    def _close_code_tab(self, index):
        widget = self.tabs.widget(index)
        if widget is self.output:
            return
        self.tabs.setTabVisible(index, False)
        self.tabs.setCurrentWidget(self.output)

    def _page_available(self, key):
        from pcide.core.development import SCRIPT_LANGUAGES, template_for
        mode = self.pages[key][2]
        opened = not self._project_closed
        if mode == 'always':
            return True
        if not opened:
            return False
        if mode == 'form':
            return template_for(self.project).mode == 'form'
        if mode == 'script':
            return self.project.manifest['language'] in SCRIPT_LANGUAGES
        if mode == 'snippets':
            return self.snippet_tree.topLevelItemCount() > 0
        return True

    def show_page(self, key):
        if not self._page_available(key):
            return False
        widget, tabs, _, _ = self.pages[key]
        tabs.setTabVisible(tabs.indexOf(widget), True)
        tabs.setCurrentWidget(widget)
        if tabs is self.tabs:
            self.workspace_tabs.setCurrentWidget(self.tabs)
        if key == 'resources':
            self._refresh_resources()
        if key != "hint":
            self._set_hint(self.pages[key][3], PAGE_HINTS.get(key, self.pages[key][3]))
        if key == "hint":
            self.hint_panel.setFocus()
        elif key == 'code':
            self.editor.focus_editor()
        return True

    def _set_hint(self, title, description):
        if hasattr(self, "hint_panel"):
            self.hint_panel.setPlainText((str(title) + "\n\n" + str(description))[:32000])

    def _page_hint(self, tabs, index):
        if not hasattr(self, "pages") or index < 0:
            return
        widget = tabs.widget(index)
        for key, (page, container, _, title) in self.pages.items():
            if page is widget and container is tabs and key != "hint":
                self._set_hint(title, PAGE_HINTS.get(key, title))
                break

    def export_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出当前日志", str(self.paths.logs / "ide-output.txt"), "文本文件 (*.txt)")
        if path:
            try:
                Path(path).write_text(self.output.toPlainText() + "\n", encoding="utf-8")
                self.statusBar().showMessage("日志已导出：" + path)
            except OSError as exc:
                self.log(str(exc))

    def _sync_project_pages(self):
        from pcide.core.development import SCRIPT_LANGUAGES, template_for
        opened = not self._project_closed
        scripted = opened and self.project.manifest['language'] in SCRIPT_LANGUAGES
        form_mode = opened and template_for(self.project).mode == 'form'
        for key, (widget, tabs, _, _) in self.pages.items():
            available = self._page_available(key)
            tabs.setTabVisible(tabs.indexOf(widget), available)
            self.page_actions[key].setEnabled(available)
        self.right_tabs.setVisible(form_mode)
        self.design_menu.setEnabled(form_mode)
        def enable_actions(menu):
            for action in menu.actions():
                if not action.isSeparator():
                    action.setEnabled(form_mode)
                if action.menu():
                    enable_actions(action.menu())
        enable_actions(self.design_menu)
        self.window_menu.setEnabled(form_mode)
        self.toolbox.setEnabled(form_mode)
        self.preview_action.setEnabled(form_mode)
        self.tabs.setEnabled(True)
        for action in self._debug_actions:
            action.setEnabled(scripted)
        for action in self._engine_actions:
            action.setEnabled(opened and template_for(self.project).mode == 'engine')
        self._sync_editor_view_action(self.editor.path)

    def _refresh_resources(self):
        self.resources_panel.set_project(self.project)

    def show_page_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('页面内容与操作说明')
        dialog.resize(820, 650)
        layout = QVBoxLayout(dialog)
        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        candidates = (self.paths.docs / '规范/pages.md', self.paths.resources / 'docs/pages.md')
        path = next((path for path in candidates if path.is_file()), None)
        viewer.setPlainText(path.read_text(encoding='utf-8') if path else '\n'.join(value[3] for value in self.pages.values()))
        layout.addWidget(viewer)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('关闭')
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _code_tab_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        menu = QMenu(self)
        close = menu.addAction("关闭标签页")
        if menu.exec(self.tabs.tabBar().mapToGlobal(position)) == close:
            self._close_code_tab(index)

    def _load_project(self):
        from pcide.core.development import SCRIPT_LANGUAGES, template_for
        scripted = self.project.manifest['language'] in SCRIPT_LANGUAGES
        form_mode = template_for(self.project).mode == 'form'
        self.variables.clear()
        self.stack.clear()
        self.debug_status.setText('未运行；变量和调用表在脚本暂停时显示。')
        self.breakpoints = {path: lines for path, lines in self.breakpoints.items() if Path(path).resolve().is_relative_to(self.project.root.resolve())}
        self._refresh_breakpoints()
        self._project_closed = False
        self.workspace_tabs.setEnabled(True)
        self.designer.setEnabled(True)
        self.tabs.setEnabled(True)
        self.editor.close_project()
        self.current_form_path = self.current_form_path if self.current_form_path.exists() else self.project.form_path
        self.designer.load(validate_form(read_json(self.current_form_path, self.project.load_form())))
        self.flow.load(self.project.load_flow())
        self.data_panel.project = self.project
        self.data_panel.load(self.project.load_data())
        self.editor.custom_types = [item['id'] for item in self.project.load_data()['types']]
        self.editor.set_startup_routines(self._startup_routine_names())
        self.editor.load(self.project.entry_path)
        self.editor.set_completion_items(self._completion_items())
        self.editor.set_routine_metadata(self._routine_metadata_index())
        self.project_tree.clear()
        self.resources_panel.set_project(self.project)
        root = QTreeWidgetItem(self.project_tree, [self.project.manifest["name"]])
        root.setData(0, Qt.ItemDataRole.UserRole, str(self.project.root))
        settings = QTreeWidgetItem(root, ["项目配置.json"])
        settings.setData(0, Qt.ItemDataRole.UserRole, str(self.project.ide_dir / "project.json"))
        labels = {"src": "代码", "ui": "界面", "flows": "流程", "plugins": "插件", "resources": "资源",
                  'database': '数据库', 'api': 'API 接口', 'models': '模型', 'providers': '能力提供者', 'game': '引擎资源'}
        folders = ["src"] + (["ui"] if form_mode else []) + (["flows", "plugins"] if scripted else []) + ["resources"]
        excluded = {'ui'} if not form_mode else set()
        if not scripted:
            excluded.update({'flows', 'plugins'})
        folders.extend(sorted(p.name for p in self.project.root.iterdir() if p.is_dir() and p.name not in folders and p.name not in {".pcide", "cache", 'Library','Temp','Logs','obj','bin','node_modules','.godot','build','.git'} and not p.is_symlink()))
        for folder in folders:
            if folder in excluded:
                continue
            node = QTreeWidgetItem(root, [labels.get(folder, folder)])
            node.setData(0, Qt.ItemDataRole.UserRole, str(self.project.root / folder))
            self._populate_project_tree(node, self.project.root / folder)
        for file in sorted(self.project.root.iterdir()):
            if file.is_file() and not file.is_symlink():
                item=QTreeWidgetItem(root,[file.name]);item.setData(0,Qt.ItemDataRole.UserRole,str(file))
        root.setExpanded(False)
        settings.setExpanded(True)
        program = QTreeWidgetItem(self.project_tree, ["程序数据" if scripted else "工程内容"])
        program.setData(0, Qt.ItemDataRole.UserRole + 2, "程序数据")
        for label in (("窗口",) if form_mode else ()) + (("模块引用表", "支持库配置") if scripted else ()) + ("资源与外部文件",):
            child = QTreeWidgetItem(program, [label])
            if label == "常量表":
                child.setData(0, Qt.ItemDataRole.UserRole + 3, "constants")
            elif label == "模块引用表":
                child.setData(0, Qt.ItemDataRole.UserRole + 3, "modules")
            elif label == "支持库配置":
                child.setData(0, Qt.ItemDataRole.UserRole + 3, "libraries")
            elif label == "资源与外部文件":
                child.setData(0, Qt.ItemDataRole.UserRole + 3, 'resources')
            elif label == "窗口":
                for form_path in self.project.window_paths():
                    window = QTreeWidgetItem(child, [self.project.load_window(form_path)["form"]["title"]])
                    window.setData(0, Qt.ItemDataRole.UserRole, str(form_path))
            child.setExpanded(label == "窗口")
        program.setExpanded(True)
        self.current_control = ""
        self.dirty = False
        self.project_label.setText(self.project.manifest["name"])
        self.setWindowTitle(f"PCIDE | {self.project.manifest['name']} | {IDE_VERSION}")
        self.vision.set_project(self.project)
        self._refresh_support_library()
        self._refresh_data_summary()
        self.select_control("")
        self._refresh_window_menu()
        self._refresh_routines()
        self._sync_project_pages()
        if not form_mode:
            self.workspace_tabs.setCurrentWidget(self.tabs)
            if not scripted and self._page_available('snippets'):
                self.show_page('snippets')
        if hasattr(self,'welcome'):self.welcome.refresh()
        root_index = self.project_tree.indexOfTopLevelItem(root)
        if root_index >= 0:
            self.project_tree.takeTopLevelItem(root_index)
            self.project_tree.addTopLevelItem(root)

    def _open_program_item(self, item, column=0):
        group = item.data(0, Qt.ItemDataRole.UserRole + 3)
        if group == 'resources':
            self.show_page('resources')
            return
        if group == "modules":
            from pcide.ui.module_dialog import ModuleDialog
            ModuleDialog(self.project, self).exec()
            self._libraries_changed()
            return
        if group == "libraries":
            self.open_libraries(0)
            return
        if group:
            self.data_panel.select_group(group)
            identity = item.data(0, Qt.ItemDataRole.UserRole + 4)
            if identity:
                for row, (_, value) in enumerate(self.data_panel.row_items):
                    if value == identity:
                        self.data_panel.table.selectRow(row)
                        break
            self.tabs.setTabVisible(self.tabs.indexOf(self.data_panel), True)
            self.tabs.setCurrentWidget(self.data_panel)
            self.workspace_tabs.setCurrentWidget(self.tabs)
            return
        line = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if isinstance(line, int):
            self._open_routine(item, column)
            return
        if item.data(0, Qt.ItemDataRole.UserRole):
            self.open_file(item, column)

    def _replace_program_section(self, title):
        for index in range(self.project_tree.topLevelItemCount() - 1, -1, -1):
            item = self.project_tree.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole + 2) == title:
                self.project_tree.takeTopLevelItem(index)
        section = QTreeWidgetItem(self.project_tree, [title])
        section.setData(0, Qt.ItemDataRole.UserRole + 2, title)
        section.setExpanded(title == "程序数据")
        return section

    def _completion_items(self):
        """Build the project symbol list shown by the editor's completion popup."""
        items = [
            {"label": name, "kind": "keyword", "detail": "关键字"}
            for name in (("如果", "否则", "循环", "返回", "真", "假", "空", "导入", "定义") if self.project.manifest['language'] in {'python','zhxb','javascript','typescript'} else ())
        ]
        try:
            data = self.project.load_data()
        except (OSError, ValueError, ProjectError):
            data = {"variables": [], "constants": [], "apis": []}
        for key, kind, detail in (("variables", "variable", "项目变量"), ("constants", "constant", "项目常量")):
            for value in data.get(key, []):
                if value.get("scope") == "local":
                    continue
                from pcide.core.data import reference_name
                label = reference_name(value)
                if label:
                    items.append({"label": label, "kind": kind, "detail": f"{detail} · {value.get('type', '')}",
                                  "documentation": value.get("description", "")})
        for value in data.get("apis", []):
            label = value.get("id") or value.get("label")
            if label:
                params = value.get("parameters", [])
                items.append({"label": label, "kind": "function", "detail": f"支持库函数 · {value.get('return_type', '')}",
                              "documentation": value.get("description", ""), "parameters": params,
                              "insertText": label + ("(${1})" if params else "()")})
        from pcide.core.libraries import SYSTEM_LIBRARIES, DEVELOPMENT_COMMANDS, load_libraries
        language = self.project.manifest['language']
        for label,category,code,description in DEVELOPMENT_COMMANDS.get(language,[]):
            items.append({'label':label,'kind':'function','detail':category,'documentation':description,'insertText':code})
        try:
            enabled = load_libraries(self.project)['system']
            for library in SYSTEM_LIBRARIES:
                if library['id'] not in enabled or language not in library.get('languages', {'python','zhxb','javascript','typescript'}):
                    continue
                for command in library['commands']:
                    code = command['code'].get(language)
                    if code:
                        items.append({'label': command['label'], 'kind': 'function', 'detail': library['name'],
                                      'documentation': command['description'], 'insertText': code})
            from pcide.core.modules import load_modules
            for module in load_modules(self.project)['modules']:
                if language in {'python', 'zhxb'}:
                    for name in module['exports']:
                        items.append({'label': module['id']+'.'+name, 'kind': 'function', 'detail': '模块 '+module['version'],
                                      'insertText': module['id']+'.'+name+'(${1})'})
        except (OSError, ValueError) as exc:
            self.log('支持库补全：'+str(exc))
        # Public routines are project symbols and can be called from every
        # source file.  The editor writes this small explicit index on edit.
        try:
            routines = json.loads((self.project.ide_dir / "routines.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            routines = {}
        for value in routines.values() if isinstance(routines, dict) else []:
            if isinstance(value, dict) and value.get("public") and value.get("name"):
                items.append({"label": value["name"], "kind": "function", "detail": "公开子程序",
                              "documentation": value.get("remark", ""), "parameters": value.get("parameters", [])})
        for control in self.designer.form.get("controls", []):
            label = control.get("name") or control.get("id")
            if label:
                items.append({"label": label, "kind": "field", "detail": f"窗口控件 · {control.get('type', '')}"})
            for handler in control.get("events", {}).values():
                if handler:
                    items.append({"label": handler, "kind": "function", "detail": "事件处理子程序"})
        for handler in self.designer.form.get("form", {}).get("events", {}).values():
            if handler:
                items.append({"label": handler, "kind": "function", "detail": "窗口事件处理子程序"})
        return items

    def _routine_metadata_index(self):
        try:
            value = json.loads((self.project.ide_dir / "routines.json").read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return {}
            from pcide.core.routines import reconcile
            for source in self.project.scripts():
                file = source.relative_to(self.project.root).as_posix()
                text = self.editor.documents.get(str(source.resolve())) if hasattr(self, "editor") else None
                value = reconcile(value, file, text if text is not None else source.read_text(encoding="utf-8"), source.suffix)
            return value
        except (OSError, ValueError):
            return {}

    def _save_routine_metadata(self, uri, raw):
        """Persist editable routine metadata and refresh cross-file completion."""
        try:
            path = Path(uri).resolve()
            if not path.is_relative_to(self.project.root.resolve()):
                return
            metadata = json.loads(raw)
            if (not isinstance(metadata, dict) or type(metadata.get("line")) is not int
                    or metadata["line"] < 1 or metadata["line"] > 1_000_000):
                return
            if not isinstance(metadata.get("name"), str) or not re.fullmatch(r"[\w\u4e00-\u9fff]+", metadata["name"], re.UNICODE):
                return
            if len(metadata["name"]) > 128 or not isinstance(metadata.get("sourceName", ""), str):
                return
            if "startup" in metadata and type(metadata["startup"]) is not bool:
                return
            allowed_types = {"", "文本型", "数值型", "整数型", "长整数型", "小数型", "双精度小数型",
                             "逻辑型(布尔型)", "字节型", "日期时间型", "字节集", "对象型", "数组型", "自定义类型"}
            allowed_types |= {item['id'] for item in self.project.load_data()['types']}
            if metadata.get("returnType", "") not in allowed_types or type(metadata.get("public", False)) is not bool:
                return
            if not isinstance(metadata.get("remark", ""), str) or len(metadata.get("remark", "")) > 1024:
                return
            locals_value = metadata.get("locals", [])
            if not isinstance(locals_value, list) or len(locals_value) > 256:
                return
            normalized_locals = []
            local_names = set()
            for item in locals_value:
                if not isinstance(item, dict):
                    return
                local_name = str(item.get("name", "")).strip()
                if not local_name:
                    continue
                if not local_name.isidentifier() or keyword.iskeyword(local_name) or local_name.startswith('__pcide_') or local_name in local_names:
                    return
                local_names.add(local_name)
                local_type = str(item.get("type", "文本型"))
                if local_type not in allowed_types - {""}:
                    return
                initial = str(item.get('defaultValue',''))
                remark = str(item.get('remark',''))
                if len(initial)>512 or len(remark)>1024:
                    raise ValueError('局部变量初始值或备注超过长度限制')
                from pcide.core.data import TYPES, _initializer
                if local_type in TYPES:
                    _initializer({'type':local_type,'default':initial},'python')
                elif initial:
                    raise ValueError('自定义类型局部变量初始值必须为空')
                normalized_locals.append({"name": local_name, "type": local_type,
                                          "defaultValue": initial, "remark": remark})
            metadata["locals"] = normalized_locals
            source_name = metadata.get("sourceName") or metadata["name"]
            if not source_name.isidentifier() or not metadata["name"].isidentifier() or keyword.iskeyword(metadata['name']):
                return
            from pcide.core.routines import scan, find_metadata
            text = self.editor.documents.get(str(path), path.read_text(encoding="utf-8"))
            routine = next((value for value in scan(text, path.suffix) if value["sourceName"] == source_name), None)
            if routine is None:
                raise ValueError("子程序声明已改变，请重新选择")
            if set(routine["parameters"]) & local_names:
                raise ValueError("参数与局部变量重名")
            startup = source_name in self._startup_routine_names()
            metadata["startup"] = startup
            renamed = not startup and metadata["name"] != source_name
            if renamed:
                self._rename_routine(path, source_name, metadata["name"])
                source_name = metadata["name"]
            metadata["sourceName"] = source_name
            metadata['parameters'] = routine['parameters']
            metadata["line"] = routine["line"]
            index_path = self.project.ide_dir / "routines.json"
            index = self._routine_metadata_index()
            key = f"{path.relative_to(self.project.root).as_posix()}:{metadata['line']}"
            metadata["file"] = path.relative_to(self.project.root).as_posix()
            previous = find_metadata(index, metadata["file"], source_name, metadata["line"])
            metadata["id"] = previous.get("id") or uuid.uuid4().hex
            index[key] = metadata
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._update_routine_tree_label(metadata["line"], metadata["name"])
            self.editor.set_completion_items(self._completion_items())
            self.editor.routine_metadata_index = index
            if self.editor._fallback and self.editor.path == str(path):
                self.editor.routine_panel.value = copy.deepcopy(metadata)
                from pcide.ui.routine_ranges import scan_editor
                self.editor.routine_panel.routines = scan_editor(self.editor.documents[str(path)], path.suffix)
            elif renamed:
                self.editor.set_routine_metadata(index)
        except (OSError, ValueError, TypeError) as exc:
            self.log("子程序信息未保存：" + str(exc))

    def _rename_routine(self, path, old, new):
        from pcide.core.routines import rename_identifier
        changes = {}
        index = self._routine_metadata_index()
        for source in self.project.scripts():
            source = source.resolve()
            text = self.editor.documents.get(str(source), source.read_text(encoding="utf-8"))
            from pcide.core.routines import scan
            if source != path and any(value["sourceName"] == old for value in scan(text, source.suffix)):
                raise ValueError("其他文件存在同名子程序；请先明确调用范围")
            updated = rename_identifier(text, source.suffix, old, new)
            if updated != text:
                changes[str(source)] = updated
        forms = {}
        for form_path in self.project.window_paths():
            form = copy.deepcopy(self.designer.form) if form_path.resolve() == self.current_form_path.resolve() else self.project.load_window(form_path)
            changed = False
            for owner in [form["form"], *form["controls"]]:
                for event, handler in owner.get("events", {}).items():
                    if handler == old:
                        owner["events"][event] = new
                        changed = True
            if changed:
                forms[form_path] = validate_form(form)
        for source, text in changes.items():
            if source not in self.editor.saved:
                self.editor.saved[source] = Path(source).read_text(encoding="utf-8")
            self.editor.documents[source] = text
            if self.editor.path == source:
                self.editor.set_value(text)
        for form_path, form in forms.items():
            atomic_write_json(form_path, form)
            if form_path.resolve() == self.current_form_path.resolve():
                self.designer.form = form
        for value in index.values():
            if value.get("file") == path.relative_to(self.project.root).as_posix() and value.get("sourceName") == old:
                value.update(sourceName=new, name=new)
        atomic_write_json(self.project.ide_dir / "routines.json", index)
        self.mark_dirty()

    def _update_routine_tree_label(self, line, name):
        """Reflect an edited routine title without changing its source handler."""
        if type(line) is not int or not isinstance(name, str) or not name.strip():
            return
        for index in range(self.routine_list.topLevelItemCount() if hasattr(self, "routine_list") else 0):
            item = self.routine_list.topLevelItem(index)
            item_line = item.data(0, Qt.ItemDataRole.UserRole)
            if (item_line is not None and str(item_line) == str(line)) or item.text(1) == f"第 {line} 行":
                item.setText(0, name)
        section = None
        if hasattr(self, "project_tree"):
            for index in range(self.project_tree.topLevelItemCount()):
                candidate = self.project_tree.topLevelItem(index)
                if candidate.data(0, Qt.ItemDataRole.UserRole + 2) == "子程序":
                    section = candidate
                    break
        if section is not None:
            for index in range(section.childCount()):
                item = section.child(index)
                item_line = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if (item_line is not None and str(item_line) == str(line)) or item.text(0).endswith(f"（第 {line} 行）"):
                    item.setText(0, f"子程序 {name}（第 {line} 行）")

    def _refresh_routines(self):
        if not hasattr(self, "routine_list"):
            return
        self.routine_list.clear()
        from pcide.core.development import SCRIPT_LANGUAGES
        if self.project.manifest['language'] not in SCRIPT_LANGUAGES:
            return
        try:
            text = self.editor.documents.get(str(self.project.entry_path.resolve()), self.project.entry_path.read_text(encoding="utf-8"))
        except OSError:
            text = ""
        section = self._replace_program_section("子程序")
        from pcide.ui.routine_ranges import scan_editor
        from pcide.core.routines import find_metadata
        startup_names = set(self._startup_routine_names())
        metadata_index = self._routine_metadata_index()
        for routine in scan_editor(text, self.project.entry_path.suffix):
            line = routine['line']
            source_name = routine['sourceName']
            # The startup handler remains the real source-level event name,
            # but its visible Yi-style title is user-editable metadata.  Do
            # not turn the marker into a locked function name or rename the
            # handler that the form's load event invokes.
            stored = find_metadata(metadata_index, self.project.entry_path.relative_to(self.project.root).as_posix(), source_name, line)
            name = (str(stored.get("name") or "_启动程序")
                    if source_name in startup_names else source_name)
            item = QTreeWidgetItem(self.routine_list, [name, f"第 {line} 行"])
            item.setData(0, Qt.ItemDataRole.UserRole, line)
            visible = QTreeWidgetItem(section, ["子程序 " + name + f"（第 {line} 行）"])
            visible.setData(0, Qt.ItemDataRole.UserRole, str(self.project.entry_path))
            visible.setData(0, Qt.ItemDataRole.UserRole + 1, line)

    def _open_routine(self, item, _column=0):
        line = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(line, int):
            line = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(line, int):
            file = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(file, str):
                self.editor.load(file)
            else:
                self.editor.load(self.project.entry_path)
            self.show_page('code')
            self.editor.goto_routine(line)

    def open_libraries(self, page=0):
        from pcide.ui.library_dialog import LibraryDialog
        try:
            dialog = LibraryDialog(self.project, self, page)
            dialog.changed.connect(self._libraries_changed)
            dialog.exec()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '支持库配置', str(exc))

    def _libraries_changed(self):
        self.data_panel.load(self.project.load_data())
        self._refresh_support_library()
        self._refresh_data_summary()
        self.editor.set_completion_items(self._completion_items())
        self._refresh_routines()

    def _filter_support_library(self, text=''):
        self._filter_catalog_tree(self.support_library, text)

    def _filter_catalog_tree(self, tree, text=''):
        query = text.casefold().strip()
        def visit(item, inherited=False):
            matched = inherited or query in (item.text(0)+' '+item.text(1)).casefold()
            child_matches = [visit(item.child(i), matched) for i in range(item.childCount())]
            visible = matched or any(child_matches)
            item.setHidden(not visible)
            if query and visible and item.childCount():
                item.setExpanded(True)
            return visible
        for index in range(tree.topLevelItemCount()):
            visit(tree.topLevelItem(index))

    def _show_support_item_details(self, item, _previous=None):
        if not hasattr(self, 'support_details'):
            return
        if item is None:
            self.support_details.clear()
            return
        model = item.data(0, Qt.ItemDataRole.UserRole+5) or {}
        text = model.get('label', item.text(0)) + '\n\n' + model.get('description', item.text(1))
        if model.get('code'):
            text += '\n\n调用示例：\n' + model['code']
        self.support_details.setPlainText(text)
        self._set_hint(model.get("label", item.text(0)), text)

    def _refresh_code_snippets(self):
        if not hasattr(self, 'snippet_tree'):
            return
        from pcide.core.libraries import DEVELOPMENT_COMMANDS, UNITY_COMMANDS
        language = self.project.manifest['language']
        unity = self.project.manifest['development']['template'].startswith('unity-')
        commands = UNITY_COMMANDS if unity else DEVELOPMENT_COMMANDS.get(language, [])
        self.snippet_tree.clear()
        groups = {}
        for label, category, code, description in commands:
            if category not in groups:
                groups[category] = QTreeWidgetItem(self.snippet_tree, [category, 'Unity' if unity else language])
                groups[category].setExpanded(True)
            item = QTreeWidgetItem(groups[category], [label, description])
            item.setToolTip(0, description+'\n'+code)
            item.setData(0, Qt.ItemDataRole.UserRole, code)
            item.setData(0, Qt.ItemDataRole.UserRole+5, {'label': label, 'description': description, 'code': code})
        index = self.left_catalog.indexOf(self.snippet_host)
        if index >= 0:
            self.left_catalog.setTabVisible(index, bool(commands))
        self._filter_catalog_tree(self.snippet_tree, self.snippet_search.text())

    def _populate_control_library_type(self, parent, label, entry):
        from pcide.core.control_catalog import CONTROL_LABELS, CHOICES, control_defaults
        from pcide.ui.properties import PROPERTY_LABELS, EVENT_LABELS, control_events
        from pcide.core.project import DEFAULT_FORM
        kind = next((key for key, value in CONTROL_LABELS.items() if value == label), None)
        if label == '窗口':
            values = {key: value for key, value in DEFAULT_FORM['form'].items() if key not in {'events', 'window'}}
            values.update(DEFAULT_FORM['form']['window'])
            event_ids = ('load', 'resize', 'close')
        elif kind:
            values = control_defaults(kind)
            event_ids = control_events(kind)
        else:
            return
        props = entry(parent, '属性', '在属性页编辑；默认值与表单合同一致')
        if kind == "MenuBar":
            entry(props, "菜单层级", "数据名称：menu；在设计 → 窗口菜单编辑器中编辑子菜单、分隔线、快捷键、可见/启用/勾选状态和处理子程序。旧 items 顶层名称保留兼容。")
        for key, value in values.items():
            type_name = '逻辑型' if isinstance(value, bool) else '整数型' if isinstance(value, int) else '数组型' if isinstance(value, list) else '文本型'
            description = key+' · '+type_name+'；默认值：'+json.dumps(value, ensure_ascii=False)
            if key in CHOICES:
                description += '\n可选值：'+ '、'.join(name+' ('+str(code)+')' for name, code in CHOICES[key])
            entry(props, PROPERTY_LABELS.get(key, key), description)
        events = entry(parent, '事件', '在属性 → 事件中绑定子程序；双击设计控件进入对应事件代码')
        for event_id in event_ids:
            description = '事件代码：'+event_id+'；事件参数含控件/窗口 id 与 event'
            if kind == "MenuBar" and event_id == "click":
                description = "菜单项未设置独立处理子程序时使用此处理器；参数含菜单栏 id、menu_id、text、checked，event 为 menu。"
            entry(events, EVENT_LABELS.get(event_id, event_id), description)
        methods = entry(parent, '方法', '通过窗口支持库代理调用')
        if label == '窗口':
            entry(methods, '打开', '窗口路径为项目内 .form.json 文件', '__import__("pcide.runtime_api", fromlist=["ui"]).ui.open("ui/main.form.json")')
            entry(methods, '关闭', '关闭指定运行窗口', '__import__("pcide.runtime_api", fromlist=["ui"]).ui.close("ui/main.form.json")')
        else:
            entry(methods, '设置属性', '将控件ID替换为项目中的实际 ID；UI 更新在窗口线程处理', '__import__("pcide.runtime_api", fromlist=["ui"]).ui.set("控件ID", enabled=True)')
            if kind == 'Timer':
                entry(parent, '当前能力', '当前仅有时钟设计属性与显示组件；定时事件尚未实现')
            elif kind == 'WebView':
                entry(parent, '当前能力', '当前为网页地址/文本显示组件，尚未实现网页加载与浏览器交互')

    def _refresh_support_library(self):
        if not hasattr(self, 'support_library'):
            return
        from pcide.core.libraries import SYSTEM_LIBRARIES, CORE_CATEGORY_ORDER, load_libraries, plugin_catalog, calling_example
        from pcide.core.modules import load_modules
        language = self.project.manifest['language']
        self._refresh_code_snippets()
        self.support_library.clear()
        def entry(parent, label, description='', code=''):
            item = QTreeWidgetItem(parent, [label, description])
            item.setToolTip(0, description + ('\n'+code if code else ''))
            item.setData(0,Qt.ItemDataRole.UserRole+5,{'label':label,'description':description,'code':code})
            if code:
                item.setData(0, Qt.ItemDataRole.UserRole, code)
            return item
        try:
            model = load_libraries(self.project)
            if language not in {'python','zhxb','javascript','typescript'}:
                entry(self.support_library, '当前工程：'+language, '当前语言的 API 示例在“代码片段”页。中文源码项目显示 PCIDE 核心和窗口支持库。')
            for library in SYSTEM_LIBRARIES:
                if library['id'] not in model['system'] or language not in library.get('languages', {'python','zhxb','javascript','typescript'}):
                    continue
                parent_description = '按易语言支持库的命令类别、库定义数据类型和库定义常量展示' if language == 'zhxb' else '当前语言的系统命令'
                parent = entry(self.support_library, library['name'], parent_description)
                parent.setExpanded(True)
                categories = {}
                ordered_categories = [name for name in CORE_CATEGORY_ORDER if any(command['category'] == name for command in library['commands'])]
                ordered_categories += [command['category'] for command in library['commands'] if command['category'] not in ordered_categories]
                for name in dict.fromkeys(ordered_categories):
                    categories[name] = entry(parent, name)
                for command in library['commands']:
                    category = categories[command['category']]
                    code = command['code'].get(language)
                    entry(category, command['label'], command['description'] if code else '当前语言未开放此命令', code)
                if library['types']:
                    types = entry(parent, '库定义数据类型', '窗口支持库类型在控件箱添加；核心数据类型在变量声明表中选择')
                    for label in library['types']:
                        type_item = entry(types, label, '窗口组件类型' if library['id'] == 'system.window' else '程序数据类型')
                        if library['id'] == 'system.window':
                            self._populate_control_library_type(type_item, label, entry)
                if library['constants']:
                    constants = entry(parent, '库定义常量')
                    for label, code in library['constants']:
                        entry(constants, label, '插入常量值', code)
            external = entry(self.support_library, '外部支持库', '加入 DLL、DEX 或封装包')
            modules = entry(self.support_library, '引用模块', '源码公开接口与易模块文件')
            data = self.project.load_data()
            for api in data['apis']:
                code = api['id']+'('+', '.join(p['id'] for p in api['parameters'])+')' if language in {'python','zhxb'} else ''
                entry(external, api['label'], 'DLL · '+api['entry']+' · '+api['calling_convention'] if code else 'DLL 调用需要 Python/中文源码', code)
            for module in load_modules(self.project)['modules']:
                parent = entry(modules, module['id'], '源码模块 '+module['version'])
                for name in module['exports']:
                    from pcide.core.libraries import module_documentation
                    description,code=module_documentation(self.project,module,name)
                    entry(parent, name, description if language in {'python','zhxb'} else '需 Python/中文运行时', code if language in {'python','zhxb'} else '')
            for record in model['imports']:
                if record['kind'] in {'py','zhxb','dll'}:
                    continue
                parent = modules if record['kind'] in {'js','ts','ec'} else external
                entry(parent, record['id'], record['kind'].upper()+' · '+record['status'], calling_example(record, language))
            for manifest in plugin_catalog(self.project):
                missing = set(manifest.permissions)-set(self.project.manifest.get('permissions',[]))
                parent = entry(external, manifest.name, manifest.kind+' '+manifest.version+(' · 待授权 '+','.join(sorted(missing)) if missing else ' · 独立宿主'))
                for capability in manifest.capabilities:
                    record = {'id': manifest.id, 'kind': manifest.kind, 'capabilities': [capability]}
                    entry(parent, capability, '支持库公开能力' if language in {'python','zhxb'} else '需 Python/中文运行时', calling_example(record, language))
            external.setExpanded(True)
            modules.setExpanded(True)
        except (ValueError, OSError, RuntimeError) as exc:
            entry(self.support_library, '支持库配置错误', str(exc))
        self._filter_support_library(self.support_search.text() if hasattr(self, 'support_search') else '')

    def _refresh_data_summary(self):
        if not hasattr(self, "data_summary"):
            return
        self.data_summary.clear()
        from pcide.core.development import SCRIPT_LANGUAGES
        if self.project.manifest['language'] not in SCRIPT_LANGUAGES:
            return
        try:
            data = self.project.load_data()
        except (OSError, ValueError, ProjectError):
            data = {"variables": [], "constants": [], "apis": []}
        section = self._replace_program_section("变量 / 常量")
        groups = [('全局变量', 'variables', 'global'), ('窗口变量', 'variables', 'window'),
                  ('程序集变量', 'variables', 'module'), ('局部变量', 'variables', 'local'),
                  ('常量', 'constants', 'constants'), ('自定义数据类型', 'types', 'types'), ('DLL 命令', 'apis', 'apis')]
        for group, key, selection in groups:
            parent = QTreeWidgetItem(section, [group, ''])
            parent.setData(0, Qt.ItemDataRole.UserRole + 3, selection)
            parent.setExpanded(True)
            for value in data.get(key, []):
                if key == 'variables' and value.get('scope') != selection:
                    continue
                label = value.get('label') or value.get('id') or ''
                owner = value.get('owner', '')
                item = QTreeWidgetItem(parent, [label + (' ('+owner+')' if owner else ''), str(value.get('type') or value.get('return_type') or '')])
                item.setData(0, Qt.ItemDataRole.UserRole + 3, selection)
                item.setData(0, Qt.ItemDataRole.UserRole + 4, value.get('id', label))

    def _save_program_data(self, data):
        self.project.save_data(data)
        self.editor.custom_types = [item['id'] for item in data.get('types', [])]
        self._refresh_data_summary()
        self._refresh_support_library()
        self.editor.set_completion_items(self._completion_items())

    def _insert_library_item(self, item, _column=0):
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value and hasattr(self.editor, "insert_text"):
            self.editor.insert_text(str(value))
            self.tabs.setTabVisible(self.tabs.indexOf(self.editor), True)
            self.show_page('code')
            self.workspace_tabs.setCurrentWidget(self.tabs)

    def _support_context_menu(self,position):
        self._catalog_context_menu(self.support_library, position)

    def _snippet_context_menu(self, position):
        self._catalog_context_menu(self.snippet_tree, position)

    def _catalog_context_menu(self, tree, position):
        item=tree.itemAt(position)
        if not item:return
        tree.setCurrentItem(item)
        menu=QMenu(self)
        help_action=menu.addAction('查看说明与调用示例')
        insert=menu.addAction('插入代码编辑器')
        copy_action=menu.addAction('复制调用示例')
        code=item.data(0,Qt.ItemDataRole.UserRole)
        insert.setEnabled(bool(code));copy_action.setEnabled(bool(code))
        selected=menu.exec(tree.viewport().mapToGlobal(position))
        if selected==insert:self._insert_library_item(item)
        elif selected==copy_action:QApplication.clipboard().setText(str(code))
        elif selected==help_action:self.show_library_help(item)

    def show_library_help(self,item):
        model=item.data(0,Qt.ItemDataRole.UserRole+5) or {'label':item.text(0),'description':item.text(1),'code':''}
        dialog=QDialog(self);dialog.setWindowTitle(model['label']+' · 说明与例子');dialog.resize(680,430)
        layout=QVBoxLayout(dialog)
        text=QPlainTextEdit();text.setReadOnly(True)
        text.setPlainText(model['label']+'\n\n'+model['description']+'\n\n调用示例：\n'+(model['code'] or '此分类无可插入调用；展开查看具体接口。')+'\n\n双击、右键“插入代码编辑器”或拖动到代码正文插入。线程/UI例子可在帮助 → 示例中心搜索。')
        layout.addWidget(text)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        action=buttons.addButton('插入编辑器',QDialogButtonBox.ButtonRole.ActionRole);action.setEnabled(bool(model['code']))
        action.clicked.connect(lambda:self._insert_library_item(item));buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        dialog.exec()

    def _add_toolbox_item(self, item, _column=0):
        kind = item.data(0, Qt.ItemDataRole.UserRole)
        if kind:
            self.designer.add(kind)

    def trigger_completion(self):
        if self.editor.loaded:
            if self.editor._fallback:
                self.editor.trigger_completion()
            else:
                self.editor.page.runJavaScript("pcide.triggerSuggest()")

    def toggle_editor_fold(self):
        if self.editor.loaded:
            if self.editor._fallback:
                self.editor.routine_panel.collapse()
            else:
                self.editor.page.runJavaScript("pcide.toggleFold()")

    def format_editor(self):
        if self.editor.loaded:
            self.editor.format_document()

    def editor_undo(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,(QLineEdit,QPlainTextEdit)):
            focus.undo()
        elif self.workspace_tabs.currentWidget() is self.designer:
            self.designer.undo()
        else:
            self.editor.undo()

    def editor_redo(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,(QLineEdit,QPlainTextEdit)):
            focus.redo()
        elif self.workspace_tabs.currentWidget() is self.designer:
            self.designer.redo()
        else:
            self.editor.redo()

    def switch_workspace(self):
        code=self.workspace_tabs.currentWidget() is self.designer
        self.workspace_tabs.setCurrentWidget(self.tabs if code else self.designer)
        if code:
            self.tabs.setTabVisible(self.tabs.indexOf(self.editor),True)
            self.show_page('code')
            self.editor.view.setFocus()
        else:
            self.designer.setFocus()

    def show_shortcuts(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('快捷键与操作说明')
        dialog.resize(650,570)
        layout=QVBoxLayout(dialog)
        text=QPlainTextEdit()
        text.setReadOnly(True)
        shortcuts={action.shortcut().toString():action.text() for action in self.findChildren(QAction) if not action.shortcut().isEmpty()}
        text.setPlainText('\n'.join(key+'  '+label for key,label in shortcuts.items())+'\n\nCtrl+D / Delete：设计画布中复制/删除控件。\n参数：调用方传入；可省略参数使用声明的默认值。\n局部变量：内部初始化，普通局部每次调用重新初始化；静态局部在 Python/中文运行时保留值。\n编辑参数后检查正文引用和所有调用处。\nTab / Shift+Tab：表格下一项/上一项；双击或 F2 编辑单元格。')
        layout.addWidget(text)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def edit_routine_parameters(self,uri,line):
        path=Path(uri).resolve()
        if not path.is_relative_to(self.project.root.resolve()):
            return
        def opened():
            from pcide.ui.parameter_dialog import ParameterDialog
            from pcide.ui.routine_ranges import scan_editor
            source=self.editor.documents[str(path)]
            routine=next((r for r in scan_editor(source,path.suffix) if r['line']==line),None)
            if not routine:
                return
            try:
                from pcide.core.routines import find_metadata
                file=path.relative_to(self.project.root).as_posix()
                index=self._routine_metadata_index()
                stored=find_metadata(index,file,routine['sourceName'],line)
                local_names=[p['name'] for p in stored.get('locals',[])]+[p['id'] for p in self.project.load_data()['variables'] if p['scope']=='local' and p['owner'] in {routine['sourceName'],file+':'+routine['sourceName']}]
                dialog=ParameterDialog(source,path.suffix,routine['sourceName'],self,notes=stored.get('parameterNotes'),local_names=local_names)
                if dialog.exec()==QDialog.DialogCode.Accepted:
                    self.editor.set_value(dialog.result_source)
                    self.editor.documents[str(path)]=dialog.result_source
                    path.write_text(dialog.result_source,encoding='utf-8')
                    self.editor.saved[str(path)]=dialog.result_source
                    key=file+':'+str(line)
                    index[key]={**stored,'id':stored.get('id') or uuid.uuid4().hex,'name':stored.get('name') or ('_启动程序' if routine['sourceName'] in self._startup_routine_names() else routine['sourceName']),
                                'sourceName':routine['sourceName'],'file':file,'line':line,'parameterNotes':dialog.notes}
                    atomic_write_json(self.project.ide_dir/'routines.json',index)
                    self.editor.set_routine_metadata(self._routine_metadata_index())
                    self._refresh_routines()
                    self.editor.set_completion_items(self._completion_items())
            except (ValueError,OSError,SyntaxError) as exc:
                self.log('参数未保存：'+str(exc))
        self.editor.capture(opened)

    def replace_in_editor(self):
        if not self.editor.path:
            return
        search, ok = QInputDialog.getText(self, "替换文本", "查找内容")
        if not ok or not search:
            return
        replacement, ok = QInputDialog.getText(self, "替换文本", "替换为")
        if not ok:
            return
        count = self.editor.replace(search, replacement, replace_all=True)
        self.statusBar().showMessage(f"已替换 {count} 处")

    def save_editor_as(self):
        if not self.editor.path:
            return
        target, _ = QFileDialog.getSaveFileName(self, "保存当前文件为", str(Path(self.editor.path)), "所有文件 (*)")
        if not target:
            return
        target = Path(target).resolve()
        try:
            if not target.is_relative_to(self.project.root.resolve()) or target.is_dir():
                raise ProjectError("只能保存到当前项目目录")
            if target == self.project.ide_dir / "project.json":
                raise ProjectError("不能覆盖项目配置")
            source_path = self.editor.path
            def save():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(self.editor.documents[source_path], encoding="utf-8", newline="\n")
                self._refresh_after_file_change(file_path=target)
            self.after_save(save)
        except (OSError, ProjectError) as exc:
            self.log(f"无法另存文件：{exc}")

    def goto_editor_line(self):
        line, ok = QInputDialog.getInt(self, "跳转到行", "行号", 1, 1, 1000000)
        if ok:
            self.editor.goto(line)

    def toggle_chinese_editor(self):
        if self.editor.loaded:
            self.editor.toggle_chinese_view()
            self._sync_editor_view_action(self.editor.path or '')

    def _sync_editor_view_action(self, path):
        if not hasattr(self, 'chinese_view_action'):
            return
        supported = bool(path) and self.editor._language(path) in {'python','javascript','typescript','zhxb'}
        self.chinese_view_action.setEnabled(supported)
        self.chinese_view_action.setChecked(supported and self.editor.chinese_view)
        for action in self._routine_actions:
            action.setEnabled(supported and not self._project_closed)

    def _editor_document_loaded(self, path):
        self._sync_editor_view_action(path)
        self.editor.set_breakpoints(self.breakpoints.get(path, set()))

    def show_environment(self):
        if self._project_closed:
            return
        from pcide.ui.configuration_dialogs import EnvironmentDialog
        dialog = EnvironmentDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.manifest['execution'] = dialog.execution()
            self.after_save(lambda: self.statusBar().showMessage('运行限制已保存，下一次脚本启动生效'))

    def show_platform_capabilities(self):
        """Edit the versioned, project-local capability switches."""
        if self._project_closed:
            return
        from pcide.ui.configuration_dialogs import PlatformCapabilitiesDialog
        dialog = PlatformCapabilitiesDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.manifest['platform'] = dialog.result_platform
            self._refresh_support_library()
            self.after_save(lambda: self.statusBar().showMessage("平台能力已保存"))

    def open_ai_assistant(self):
        if self._project_closed:self.log('请先新建或打开工程。');return
        self.after_save(self._open_ai_assistant_saved)

    def _open_ai_assistant_saved(self):
        from pcide.ui.agent_dialog import AgentDialog
        dialog = AgentDialog(self.project, self)
        dialog.exec()
        self.project = Project.open(self.project.root)
        self._load_project()

    def connect_unity_project(self):
        self.connect_engine_project('unity')

    def connect_engine_project(self, engine):
        if self.busy:return
        folder = QFileDialog.getExistingDirectory(self, f'选择已有 {engine.title()} 工程', str(self.paths.projects))
        if not folder:
            return
        def connect():
            from pcide.core.development import template_for
            from pcide.core.engines import bind_engine_project, engine_root
            try:
                if template_for(self.project).id.startswith(engine+'-') and not self._project_closed:
                    candidate=Project(self.project.root,copy.deepcopy(self.project.manifest))
                    candidate.manifest['development']['engine_root']=str(Path(folder).resolve())
                    engine_root(candidate)
                    candidate.save_manifest();self._switch(candidate)
                else:
                    stem=self.paths.project(engine.title()+'_'+Path(folder).name).name
                    name=stem;number=2
                    while self.paths.project(name).exists():
                        name=stem+'_'+str(number);number+=1
                    project=bind_engine_project(self.paths,name,engine+'-3d',folder,
                        self.project.manifest['development']['tools'])
                    self._switch(project)
                self.log(f'{engine.title()} 已绑定：{folder}。F5打开/运行；Ctrl+B构建Windows游戏；环境菜单选择已有引擎程序。')
            except (ValueError,OSError) as exc:
                QMessageBox.warning(self,'引擎接入失败',str(exc))
        self.after_save(connect)

    def open_database_designer(self):
        if self._project_closed:
            return
        self.after_save(self._open_database_designer_saved)

    def _open_database_designer_saved(self):
        from pcide.ui.platform_dialogs import DatabaseDesignerDialog
        dialog = DatabaseDesignerDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_project()
            self.statusBar().showMessage("数据库定义已保存")

    def open_api_center(self):
        if self._project_closed:
            return
        self.after_save(self._open_api_center_saved)

    def _open_api_center_saved(self):
        from pcide.ui.platform_dialogs import ApiCenterDialog
        dialog = ApiCenterDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_project()
            self.statusBar().showMessage("API 接口定义已保存")

    def _populate_project_tree(self, parent, directory):
        if not directory.is_dir():
            return
        for path in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.casefold())):
            if path.name in {"__pycache__", ".git", 'Library','Temp','Logs','obj','bin','node_modules','.godot','cache','build'} or path.suffix in {".pdb", ".pyc"} or path.is_symlink():
                continue
            item = QTreeWidgetItem(parent, [path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            if path.is_dir():
                self._populate_project_tree(item, path)
            elif path.suffix in {'.py', '.zhxb', '.js', '.ts'} and path.resolve() != self.project.entry_path.resolve() and path.stat().st_size <= 5 * 1024 * 1024:
                from pcide.ui.routine_ranges import scan_editor
                try:
                    text = self.editor.documents.get(str(path.resolve()), path.read_text(encoding='utf-8'))
                    for routine in scan_editor(text, path.suffix):
                        child = QTreeWidgetItem(item, ['子程序 ' + routine['sourceName'] + f"（第 {routine['line']} 行）"])
                        child.setData(0, Qt.ItemDataRole.UserRole, str(path))
                        child.setData(0, Qt.ItemDataRole.UserRole + 1, routine['line'])
                except (OSError, ValueError):
                    pass

    def _refresh_window_menu(self):
        if not hasattr(self, "window_menu"):
            return
        for action in self.window_actions:
            self.window_menu.removeAction(action)
        self.window_actions.clear()
        for path in self.project.window_paths():
            action = self._action(path.relative_to(self.project.root / "ui").as_posix(), lambda _, p=path: self.switch_window(p))
            self.window_menu.addAction(action)
            self.window_actions.append(action)

    def switch_window(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = self.project.root / "ui" / path
        try:
            form = self.project.load_window(path)
            self.current_form_path = path.resolve()
            self.designer.load(form)
            self.editor.set_startup_routines(self._startup_routine_names())
            self._refresh_routines()
            self._show_designer_view()
            self.statusBar().showMessage(f"已切换窗口：{form['form']['title']}")
            if self.runtime_manager and self.runtime_form:
                self.runtime_form.close()
                self.runtime_form = self.runtime_manager.open(str(self.current_form_path))
        except (ProjectError, OSError, ValueError) as exc:
            self.log(str(exc))

    def _startup_routine_names(self):
        """Only the project's primary startup window owns the software title."""
        primary = self.designer.form if self.current_form_path.resolve() == self.project.form_path.resolve() else self.project.load_form()
        events = primary.get("form", {}).get("events", {})
        names = []
        load_handler = events.get("load")
        if isinstance(load_handler, str) and load_handler.strip():
            names.append(load_handler.strip())
        if self.project.manifest.get("language") == "zhxb":
            names.append("主程序")
        return names

    def _show_generated_data(self, language, source):
        self.output.setPlainText(source)
        self.tabs.setCurrentWidget(self.output)
        self.workspace_tabs.setCurrentWidget(self.tabs)
        self.statusBar().showMessage(f"已生成 {language} 数据代码")

    def _show_designer_view(self):
        """Keep the source editor out of the active pane while editing a form."""
        self.tabs.setCurrentWidget(self.output)
        if hasattr(self, "workspace_tabs"):
            self.workspace_tabs.setCurrentWidget(self.designer)

    def _tree_path(self, item):
        raw = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return Path(raw).resolve() if raw else self.project.root

    def _refresh_after_file_change(self, form_path=None, file_path=None):
        form_path = Path(form_path).resolve() if form_path else None
        file_path = Path(file_path).resolve() if file_path else None
        self.current_form_path = form_path if form_path and form_path.is_file() else self.project.form_path
        self._load_project()
        if file_path and file_path.is_file():
            try:
                self.editor.load(file_path)
                self.editor.set_breakpoints(self.breakpoints.get(str(file_path), set()))
                editor_index = self.tabs.indexOf(self.editor)
                if editor_index >= 0:
                    self.tabs.setTabVisible(editor_index, True)
                self.show_page('code')
                self.workspace_tabs.setCurrentWidget(self.tabs)
            except (OSError, ValueError) as exc:
                self.log(str(exc))

    def _reject_if_running(self):
        if self.runner.active or self.busy:
            QMessageBox.warning(self, "无法修改项目", "请先停止运行或等待当前任务结束")
            return True
        return False

    def _create_project_file(self, directory):
        name, ok = QInputDialog.getText(self, "新建文件", "文件名")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not valid_file_name(name):
            QMessageBox.warning(self, "无法创建文件", "文件名包含非法字符")
            return
        target = directory / name
        if target.exists():
            QMessageBox.warning(self, "无法创建文件", "同名文件或目录已存在")
            return
        def create():
            try:
                target.write_text("", encoding="utf-8")
                self._refresh_after_file_change(file_path=target)
            except OSError as exc:
                self.log(f"无法创建文件：{exc}")
        self.after_save(create)

    def _create_project_directory(self, directory):
        name, ok = QInputDialog.getText(self, "新建目录", "目录名")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not valid_file_name(name):
            QMessageBox.warning(self, "无法创建目录", "目录名包含非法字符")
            return
        target = directory / name
        if target.exists():
            QMessageBox.warning(self, "无法创建目录", "同名文件或目录已存在")
            return
        def create():
            try:
                target.mkdir(parents=False)
                self._refresh_after_file_change()
            except OSError as exc:
                self.log(f"无法创建目录：{exc}")
        self.after_save(create)

    def _import_project_file(self, directory):
        directory = Path(directory).resolve()
        if not directory.is_relative_to(self.project.root.resolve()):
            self.log('导入目录必须位于当前工程内')
            return
        source, _ = QFileDialog.getOpenFileName(self, "导入文件或 DLL", "", "所有文件 (*)")
        if not source:
            return
        source = Path(source).resolve()
        target = directory / source.name
        if target.exists():
            QMessageBox.warning(self, "无法导入文件", "目标目录中已存在同名文件")
            return
        def import_file():
            try:
                if source == target:
                    raise ProjectError("不能把文件导入到自身")
                shutil.copy2(source, target)
                if directory.is_relative_to((self.project.root / 'resources').resolve()):
                    self._refresh_after_file_change()
                    self.show_page('resources')
                else:
                    self._refresh_after_file_change(file_path=target)
            except (OSError, ProjectError) as exc:
                self.log(f"无法导入文件：{exc}")
        self.after_save(import_file)

    def _rename_project_path(self, source):
        if self._reject_if_running():
            return
        reason = self.project.protected_path_reason(source)
        if reason:
            QMessageBox.warning(self, "无法重命名", reason)
            return
        default = source.name
        name, ok = QInputDialog.getText(self, "重命名", "新名称", text=default)
        if not ok or not name.strip():
            return
        name = name.strip()
        if source.suffixes[-2:] == [".form", ".json"] and not name.lower().endswith(".form.json"):
            name += ".form.json"
        if not valid_file_name(name):
            QMessageBox.warning(self, "无法重命名", "名称包含非法字符")
            return
        target = source.parent / name
        if target.exists():
            QMessageBox.warning(self, "无法重命名", "目标名称已存在")
            return
        current_form = self.current_form_path.resolve()
        current_file = Path(self.editor.path).resolve() if self.editor.path else None
        source_was_dir = source.is_dir()
        def rename():
            try:
                result = self.project.rename_path(source, name)
                if source.suffixes[-2:] == [".form", ".json"]:
                    try:
                        form = self.project.load_window(result)
                        old_id = form["form"].get("id")
                        old_stem = source.name[:-10]
                        new_stem = result.name[:-10]
                        if not old_id or old_id == old_stem:
                            form["form"]["id"] = new_stem
                            self.project.save_window(result, form)
                    except (ProjectError, OSError, ValueError) as exc:
                        self.log(f"窗口标识同步失败：{exc}")
                preferred_form = result if current_form == source or source_was_dir and current_form.is_relative_to(source) else current_form
                preferred_file = result if current_file == source else (result / current_file.relative_to(source) if source_was_dir and current_file and current_file.is_relative_to(source) else current_file)
                self._refresh_after_file_change(preferred_form, preferred_file)
            except (OSError, ProjectError) as exc:
                self.log(f"无法重命名：{exc}")
        self.after_save(rename)

    def _delete_project_path(self, target):
        if self._reject_if_running():
            return
        reason = self.project.protected_path_reason(target)
        if reason:
            QMessageBox.warning(self, "无法删除", reason)
            return
        if target.is_dir():
            answer = QMessageBox.question(self, "删除目录", f"确定删除目录及其中全部内容吗？\n{target.name}",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        else:
            answer = QMessageBox.question(self, "删除文件", f"确定删除文件吗？\n{target.name}",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        current_form = self.current_form_path.resolve()
        current_file = Path(self.editor.path).resolve() if self.editor.path else None
        target_was_dir = target.is_dir()
        def delete():
            try:
                self.project.delete_path(target)
                preferred_form = None if current_form == target or target_was_dir and current_form.is_relative_to(target) else current_form
                preferred_file = None if current_file == target or target_was_dir and current_file and current_file.is_relative_to(target) else current_file
                self._refresh_after_file_change(preferred_form, preferred_file)
            except (OSError, ProjectError) as exc:
                self.log(f"无法删除：{exc}")
        self.after_save(delete)

    def project_context_menu(self, position):
        item = self.project_tree.itemAt(position)
        if not item:
            return
        group = item.data(0, Qt.ItemDataRole.UserRole + 3)
        if group:
            self._open_program_item(item)
            if group == 'modules':
                return
            menu = QMenu(self)
            selected_kind = 'constant' if group == 'constants' else 'type' if group == 'types' else 'api' if group == 'apis' else 'variable'
            add = menu.addAction('添加当前类别')
            edit = menu.addAction('编辑当前行')
            duplicate = menu.addAction('复制当前行')
            delete = menu.addAction('删除当前行')
            members = menu.addAction('编辑成员 / 参数')
            chosen = menu.exec(self.project_tree.viewport().mapToGlobal(position))
            if chosen == add:
                self.data_panel._add(selected_kind)
            elif chosen == edit:
                row = self.data_panel.table.currentRow()
                if row >= 0:
                    self.data_panel.table.editItem(self.data_panel.table.item(row,0))
            elif chosen == duplicate:
                self.data_panel._duplicate()
            elif chosen == delete:
                self.data_panel._delete()
            elif chosen == members:
                self.data_panel._edit_members()
            return
        target = self._tree_path(item)
        container = target if target.is_dir() else target.parent
        menu = QMenu(self)
        open_action = menu.addAction("打开") if target.is_file() else None
        if open_action:
            menu.addSeparator()
        add_file = menu.addAction("新建文件")
        add_dir = menu.addAction("新建目录")
        add_window = menu.addAction("新建窗口") if container == self.project.root / "ui" else None
        import_file = menu.addAction("导入文件或 DLL")
        menu.addSeparator()
        rename = menu.addAction("重命名")
        delete = menu.addAction("删除")
        protected = self.project.protected_path_reason(target)
        rename.setEnabled(protected is None)
        delete.setEnabled(protected is None)
        chosen = menu.exec(self.project_tree.viewport().mapToGlobal(position))
        if chosen == open_action:
            self.open_file(item)
        elif chosen == add_file:
            self._create_project_file(container)
        elif chosen == add_window:
            self.new_window()
        elif chosen == add_dir:
            self._create_project_directory(container)
        elif chosen == import_file:
            self._import_project_file(container)
        elif chosen == rename:
            self._rename_project_path(target)
        elif chosen == delete:
            self._delete_project_path(target)

    def mark_dirty(self):
        self.dirty = True
        self.setWindowTitle(f"PCIDE | {self.project.manifest['name']} * | {IDE_VERSION}")

    def handlers(self):
        from pcide.core.routines import scan
        path = self.project.entry_path
        text = self.editor.documents.get(str(path.resolve()), '')
        return sorted({item['sourceName'] for item in scan(text, path.suffix)})

    def select_control(self, control_id):
        if control_id and not any(c["id"] == control_id for c in self.designer.form["controls"]):
            control_id = ""
        self.current_control = control_id
        self.properties.show_selection(self.designer.form, control_id, self.handlers())
        if hasattr(self, "left_catalog") and self._page_available('properties'):
            self.left_catalog.setCurrentWidget(self.properties)
        if control_id:
            control = next(c for c in self.designer.form["controls"] if c["id"] == control_id)
            self._set_hint(control["name"], f'编号：{control_id}\n位置：{control["x"]}, {control["y"]}\n尺寸：{control["width"]} × {control["height"]}\n\n' + PAGE_HINTS["properties"])

    def change_property(self, control_id, changes):
        try:
            self.designer.update_control(control_id, changes)
        except (ValueError, TypeError) as exc:
            self.log(f"属性错误: {exc}")
            self.select_control(control_id)

    def change_form(self, changes):
        candidate = copy.deepcopy(self.designer.form)
        if "window" in changes:
            candidate["form"].setdefault("window", {}).update(changes["window"])
        else:
            candidate["form"].update(changes)
        try:
            validate_form(candidate)
            self.designer.begin_edit()
            self.designer.form = candidate
            self.designer.commit_edit()
            self.designer.load(candidate, True)
        except ValueError as exc:
            self.log(str(exc))

    def change_event(self, control_id, event_name, handler):
        try:
            candidate = copy.deepcopy(self.designer.form)
            data = next(c for c in candidate["controls"] if c["id"] == control_id) if control_id else candidate["form"]
            data.setdefault("events", {})[event_name] = handler
            validate_form(candidate)
            self.designer.begin_edit()
            self.designer.form = candidate
            self.designer.commit_edit()
            self.designer.load(candidate, True)
            if not control_id and event_name == "load":
                self.editor.set_startup_routines(self._startup_routine_names())
            self.designer.select(control_id)
        except ValueError as exc:
            self.log(str(exc))

    def goto_event(self, control_id, event_name):
        data = next(c for c in self.designer.form["controls"] if c["id"] == control_id) if control_id else self.designer.form["form"]
        handler = data.get("events", {}).get(event_name) or f"on_{control_id or 'main_form'}_{event_name}"
        if not valid_name(handler):
            self.log("非法事件处理器")
            return
        self.change_event(control_id, event_name, handler)
        self._open_event_handler(handler)

    def _open_event_handler(self, handler):
        entry = str(self.project.entry_path)
        self.editor.load(entry)
        text = self.editor.documents[entry]
        pattern = (r"\.子程序[ \t]+" + re.escape(handler) + r"(?=[ \t]*(?:\(|,|\r?$))"
                   if self.project.manifest['language'] == 'zhxb' else r"(?:def|function)\s+" + re.escape(handler) + r"\s*\(")
        found = re.search(pattern, text, re.MULTILINE)
        if not found:
            if self.project.manifest["language"] == "python":
                text += f"\n\ndef {handler}(event=None):\n    print('{handler}')\n"
            elif self.project.manifest['language'] == 'zhxb':
                text += f'\n\n.子程序 {handler}\n输出({handler!r})\n'
            else:
                text += f"\n\nfunction {handler}(event) {{\n    console.log('{handler}');\n}}\n"
            self.editor.set_value(text)
            found = re.search(pattern, text, re.MULTILINE)
            self.mark_dirty()
        self.show_page('code')
        self.workspace_tabs.setCurrentWidget(self.tabs)
        self.editor.goto_routine(text[:found.start()].count("\n") + 1)

    def edit_window_menu(self, control_id=None):
        from pcide.core.development import template_for
        if self._project_closed or template_for(self.project).mode != "form":
            self.log("窗口菜单编辑器用于窗口工程。")
            return
        from pcide.core.menus import legacy_menu
        from pcide.ui.menu_dialog import MenuDialog
        menus = [c for c in self.designer.form["controls"] if c["type"] == "MenuBar"]
        selected_id = control_id if isinstance(control_id, str) else self.current_control
        control = next((c for c in menus if c["id"] == selected_id), menus[0] if menus else None)
        try:
            definition = control["properties"].get("menu") if control else None
            if definition is None:
                definition = legacy_menu(control["properties"].get("items", ["文件", "编辑"]) if control else ["文件", "编辑"])
            dialog = MenuDialog(definition, self.handlers(), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._apply_window_menu(control["id"] if control else "", dialog.result_menu)
                if dialog.open_handler:
                    self._open_event_handler(dialog.open_handler)
        except (ValueError, OSError) as exc:
            self.log(str(exc))

    def _apply_window_menu(self, control_id, definition):
        from pcide.core.menus import validate_menu
        from pcide.core.project import ControlModel, unique_control_name
        from pcide.core.control_catalog import control_defaults
        definition = validate_menu(definition)
        candidate = copy.deepcopy(self.designer.form)
        control = next((c for c in candidate["controls"] if c["id"] == control_id and c["type"] == "MenuBar"), None)
        if control is None:
            identity = unique_control_name("MenuBar", {c["id"] for c in candidate["controls"]})
            control = ControlModel(identity, "MenuBar", identity, x=0, y=0,
                width=candidate["form"]["width"], height=26, properties=control_defaults("MenuBar")).to_dict()
            candidate["controls"].append(control)
        control["properties"].update(menu=definition, items=[item["text"] for item in definition if item["kind"] != "separator"])
        validate_form(candidate)
        self.designer.begin_edit()
        self.designer.form = candidate
        self.designer.commit_edit()
        self.designer.load(candidate, True)
        self.designer.select(control["id"])
        return control["id"]

    def reverse_navigation(self, path, line):
        text = self.editor.documents.get(path, "")
        prefix = "\n".join(text.splitlines()[:line])
        names = re.findall(r"(?:def|function)\s+([A-Za-z_][A-Za-z0-9_]*)", prefix)
        if names:
            for control in self.designer.form["controls"]:
                if names[-1] in control["events"].values() and self.current_control != control["id"]:
                    self.designer.select(control["id"])
                    break
        self.statusBar().showMessage(f"{Path(path).name}:{line}")

    def toggle_breakpoint(self, path, line):
        values = self.breakpoints.setdefault(path, set())
        values.remove(line) if line in values else values.add(line)
        self.editor.set_breakpoints(values)
        self._refresh_breakpoints()

    def _refresh_breakpoints(self):
        self.breakpoint_tree.clear()
        for path, lines in sorted(self.breakpoints.items()):
            for line in sorted(lines):
                try:
                    display = Path(path).resolve().relative_to(self.project.root.resolve()).as_posix()
                except ValueError:
                    display = str(path)
                item = QTreeWidgetItem(self.breakpoint_tree, [display, str(line)])
                item.setToolTip(0, str(path))
                item.setData(0, Qt.ItemDataRole.UserRole, (path, line))

    def clear_breakpoints(self):
        self.breakpoints.clear()
        self.editor.set_breakpoints(set())
        self._refresh_breakpoints()

    def goto_breakpoint(self, item, _column=0):
        path, line = item.data(0, Qt.ItemDataRole.UserRole)
        self.editor.load(path)
        self.editor.goto(line)
        self.show_page('code')

    def toggle_grid(self, enabled):
        self.designer.form["grid"]["enabled"] = enabled
        self.designer.viewport().update()
        self.mark_dirty()

    def toggle_snap(self, enabled):
        self.designer.form["grid"]["snap"] = enabled
        self.mark_dirty()

    def _save_now(self):
        for path, text in self.editor.documents.items():
            if self.editor.saved.get(path) == text:
                continue
            if Path(path) == self.project.form_path:
                self.designer.load(validate_form(json.loads(text)))
            elif Path(path) == self.project.flow_path:
                self.flow.load(json.loads(text))
            elif Path(path) == self.project.ide_dir / "project.json":
                candidate = Project(self.project.root, json.loads(text))
                if not candidate.entry_path.is_file():
                    raise ProjectError("project entry file missing")
                if self.runner.active or self.busy:
                    raise RuntimeError("运行期间不能修改工程执行配置")
                self.registry.close()
                from pcide.core.plugins import PluginRegistry
                self.project = candidate
                self.registry = PluginRegistry(candidate.root, candidate.manifest.get("permissions", []))
        self.editor.save()
        atomic_write_json(self.project.ide_dir / "routines.json", self._routine_metadata_index())
        self._refresh_routines()
        from pcide.core.development import SCRIPT_LANGUAGES
        if self.project.manifest['language'] in SCRIPT_LANGUAGES:
            atomic_write_json(self.current_form_path, validate_form(self.designer.form))
            self.project.save_flow(self.flow.flow)
        self.project.save_manifest()
        self.dirty = False
        self.setWindowTitle(f"PCIDE | {self.project.manifest['name']} | {IDE_VERSION}")

    def after_save(self, function):
        if getattr(self, "_project_closed", False):
            try:
                function()
            except Exception as exc:
                self.log(str(exc))
            return
        def saved():
            try:
                self._save_now()
                function()
            except Exception as exc:
                self.log(str(exc))
        self.editor.capture(saved)

    def save_all(self):
        self.after_save(lambda: self.statusBar().showMessage("已保存"))

    def _switch(self, project):
        self.stop_script()
        self.runner.wait()
        for session in tuple(self.tool_sessions.values()):
            if not session.wait(5):raise RuntimeError('外部工具正在退出，请稍后切换工程。')
        self.registry.close()
        from pcide.core.plugins import PluginRegistry
        self.project = project
        self._project_closed = False
        self.current_form_path = project.form_path
        self.token = str(project.root)
        self.registry = PluginRegistry(project.root, project.manifest.get("permissions", []))
        self.breakpoints.clear()
        self.last_artifact=None
        self._load_project()

    def new_project(self):
        if self.busy:
            return
        from pcide.ui.development_dialogs import NewProjectDialog
        dialog=NewProjectDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.create_software_project(*dialog.chooser.selection())

    def create_software_project(self,name,template_id,target):
        if self.busy:return
        def create():
            from pcide.core.development import create_project
            project=create_project(self.paths,name,template_id)
            project.manifest['development']['target']=target
            project.save_manifest();self._switch(project)
        self.after_save(create)

    def show_welcome(self):
        self.workspace_tabs.setEnabled(True)
        self.welcome.refresh();self.workspace_tabs.setCurrentWidget(self.welcome)

    def open_project_path(self,path):
        if not self.busy:self.after_save(lambda:self._switch(Project.open(path)))

    def open_examples(self):
        if self.busy:return
        from pcide.ui.development_dialogs import ExampleDialog
        from pcide.core.examples import instantiate_example
        try:
            dialog=ExampleDialog(self.paths,self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.after_save(lambda:self._switch(instantiate_example(self.paths,dialog.selected_example)))
        except (ValueError,OSError) as exc:QMessageBox.warning(self,'示例中心',str(exc))

    def show_tools(self):
        if self.busy:return
        from pcide.ui.development_dialogs import ToolsDialog
        def configure():
            dialog=ToolsDialog(self.project,self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.statusBar().showMessage('已有工具配置已保存。'+('新建工程和示例副本会复用工作区工具路径。' if dialog.shared.isChecked() else ''))
        self.after_save(configure)

    def show_development_help(self):
        from PySide6.QtWidgets import QTextBrowser
        dialog=QDialog(self);dialog.setWindowTitle('软件 / 游戏 / 编译 / 迭代');dialog.resize(850,650)
        layout=QVBoxLayout(dialog);text=QTextBrowser();text.setOpenExternalLinks(True)
        file=self.paths.docs/'规范/development.md'
        if not file.is_file():file=self.paths.resources/'docs/development.md'
        text.setMarkdown(file.read_text(encoding='utf-8') if file.is_file() else '欢迎页选择模板；帮助→示例中心；Ctrl+B选择编译方式；环境→系统工具与游戏引擎。')
        layout.addWidget(text);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()

    def reload_project(self):
        if self.busy or self.runner.active:return
        if self.dirty:
            QMessageBox.information(self,'重新载入','请先保存编辑内容，再载入外部修改。');return
        self._switch(Project.open(self.project.root))

    def open_project(self):
        if self.busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "打开项目", str(self.paths.projects))
        if folder:
            self.open_project_path(folder)

    def close_project(self):
        if self.busy or self._reject_if_running():
            return
        def close():
            self.stop_script()
            self.runner.wait()
            self.registry.close()
            self.editor.close_project()
            self.project_tree.clear()
            self.designer.load(validate_form(copy.deepcopy({"version": 1, "form": {"title": "未打开项目", "width": 760, "height": 440, "background": "#ffffff", "events": {}, "window": {}}, "controls": [], "grid": {"enabled": True, "size": 10, "snap": True}})))
            self.designer.setEnabled(False)
            self.tabs.setEnabled(False)
            self.setWindowTitle(f"PCIDE | 未打开项目 | {IDE_VERSION}")
            self.statusBar().showMessage("项目已关闭，请新建或打开项目")
            self._project_closed = True
            self._sync_project_pages()
            self.window_menu.setEnabled(False)
            self.toolbox.setEnabled(False)
            self.last_artifact=None
            self.show_welcome()
        self.after_save(close)

    def _project_destination(self, title, default_name):
        target = QFileDialog.getExistingDirectory(self, title, str(self.paths.projects))
        if not target:
            return None
        base = Path(target).resolve()
        name, ok = QInputDialog.getText(self, title, "项目目录名", text=default_name)
        if not ok or not name.strip():
            return None
        name = name.strip()
        if not valid_file_name(name):
            QMessageBox.warning(self, title, "项目目录名包含非法字符")
            return None
        destination = (base / name).resolve()
        if not destination.is_relative_to(self.paths.projects.resolve()):
            QMessageBox.warning(self, title, "项目必须保存到项目目录")
            return None
        if destination.exists():
            QMessageBox.warning(self, title, "目标项目目录已存在")
            return None
        return destination

    def save_project_as(self):
        if getattr(self, "_project_closed", False):
            return
        destination = self._project_destination("项目另存为", self.project.manifest["name"] + "_副本")
        if not destination:
            return
        def save():
            copied = Project.copy_to(self.project.root, destination)
            copied.manifest["name"] = destination.name
            copied.save_manifest()
            self._switch(copied)
        self.after_save(save)

    def import_project(self):
        source = QFileDialog.getExistingDirectory(self, "导入项目", str(self.paths.projects))
        if not source:
            return
        source = Path(source).resolve()
        try:
            imported = Project.open(source)
        except (OSError, ProjectError, ValueError) as exc:
            QMessageBox.warning(self, "无法导入项目", str(exc))
            return
        destination = self._project_destination("导入项目", imported.manifest["name"])
        if not destination:
            return
        def import_now():
            self._switch(Project.copy_to(source, destination))
        self.after_save(import_now)

    def rename_project(self):
        if getattr(self, "_project_closed", False) or self._reject_if_running():
            return
        if not self.project.root.is_relative_to(self.paths.projects.resolve()):
            self.log("当前项目不在工作区项目目录中，不能重命名")
            return
        name, ok = QInputDialog.getText(self, "重命名项目", "项目目录名", text=self.project.root.name)
        if not ok or not name.strip() or not valid_file_name(name.strip()):
            return
        target = (self.project.root.parent / name.strip()).resolve()
        if target.exists():
            QMessageBox.warning(self, "无法重命名项目", "目标项目目录已存在")
            return
        def rename():
            self.project.root.rename(target)
            renamed = Project.open(target)
            renamed.manifest["name"] = target.name
            renamed.save_manifest()
            self._switch(renamed)
        self.after_save(rename)

    def delete_project(self):
        if getattr(self, "_project_closed", False) or self._reject_if_running():
            return
        if not self.project.root.is_relative_to(self.paths.projects.resolve()):
            self.log("当前项目不在工作区项目目录中，不能删除")
            return
        answer = QMessageBox.question(self, "删除项目", f"确定删除项目及全部文件吗？\n{self.project.root.name}",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        target = self.project.root
        def delete():
            shutil.rmtree(target)
            self.stop_script()
            self.runner.wait()
            self.registry.close()
            self.editor.close_project()
            self.project_tree.clear()
            self.workspace_tabs.setEnabled(False)
            self.tabs.setEnabled(False)
            self._project_closed = True
            self.setWindowTitle(f"PCIDE | 未打开项目 | {IDE_VERSION}")
            self.statusBar().showMessage("项目已删除")
        self.after_save(delete)

    def open_file(self, item, _column=0):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            try:
                if Path(path).is_dir():
                    item.setExpanded(not item.isExpanded())
                    return
                if str(path).lower().endswith(".form.json"):
                    self.switch_window(Path(path))
                    return
                self.editor.load(path)
                self.editor.set_breakpoints(self.breakpoints.get(path, set()))
                editor_index = self.tabs.indexOf(self.editor)
                if editor_index >= 0:
                    self.tabs.setTabVisible(editor_index, True)
                self.show_page('code')
                self.workspace_tabs.setCurrentWidget(self.tabs)
            except (ValueError, OSError) as exc:
                self.log(str(exc))

    def new_source_file(self):
        suffix = {"python": ".py", "javascript": ".js", "typescript": ".ts", "zhxb": ".zhxb",'c':'.c','cpp':'.cpp','csharp':'.cs','html':'.html','gdscript':'.gd'}.get(self.project.manifest.get("language"), ".txt")
        name, ok = QInputDialog.getText(self, "新建源码文件", "文件名", text="新文件" + suffix)
        if not ok or not name.strip():
            return
        filename = name.strip()
        if not valid_file_name(filename):
            QMessageBox.warning(self, "无法创建文件", "文件名包含非法字符")
            return
        if not Path(filename).suffix:
            filename += suffix
        target = self.project.root / "src" / filename
        if target.exists():
            QMessageBox.warning(self, "无法创建文件", "同名源码文件已存在")
            return
        def create():
            try:
                target.write_text("", encoding="utf-8")
                self._load_project()
                self.editor.load(target)
                self.show_page('code')
            except OSError as exc:
                self.log(f"无法创建文件：{exc}")
        self.after_save(create)

    def new_window(self):
        from pcide.core.development import template_for
        if template_for(self.project).mode!='form':
            self.log('当前模板使用原生/网页/引擎UI；PCIDE窗口设计器用于窗口脚本模板。');return
        name, ok = QInputDialog.getText(self, "新建窗口", "窗口名称", text="新窗口")
        if not ok or not name.strip():
            return
        safe = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff-]", "", name.strip()) or "新窗口"
        target = self.project.root / "ui" / f"{safe}.form.json"
        if target.exists():
            QMessageBox.warning(self, "无法创建窗口", "同名窗口已存在")
            return
        def create():
            try:
                form = copy.deepcopy(self.project.load_form())
                form["form"]["id"] = safe
                form["form"]["title"] = name.strip()
                atomic_write_json(target, form)
                self.current_form_path = target
                self._load_project()
                self.switch_window(target)
            except (OSError, ProjectError, ValueError) as exc:
                self.log(f"无法创建窗口：{exc}")
        self.after_save(create)

    def rename_current_window(self):
        self._rename_project_path(self.current_form_path.resolve())

    def delete_current_window(self):
        self._delete_project_path(self.current_form_path.resolve())

    def run_script(self):
        if self._project_closed:self.log('请先新建或打开工程。');return
        self.after_save(lambda: self._start_script(False))

    def debug_script(self):
        if self._project_closed:self.log('请先新建或打开工程。');return
        self.after_save(lambda: self._start_script(True))

    def _start_script(self, debug):
        if self.busy:return
        if any(session.active for session in self.tool_sessions.values()):
            self.log('已有程序/引擎在运行；请先停止或关闭后再次运行。');return
        from pcide.core.development import SCRIPT_LANGUAGES, template_for
        if self.project.manifest['language'] not in SCRIPT_LANGUAGES:
            if debug:
                self.log('此模板在外部引擎/系统调试器中调试；IDE断点调试当前支持四种脚本语言。');return
            if template_for(self.project).mode=='engine':self.launch_engine('run');return
            if self.project.manifest['language']=='html':
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.entry_path)));return
            project=self.project
            self.build_cancel.clear()
            from pcide.core.build_service import BuildService
            self.submit(lambda:BuildService(self.paths,self.build_cancel).build(project),self._run_built_artifact);return
        if self.runner.active:
            raise RuntimeError("脚本已在运行")
        if template_for(self.project).mode=='form':self.preview(run_events=True)
        self.runner.start(self.project, debug=debug, breakpoints={p: sorted(v) for p, v in self.breakpoints.items()},
                          keep_alive=template_for(self.project).mode=='form', on_message=self.signals.message.emit,
                          on_done=lambda code, state: self.signals.done.emit(self.runner.session, code, state.error))
        self.variables.clear()
        self.stack.clear()
        self.debug_status.setText('正在调试' if debug else '正在运行')

    def stop_script(self):
        self.cancel_tools()
        self.flow_runner.cancel()
        self.runner.stop()
        if self.runtime_manager:
            self.runtime_manager.close()
            self.runtime_manager = None
        if self.runtime_form:
            self.runtime_form = None

    def debug_command(self, command):
        try:
            self.runner.send(command)
        except RuntimeError as exc:
            self.log(str(exc))

    def preview(self, run_events=False):
        if self._project_closed:self.log('请先新建或打开工程。');return
        from pcide.core.development import template_for
        if template_for(self.project).mode!='form':
            self.log('此模板通过F5在系统程序/浏览器/引擎中预览。');return
        forms = {}
        for path in self.project.window_paths():
            try:
                forms[str(path.resolve())] = copy.deepcopy(self.project.load_window(path))
            except (ProjectError, OSError, ValueError) as exc:
                self.log(str(exc))
        key = str(self.current_form_path.resolve())
        forms[key] = copy.deepcopy(self.designer.form)
        if self.runtime_manager:
            self.runtime_manager.close()
        callback = self._event if run_events else lambda *_: None
        self.runtime_manager = RuntimeWindowManager(forms, callback, self)
        self.runtime_form = self.runtime_manager.open(key)

    def preview_window(self, path):
        self.switch_window(path)
        self.preview()

    def _event(self, handler, payload):
        try:
            self.runner.event(handler, payload)
        except (OSError, RuntimeError) as exc:
            self.log(str(exc))

    def _runtime_message(self, message):
        if self.closing or message.get("session") != self.runner.session:
            return
        kind = message.get("kind")
        if kind in {"stdout", "stderr"}:
            self.log(message["text"])
        elif kind == "error":
            self.log(message.get("traceback", message.get("message", "")))
        elif kind == "ready" and self.runtime_form:
            self.runtime_form.load_event()
        elif kind == "ui.window.open" and self.runtime_manager:
            try:
                self.runtime_manager.open(message["window"])
                self.runtime_manager.load_event(message["window"])
            except (KeyError, TypeError) as exc:
                self.log(f"无法打开运行窗口: {exc}")
        elif kind == "ui.window.close" and self.runtime_manager:
            try:
                self.runtime_manager.close(message["window"])
            except (KeyError, TypeError) as exc:
                self.log(f"无法关闭运行窗口: {exc}")
        elif kind == "ui.set" and self.runtime_manager:
            # Worker messages are delivered through a queued Qt signal.  A
            # handler can emit several ``ui.set`` records and then its
            # ``event.done`` acknowledgement.  Apply the visual update on
            # the next event-loop turn so the acknowledgement is observed by
            # callers before the UI settles; this also keeps the message
            # ordering deterministic for automation and debugger clients.
            update = {
                "id": message.get("id"),
                "properties": message.get("properties", {}),
                "window": message.get("window"),
            }
            QTimer.singleShot(0, lambda update=update: self._apply_runtime_update(update))
        elif kind == "paused":
            self.debug_status.setText(f"已暂停：{Path(message['file']).name}:{message['line']}；变量只读")
            self.show_page('debug')
            self.variables.clear()
            for name, value in message["variables"].items():
                QTreeWidgetItem(self.variables, [name, value])
            self.stack.clear()
            for frame in message["stack"]:
                item = QTreeWidgetItem(self.stack, [frame["function"], f"{frame['file']}:{frame['line']}"])
                item.setData(0, Qt.ItemDataRole.UserRole, frame)
            self.editor.load(message["file"])
            self.editor.goto(message["line"])
            self.statusBar().showMessage(f"暂停 {message['line']}")

    def _runtime_done(self, session, code, error):
        if session == self.runner.session and not self.closing:
            self.debug_status.setText(f'会话已结束，退出 {code}；下方保留最后暂停时的快照。')
            self.log(f"退出 {code}" + (f": {error}" if error else ""))

    def _apply_runtime_update(self, message):
        if self.closing or not self.runtime_manager:
            return
        try:
            found = self.runtime_manager.update_control(message["id"], message["properties"], message["window"])
            if not found:
                raise ValueError(f"unknown UI control: {message['id']}")
        except (KeyError, TypeError, ValueError) as exc:
            self.log(str(exc))

    def goto_stack(self, item, _column):
        frame = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            path = self.project._project_path(frame["file"])
            if type(frame.get("line")) is not int or frame["line"] < 1:
                raise ValueError("调用位置行号无效")
            self.editor.load(path)
            self.editor.goto(frame["line"])
            self.show_page('code')
        except (OSError, ValueError) as exc:
            self.log(str(exc))

    def submit(self, function, on_result=None):
        if self.busy:
            self.log("已有工具任务执行中")
            return
        self.busy = True
        self.task_result = on_result
        self.pool.start(Task(self.token, function, self.signals))

    def _task_done(self, token, result, error):
        self.busy = False
        callback=self.task_result
        self.task_result=None
        if self.closing or token != self.token:
            return
        if callback and not error:
            try:callback(result)
            except Exception as exc:self.log(str(exc))
            return
        self.log(error or json.dumps(result, ensure_ascii=False, default=str, indent=2))
        self.tabs.setCurrentWidget(self.output)

    def run_flow(self):
        flow = copy.deepcopy(self.flow.flow)
        self.after_save(lambda: self.submit(lambda: self.flow_runner.run(flow, registry=self.registry).__dict__))

    def load_plugins(self):
        from pcide.core.plugins import write_example_plugins
        project = self.project
        def load():
            write_example_plugins(project.root)
            result = {}
            for manifest in self.registry.discover():
                if set(manifest.permissions) - self.registry.permissions:
                    result[manifest.id] = {"status": "permissions not granted", "required": manifest.permissions}
                    continue
                result[manifest.id] = self.registry.call(manifest.id, manifest.capabilities[0], {})
            return result
        self.submit(load)

    def install_plugin_archive(self):
        if not self.project:
            return
        source, _ = QFileDialog.getOpenFileName(self, "安装插件包", "", "PCIDE 插件 (*.pcplugin *.zip)")
        if not source:
            return
        source = Path(source).resolve()
        def install():
            import hashlib
            import zipfile
            from pcide.core.plugin_market import install_archive
            try:
                sidecars = [source.with_suffix(source.suffix + ".json"), source.with_suffix(".json")]
                raw = None
                for sidecar in sidecars:
                    if sidecar.is_file():
                        raw = json.loads(sidecar.read_text(encoding="utf-8"))
                        break
                if raw is None:
                    with zipfile.ZipFile(source) as bundle:
                        raw = json.loads(bundle.read("catalog.json").decode("utf-8"))
                item = raw["plugins"][0] if isinstance(raw, dict) and isinstance(raw.get("plugins"), list) else raw
                item = dict(item)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if item.get("sha256", "").lower() != digest:
                    raise ProjectError("插件包 SHA-256 与清单不一致")
                item["sha256"] = digest
                target = install_archive(item, source, self.project.root / "plugins")
                self.registry.discover()
                return {"installed": target.name}
            except (OSError, ValueError, KeyError, IndexError, TypeError, zipfile.BadZipFile) as exc:
                raise ProjectError(f"插件包无效：{exc}") from exc
        self.submit(install)

    def unload_plugins(self):
        try:
            manifests = self.registry.discover()
        except Exception as exc:
            self.log(str(exc))
            return
        if not manifests:
            self.log("没有已安装插件")
            return
        labels = [manifest.id for manifest in manifests]
        plugin_id, ok = QInputDialog.getItem(self, "卸载插件", "插件", labels, editable=False)
        if not ok:
            return
        project = self.project
        def unload():
            from pcide.core.plugin_market import uninstall_plugin
            self.registry.unload(plugin_id)
            uninstall_plugin(plugin_id, project.root / "plugins")
            self.registry.discover()
            return {"uninstalled": plugin_id}
        self.submit(unload)

    def build(self):
        if self._project_closed:self.log('请先新建或打开工程。');return
        if self.busy:return
        from pcide.ui.development_dialogs import BuildDialog
        dialog=BuildDialog(self.project,self.paths,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:
                # Keep the selected build contract in the project.  Previously
                # the dialog only changed the in-memory manifest, so reopening
                # a project silently reverted target/configuration/jobs and
                # made iterative builds use an old profile.
                self.project.manifest['development']=dialog.settings()
                self.project.save_manifest()
            except (ValueError, OSError) as exc:
                self.log('无法保存编译设置：'+str(exc))
                return
            self.quick_build(force=dialog.force)

    def quick_build(self,checked=False,force=False):
        if self._project_closed:self.log('请先新建或打开工程。');return
        if self.busy:return
        if any(session.active for session in self.tool_sessions.values()):
            self.log('请先停止或关闭当前程序/引擎，再编译；Shift+F5可停止。');return
        project=self.project
        def start():
            from pcide.core.build_service import BuildService
            self.build_cancel.clear()
            self.log('开始编译；停止按钮可取消，输出将包含耗时、体积、缓存状态与日志。')
            self.submit(lambda:BuildService(self.paths,self.build_cancel).build(project,force=force),self._built)
        self.after_save(start)

    def _built(self,result):
        self.last_artifact=result.get('artifact')
        self.log(json.dumps(result,ensure_ascii=False,indent=2));self.tabs.setCurrentWidget(self.output)
        self.workspace_tabs.setCurrentWidget(self.tabs)

    def _run_built_artifact(self,result):
        self._built(result)
        self._launch_tool([result['artifact']],'程序',cwd=Path(result['artifact']).parent,
                          timeout=self.project.manifest['execution']['timeout_seconds'],
                          interactive=self.project.manifest['language'] in {'c','cpp','csharp'} and
                                      self.project.manifest['development']['template'] not in {'cpp-win32','csharp-winforms'})

    def show_build_artifact(self):
        if not self.last_artifact:self.log('请先编译一个项目。');return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.last_artifact).parent)))

    def cancel_tools(self):
        self.build_cancel.set()
        for session in self.tool_sessions.values():session.stop()

    def launch_engine(self,action='editor'):
        if self._project_closed:self.log('请先新建或打开工程。');return
        from pcide.core.development import template_for
        template=template_for(self.project)
        if template.mode!='engine':self.log('请从欢迎页新建Unity/Godot工程，或在引擎模板中绑定已有工程。');return
        def launch():
            from pcide.core.engines import engine_command
            from pcide.core.toolchains import require_tool
            engine='unity' if template.id.startswith('unity') else 'godot'
            selected='editor' if engine=='unity' and action=='run' else action
            self._launch_tool(engine_command(self.project,require_tool(self.project,engine),selected),engine)
        self.after_save(launch)

    def _launch_tool(self,command,label,cwd=None,timeout=86400,interactive=False):
        from pcide.core.tool_session import ToolSession
        from pcide.core.build_service import BuildService
        if any(session.active for session in self.tool_sessions.values()):
            self.log('已有外部程序/引擎在运行，关闭或停止后再启动。');return
        identity=uuid.uuid4().hex
        log=self.paths.logs/('session-'+identity+'.log')
        self.log(label+'已启动；停止/切换项目/退出IDE时回收。日志：'+str(log))
        environment=BuildService.system_environment()
        configured=self.project.manifest.get('development',{}).get('tools',{})
        if configured.get('dotnet'):environment['DOTNET_ROOT']=str(Path(configured['dotnet']).parent)
        driver=configured.get('cxx') or configured.get('cc')
        if driver:environment['PATH']=str(Path(driver).parent)+os.pathsep+environment.get('PATH','')
        self.tool_sessions[identity]=ToolSession(command,cwd=cwd or self.project.root,log_path=log,
            environment=environment,on_done=lambda result:self.signals.tool.emit(identity,result),timeout=timeout,
            interactive=interactive,on_output=lambda value:self.signals.tool_output.emit(identity,value))
        self.console_input.setEnabled(interactive);self.console_send.setEnabled(interactive)

    def _tool_output(self,identity,value):
        if identity in self.tool_sessions:self.log(value)

    def send_console_input(self):
        session=next((value for value in self.tool_sessions.values() if value.active and value.input is not None),None)
        if session is None:self.log('请先用F5运行控制台程序。');return
        try:
            session.send(self.console_input.text());self.console_input.clear()
        except (ValueError,RuntimeError) as exc:self.log(str(exc))

    def _tool_done(self,identity,result):
        self.tool_sessions.pop(identity,None)
        if not any(session.active and session.input is not None for session in self.tool_sessions.values()):
            self.console_input.setEnabled(False);self.console_send.setEnabled(False)
        if self.closing:return
        self.log('外部工具已结束：'+(result['error'] or '成功')+'；日志：'+result['log'])

    def replay(self):
        if self.runner.trace_path:
            records = self.runner.replay(self.runner.trace_path)
            self.log(json.dumps(records, ensure_ascii=False, indent=2))
            self.tabs.setCurrentWidget(self.output)

    def test_dex(self):
        from pcide.core.dex_bridge import DexBridge
        self.submit(lambda: DexBridge().request("host.describe"))

    def browse_dex(self):
        path, _ = QFileDialog.getOpenFileName(self, "DEX", "", "Android DEX (*.dex)")
        if path:
            from pcide.core.dex_bridge import browse_dex
            self.submit(lambda: browse_dex(path))

    def log(self, text):
        if not self.closing and hasattr(self, "output"):
            value = str(text).rstrip()
            self.output.appendPlainText(value[:16000])
            self.statusBar().showMessage(value.splitlines()[-1][:120] if value else "")

    def closeEvent(self, event):
        if self.dirty and not self.closing:
            answer = QMessageBox.question(self, "保存项目", "保存未完成的修改？",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                event.ignore()
                self.after_save(self.close)
                return
        self.stop_script()
        self.runner.wait(5)
        self.registry.close()
        for session in tuple(self.tool_sessions.values()):
            if not session.wait(5):
                self.log('外部工具正在退出，请稍后关闭。');event.ignore();return
        if not self.pool.waitForDone(5000):
            self.log("工具任务正在收尾，请稍后关闭")
            event.ignore()
            return
        self.closing = True
        self.vision.shutdown()
        self.editor.shutdown()
        event.accept()


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    for mode in ("worker", "plugin_host", "agent_http"):
        if f"--{mode}" in argv:
            if mode == "worker":
                from pcide.core.worker import main as host_main
            elif mode == "plugin_host":
                from pcide.core.plugin_host import main as host_main
            else:
                from pcide.core.agent_http import main as host_main
            return host_main()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--ui-smoke", action="store_true")
    parser.add_argument("--ui-input-smoke", action="store_true")
    parser.add_argument("--editor", choices=("auto", "native", "monaco"), default="auto")
    parser.add_argument("--screenshot")
    parser.add_argument("--report")
    parser.add_argument("--build", action="store_true")
    from pcide.core.development import TARGETS, SCRIPT_LANGUAGES
    parser.add_argument('--build-target',choices=tuple(TARGETS))
    args = parser.parse_args(argv)
    if args.ui_input_smoke:
        args.ui_smoke = True
    if args.editor != "auto":
        os.environ["PCIDE_EDITOR_BACKEND"] = args.editor
    if args.build_target and not args.build:parser.error('--build-target requires --build')
    paths = Paths().ensure()
    target = paths.project("HelloAutomation")
    project = Project.open(args.project or target) if args.project or (target / ".pcide" / "project.json").is_file() else Project.create(paths, "HelloAutomation")
    if args.build and (not args.smoke or project.manifest['language'] not in SCRIPT_LANGUAGES):
        from pcide.core.build_service import BuildService
        try:
            data=BuildService(paths).build(project,args.build_target)
        except Exception as exc:data={'ok':False,'error':str(exc),'language':project.manifest['language']}
        atomic_write_json(args.report or paths.logs/'build-cli.json',data)
        if sys.stdout is not None:print(json.dumps(data,ensure_ascii=True))
        return 0 if data['ok'] else 1
    if args.smoke and project.manifest['language'] not in SCRIPT_LANGUAGES:
        data={'ok':project.entry_path.is_file(),'language':project.manifest['language'],'executed':False,'scope':'project contract; use --build for actual tool execution'}
        if args.report:atomic_write_json(args.report,data)
        if sys.stdout is not None:print(json.dumps(data,ensure_ascii=True))
        return 0 if data['ok'] else 1
    if args.smoke:
        from pcide.core.flow import FlowRunner
        form = project.load_form()
        handlers = [c["events"]["click"] for c in form["controls"] if c["events"].get("click")]
        if form["form"].get("events", {}).get("load"):
            handlers.insert(0, form["form"]["events"]["load"])
        runner = ScriptRunner()
        code, output, state = runner.run_sync(project, timeout=project.manifest.get("execution", {}).get("timeout_seconds", 60), events=handlers)
        flow = FlowRunner().run(project.load_flow())
        data = {"root": str(paths.root), "resources": str(paths.resources), "frozen": bool(getattr(sys, "frozen", False)),
                "language": project.manifest["language"], "script_exit": code, "script_error": state.error,
                "output": output, "ui_updates": [m for m in runner.messages if m["kind"] == "ui.set"], "flow": flow.ok,
                "monaco_assets": (paths.resources / "third_party" / "monaco" / "vs" / "loader.js").is_file()}
        ok = code == 0 and flow.ok and data["monaco_assets"]
        if args.build and ok:
            from pcide.core.build_service import BuildService
            try:
                data["build"] = BuildService(paths).build(project,args.build_target)
            except Exception as exc:
                data["build_error"] = str(exc)
                ok = False
        if args.report:
            atomic_write_json(args.report, data)
        if sys.stdout is not None:
            print(json.dumps(data, ensure_ascii=True))
        return 0 if ok else 1
    register_editor_scheme()
    app = QApplication(sys.argv)
    app.setApplicationName("PCIDE")
    app.setStyle("Fusion")
    window = MainWindow(project, paths)
    if not args.project and not args.ui_smoke:window.show_welcome()
    window.show()
    if args.ui_smoke:
        window.show_page('code')
        smoke_timer = QTimer(window)
        smoke_timer.setSingleShot(True)
        result = {"qt": True, "monaco": False, "editor": "native" if window.editor._fallback else "monaco", "frozen": bool(getattr(sys, "frozen", False)),
                  "resources": str(paths.resources), "language": project.manifest["language"]}
        def complete():
            if args.screenshot:
                window.grab().save(args.screenshot)
            atomic_write_json(args.report or paths.logs / "ui-smoke.json", result)
            smoke_timer.stop()
            window.dirty = False
            window.close()
            app.exit(0 if result["editor_ready"] and (not args.ui_input_smoke or result.get('input', {}).get('ok')) else 2)

        def check_input():
            try:
                from pcide.ui.input_probe import exercise_editor_input
                result['input'] = exercise_editor_input(window)
            except Exception as exc:
                result['input'] = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
            complete()

        def finish():
            def inspected(snapshot):
                try:
                    snapshot = json.loads(snapshot)
                except (ValueError, TypeError):
                    snapshot = None
                result["editor_ready"] = isinstance(snapshot, dict) and snapshot.get("text") == project.entry_path.read_text(encoding="utf-8")
                if project.manifest['language'] not in SCRIPT_LANGUAGES:
                    result['native_source_display_matches'] = isinstance(snapshot, dict) and snapshot.get('displayText', snapshot.get('text')) == project.entry_path.read_text(encoding='utf-8')
                    result['editor_ready'] = result['editor_ready'] and result['native_source_display_matches']
                result['chinese_view_enabled'] = window.chinese_view_action.isEnabled()
                result['support_libraries'] = {window.support_library.topLevelItem(i).text(0):
                    [window.support_library.topLevelItem(i).child(j).text(0) for j in range(window.support_library.topLevelItem(i).childCount())]
                    for i in range(window.support_library.topLevelItemCount())}
                result['code_snippet_categories'] = [window.snippet_tree.topLevelItem(i).text(0) for i in range(window.snippet_tree.topLevelItemCount())]
                result['pages'] = {key: {'available': window._page_available(key), 'visible': tabs.isTabVisible(tabs.indexOf(widget))}
                                   for key, (widget, tabs, _, _) in window.pages.items()}
                result['output_shared'] = window.output.document() is window.output_panel.document()
                result['pages_help_available'] = (paths.docs / '规范/pages.md').is_file() or (paths.resources / 'docs/pages.md').is_file()
                result["editor_hidden_api"] = snapshot.get("hiddenApi") if isinstance(snapshot, dict) else None
                result["monaco"] = result["editor_ready"] and not window.editor._fallback
                if args.ui_input_smoke and result['editor_ready']:
                    # Return from the WebEngine callback before the input probe
                    # requests another JavaScript result; nested callbacks stall.
                    QTimer.singleShot(0, check_input)
                else:
                    complete()
            window.editor.page.runJavaScript("JSON.stringify(pcide.snapshot())", inspected)
        def ready():
            # Exercise the *visible* code pane. A hidden Monaco model can be
            # ready even when the user still sees a blank editor after switching.
            window.show_page('code')
            window.left_catalog.setCurrentWidget(window.support_host)
            QTimer.singleShot(800, finish)
        window.editor.ready.connect(ready)
        def timeout():
            atomic_write_json(args.report or paths.logs / "ui-smoke.json", result)
            window.dirty = False
            window.close()
            app.exit(2)
        smoke_timer.timeout.connect(timeout)
        smoke_timer.start(60000 if args.ui_input_smoke else 15000)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
