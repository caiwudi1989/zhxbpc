from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
    QSplitter, QStyle, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QMainWindow, QMenu,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit)

from pcide.core.paths import IDE_VERSION, Paths, atomic_write_json, read_json
from pcide.core.project import Project, ProjectError, validate_form, valid_file_name, valid_name
from pcide.core.runner import ScriptRunner
from pcide.ui.designer import FormDesigner, Toolbox
from pcide.ui.editor import CodeEditor, register_editor_scheme
from pcide.ui.flow_canvas import FlowCanvas
from pcide.ui.form_runtime import RuntimeForm, RuntimeWindowManager
from pcide.ui.properties import PropertyPanel


class Signals(QObject):
    message = Signal(dict)
    done = Signal(str, int, str)
    task = Signal(str, object, str)


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
        self.busy = False
        self.token = str(self.project.root)
        self.closing = False
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
            self._action("构建可执行文件", self.build, style.SP_DriveHDIcon),
        ]
        for action in actions:
            toolbar.addAction(action)
        file_menu = self.menuBar().addMenu("项目")
        for action in actions[:3]:
            file_menu.addAction(action)
        edit_menu = self.menuBar().addMenu("设计")
        for name, callback, shortcut in [
            ("撤销", lambda: self.designer.undo(), "Ctrl+Z"),
            ("重做", lambda: self.designer.redo(), "Ctrl+Y"),
            ("复制控件", lambda: self.designer.duplicate(), "Ctrl+D"),
            ("删除控件", lambda: self.designer.delete_selected(), "Delete"),
            ("左对齐", lambda: self.designer.align("left"), None),
            ("上对齐", lambda: self.designer.align("top"), None),
            ("等宽", lambda: self.designer.align("width"), None)]:
            edit_menu.addAction(self._action(name, callback, shortcut=shortcut))
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
            debug_menu.addAction(self._action(title, lambda _, cmd=command: self.debug_command(cmd), shortcut=shortcut))
        debug_menu.addAction(self._action("回放最近会话", self.replay))
        tools = self.menuBar().addMenu("扩展")
        tools.addAction(self._action("示例插件", self.load_plugins))
        tools.addAction(self._action("卸载插件", self.unload_plugins))
        tools.addAction(self._action("DEX 浏览", self.browse_dex))
        tools.addAction(self._action("Android 远程主机", self.test_dex))
        tools.addAction(self._action("新建源码文件", self.new_source_file))
        environment_menu = self.menuBar().addMenu("环境")
        environment_menu.addAction(self._action("项目环境", self.show_environment))
        environment_menu.addAction(self._action("重新扫描支持库", self._refresh_support_library))
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
        self.designer.selected.connect(self.select_control)
        self.designer.changed.connect(self.mark_dirty)
        self.designer.event_requested.connect(self.goto_event)
        self.editor = CodeEditor(self.paths)
        self.editor.changed.connect(lambda _: self.mark_dirty())
        self.editor.breakpoint.connect(self.toggle_breakpoint)
        self.editor.cursor.connect(self.reverse_navigation)
        self.editor.error.connect(self.log)
        self._editor_toolbar = QToolBar("代码编辑", self)
        self._editor_toolbar.setMovable(False)
        self._editor_toolbar.addAction(self._action("智能补全", self.trigger_completion, shortcut="Ctrl+Space"))
        self._editor_toolbar.addAction(self._action("折叠/展开区域", self.toggle_editor_fold, shortcut="Ctrl+K"))
        self._editor_toolbar.addAction(self._action("格式化当前文件", self.format_editor, shortcut="Ctrl+Shift+F"))
        chinese_view = self._action("中文易语言视图", self.toggle_chinese_editor)
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
        self.variables = QTreeWidget()
        self.variables.setHeaderLabels(["变量", "值"])
        self.stack = QTreeWidget()
        self.stack.setHeaderLabels(["函数", "位置"])
        self.stack.itemDoubleClicked.connect(self.goto_stack)
        debug_split = QSplitter()
        debug_split.addWidget(self.variables)
        debug_split.addWidget(self.stack)
        from pcide.ui.vision_panel import VisionPanel
        from pcide.ui.data_panel import DataPanel
        self.vision = VisionPanel(self.project, self.paths)
        self.vision.message.connect(self.log)
        self.vision.execute_requested.connect(self.submit)
        self.data_panel = DataPanel(self.project)
        self.data_panel.changed.connect(self.project.save_data)
        self.data_panel.generated.connect(self._show_generated_data)
        self.support_library = QTreeWidget()
        self.support_library.setHeaderLabels(["支持库 / 命令", "说明"])
        self.support_library.setAlternatingRowColors(True)
        self.support_library.itemDoubleClicked.connect(self._insert_library_item)
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
        self.code_tabs = self.tabs
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setDocumentMode(True)
        self.workspace_tabs.addTab(self.designer, "界面设计")
        self.workspace_tabs.addTab(self.tabs, "代码工作区")
        self.properties = PropertyPanel()
        self.properties.property_changed.connect(self.change_property)
        self.properties.form_changed.connect(self.change_form)
        self.properties.event_changed.connect(self.change_event)
        self.properties.event_requested.connect(self.goto_event)
        self.properties.selected.connect(self.designer.select)
        self.right_tabs.addTab(self.toolbox, "控件箱")
        self.left_catalog.insertTab(0, self.support_library, "支持库")
        self.left_catalog.addTab(self.properties, "属性")
        self.left_catalog.setTabPosition(QTabWidget.TabPosition.South)
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
        output_layout.addWidget(QLabel("输出 / 调试信息"))
        output_layout.addWidget(self.output_panel)
        root_layout = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(layout)
        root_layout.addWidget(output_box)
        root_layout.setSizes([720, 180])
        self.setCentralWidget(root_layout)
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

    def _code_tab_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        menu = QMenu(self)
        close = menu.addAction("关闭标签页")
        if menu.exec(self.tabs.tabBar().mapToGlobal(position)) == close:
            self._close_code_tab(index)

    def _load_project(self):
        self.editor.close_project()
        self.current_form_path = self.current_form_path if self.current_form_path.exists() else self.project.form_path
        self.designer.load(validate_form(read_json(self.current_form_path, self.project.load_form())))
        self.flow.load(self.project.load_flow())
        self.data_panel.load(self.project.load_data())
        self.editor.load(self.project.entry_path)
        self.editor.set_completion_items(self._completion_items())
        self.project_tree.clear()
        root = QTreeWidgetItem(self.project_tree, [self.project.manifest["name"]])
        root.setData(0, Qt.ItemDataRole.UserRole, str(self.project.root))
        settings = QTreeWidgetItem(root, ["项目配置.json"])
        settings.setData(0, Qt.ItemDataRole.UserRole, str(self.project.ide_dir / "project.json"))
        labels = {"src": "代码", "ui": "界面", "flows": "流程", "plugins": "插件", "resources": "资源"}
        folders = ["src", "ui", "flows", "plugins", "resources"]
        folders.extend(sorted(p.name for p in self.project.root.iterdir() if p.is_dir() and p.name not in folders and p.name not in {".pcide", "cache"}))
        for folder in folders:
            node = QTreeWidgetItem(root, [labels.get(folder, folder)])
            node.setData(0, Qt.ItemDataRole.UserRole, str(self.project.root / folder))
            self._populate_project_tree(node, self.project.root / folder)
        root.setExpanded(False)
        settings.setExpanded(True)
        program = QTreeWidgetItem(self.project_tree, ["程序数据"])
        program.setData(0, Qt.ItemDataRole.UserRole + 2, "程序数据")
        for label in ("窗口", "常量表", "资源表", "模块引用表", "外部文件记录表"):
            child = QTreeWidgetItem(program, [label])
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
        root_index = self.project_tree.indexOfTopLevelItem(root)
        if root_index >= 0:
            self.project_tree.takeTopLevelItem(root_index)
            self.project_tree.addTopLevelItem(root)

    def _open_program_item(self, item, column=0):
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
            for name in ("如果", "否则", "循环", "返回", "真", "假", "空", "导入", "定义")
        ]
        try:
            data = self.project.load_data()
        except (OSError, ValueError, ProjectError):
            data = {"variables": [], "constants": [], "apis": []}
        for key, kind, detail in (("variables", "variable", "项目变量"), ("constants", "constant", "项目常量")):
            for value in data.get(key, []):
                label = value.get("id") or value.get("label")
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

    def _refresh_routines(self):
        if not hasattr(self, "routine_list"):
            return
        self.routine_list.clear()
        try:
            text = self.project.entry_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        pattern = r"(?m)^\s*(?:def|function)\s+([A-Za-z_][A-Za-z0-9_]*)"
        section = self._replace_program_section("子程序")
        for match in re.finditer(pattern, text):
            line = text.count("\n", 0, match.start()) + 1
            item = QTreeWidgetItem(self.routine_list, [match.group(1), f"第 {line} 行"])
            item.setData(0, Qt.ItemDataRole.UserRole, line)
            visible = QTreeWidgetItem(section, [match.group(1) + f"（第 {line} 行）"])
            visible.setData(0, Qt.ItemDataRole.UserRole + 1, line)

    def _open_routine(self, item, _column=0):
        line = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(line, int):
            line = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(line, int):
            self.tabs.setCurrentWidget(self.editor)
            self.editor.goto(line)

    def _refresh_support_library(self):
        if not hasattr(self, "support_library"):
            return
        self.support_library.clear()
        groups = {
            "系统支持库": [("程序_取运行目录", "取得程序运行目录"), ("程序_延时", "系统延时"),
                            ("系统_取环境变量", "读取系统环境变量"), ("系统_执行", "执行系统命令")],
            "窗口与界面支持库": [("窗口_创建", "创建窗口"), ("窗口_关闭", "关闭窗口"), ("窗口_重绘", "重绘窗口"),
                                  ("窗口_置标题", "设置窗口标题"), ("鼠标_取位置", "取得鼠标位置")],
            "文本与文件支持库": [("文本_取长度", "文本长度"), ("文本_替换", "文本替换"), ("文本_分割", "文本分割"),
                                  ("文件_读入", "读取文件"), ("文件_写出", "写出文件"), ("目录_创建", "创建目录")],
            "网络与数据支持库": [("网络_请求", "发起网络请求"), ("网络_下载", "下载文件"), ("JSON_解析", "解析 JSON"),
                                  ("数据库_查询", "执行数据库查询")],
            "图像与多媒体支持库": [("图像_加载", "加载图像"), ("图像_保存", "保存图像"), ("声音_播放", "播放声音")],
            "调试支持库": [("调试输出", "输出调试信息"), ("调试_断点", "设置断点"), ("日志_写入", "写入日志")],
        }
        try:
            data = self.project.load_data()
        except (OSError, ValueError, ProjectError):
            data = {"variables": [], "constants": [], "apis": []}
        project_entries = []
        for key in ("variables", "constants", "apis"):
            for value in data.get(key, []):
                label = value.get("id") or value.get("label")
                if label:
                    project_entries.append((label, value.get("description", key)))
        if project_entries:
            groups["项目数据"] = project_entries
        for group, entries in groups.items():
            parent = QTreeWidgetItem(self.support_library, [group, ""])
            parent.setExpanded(True)
            for label, description in entries:
                item = QTreeWidgetItem(parent, [label, description])
                item.setData(0, Qt.ItemDataRole.UserRole, label)

    def _refresh_data_summary(self):
        if not hasattr(self, "data_summary"):
            return
        self.data_summary.clear()
        try:
            data = self.project.load_data()
        except (OSError, ValueError, ProjectError):
            data = {"variables": [], "constants": [], "apis": []}
        section = self._replace_program_section("变量 / 常量")
        for group, key in (("变量", "variables"), ("常量", "constants"), ("支持库 API", "apis")):
            parent = QTreeWidgetItem(section, [group, ""])
            parent.setExpanded(True)
            for value in data.get(key, []):
                label = value.get("label") or value.get("id") or ""
                typ = value.get("type") or value.get("return_type") or ""
                item = QTreeWidgetItem(parent, [label, str(typ)])
                item.setData(0, Qt.ItemDataRole.UserRole, value.get("id", label))

    def _insert_library_item(self, item, _column=0):
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value and hasattr(self.editor, "insert_text"):
            self.editor.insert_text(str(value))
            self.tabs.setCurrentWidget(self.editor)

    def _add_toolbox_item(self, item, _column=0):
        kind = item.data(0, Qt.ItemDataRole.UserRole)
        if kind:
            self.designer.add(kind)

    def trigger_completion(self):
        if self.editor.loaded:
            self.editor.page.runJavaScript("pcide.triggerSuggest()")

    def toggle_editor_fold(self):
        if self.editor.loaded:
            self.editor.page.runJavaScript("pcide.toggleFold()")

    def format_editor(self):
        if self.editor.loaded:
            self.editor.page.runJavaScript("pcide.formatDocument()")

    def toggle_chinese_editor(self):
        if self.editor.loaded:
            self.editor.toggle_chinese_view()

    def show_environment(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("项目环境")
        dialog.setMinimumWidth(520)
        form = QFormLayout(dialog)
        language = QComboBox(dialog)
        language.addItems(["Python", "JavaScript / Node.js", "TypeScript / Node.js"])
        current = self.project.manifest.get("language", "python")
        language.setCurrentIndex({"python": 0, "javascript": 1, "typescript": 2}.get(current, 0))
        python_path = QLineEdit(str(self.paths.root / "runtime" / "dev" / "python.exe"))
        node_path = QLineEdit(str(self.paths.root / "runtime" / "dev" / "node.exe"))
        form.addRow("项目语言", language)
        form.addRow("Python 解释器", python_path)
        form.addRow("Node.js 运行时", node_path)
        form.addRow(QLabel("代码补全会同时使用项目变量、常量、API 和窗口事件。"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.manifest["environment"] = {
                "language": language.currentText(),
                "python": python_path.text().strip(),
                "node": node_path.text().strip(),
            }
            self.after_save(lambda: self.statusBar().showMessage("项目环境已保存"))

    def _populate_project_tree(self, parent, directory):
        if not directory.is_dir():
            return
        for path in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.casefold())):
            if path.name in {"__pycache__", ".git"} or path.suffix in {".pdb", ".pyc"}:
                continue
            item = QTreeWidgetItem(parent, [path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            if path.is_dir():
                self._populate_project_tree(item, path)

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
            self._show_designer_view()
            self.statusBar().showMessage(f"已切换窗口：{form['form']['title']}")
            if self.runtime_manager and self.runtime_form:
                self.runtime_form.close()
                self.runtime_form = self.runtime_manager.open(str(self.current_form_path))
        except (ProjectError, OSError, ValueError) as exc:
            self.log(str(exc))

    def _show_generated_data(self, language, source):
        self.output.setPlainText(source)
        self.output_panel.setPlainText(source)
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
                self.tabs.setCurrentWidget(self.editor)
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
        text = self.editor.documents.get(str(self.project.entry_path), "")
        return sorted(set(re.findall(r"(?:def|function)\s+([A-Za-z_][A-Za-z0-9_]*)", text)))

    def select_control(self, control_id):
        self.current_control = control_id
        self.properties.show_selection(self.designer.form, control_id, self.handlers())
        if hasattr(self, "left_catalog"):
            self.left_catalog.setCurrentWidget(self.properties)

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
            self.designer.select(control_id)
        except ValueError as exc:
            self.log(str(exc))

    def goto_event(self, control_id, event_name):
        entry = str(self.project.entry_path)
        self.editor.load(entry)
        data = next(c for c in self.designer.form["controls"] if c["id"] == control_id) if control_id else self.designer.form["form"]
        handler = data.get("events", {}).get(event_name) or f"on_{control_id or 'main_form'}_{event_name}"
        if not valid_name(handler):
            self.log("非法事件处理器")
            return
        self.change_event(control_id, event_name, handler)
        text = self.editor.documents[entry]
        pattern = r"(?:def|function)\s+" + re.escape(handler) + r"\s*\("
        found = re.search(pattern, text)
        if not found:
            if self.project.manifest["language"] == "python":
                text += f"\n\ndef {handler}(event=None):\n    print('{handler}')\n"
            else:
                text += f"\n\nfunction {handler}(event) {{ console.log('{handler}'); }}\n"
            self.editor.set_value(text)
            found = re.search(pattern, text)
            self.mark_dirty()
        self.tabs.setCurrentWidget(self.editor)
        self.workspace_tabs.setCurrentWidget(self.tabs)
        self.editor.goto(text[:found.start()].count("\n") + 1)

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
        atomic_write_json(self.current_form_path, validate_form(self.designer.form))
        self.project.save_flow(self.flow.flow)
        self.project.save_manifest()
        self.dirty = False
        self.setWindowTitle(f"PCIDE | {self.project.manifest['name']} | {IDE_VERSION}")

    def after_save(self, function):
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
        self.registry.close()
        from pcide.core.plugins import PluginRegistry
        self.project = project
        self.current_form_path = project.form_path
        self.token = str(project.root)
        self.registry = PluginRegistry(project.root, project.manifest.get("permissions", []))
        self.breakpoints.clear()
        self._load_project()

    def new_project(self):
        if self.busy:
            return
        name, ok = QInputDialog.getText(self, "新建项目", "名称", text="MyScript")
        if not ok:
            return
        language, ok = QInputDialog.getItem(self, "新建项目", "语言", ["python", "javascript", "typescript"], editable=False)
        if ok:
            self.after_save(lambda: self._switch(Project.create(self.paths, name, language)))

    def open_project(self):
        if self.busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "打开项目", str(self.paths.projects))
        if folder:
            self.after_save(lambda: self._switch(Project.open(folder)))

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
                self.tabs.setCurrentWidget(self.editor)
                self.workspace_tabs.setCurrentWidget(self.tabs)
            except (ValueError, OSError) as exc:
                self.log(str(exc))

    def new_source_file(self):
        suffix = {"python": ".py", "javascript": ".js", "typescript": ".ts"}.get(self.project.manifest.get("language"), ".txt")
        name, ok = QInputDialog.getText(self, "新建源码文件", "文件名", text="新文件" + suffix)
        if not ok or not name.strip():
            return
        filename = name.strip()
        if not valid_file_name(filename):
            QMessageBox.warning(self, "无法创建文件", "文件名包含非法字符")
            return
        if Path(filename).suffix.lower() not in {".py", ".js", ".ts"}:
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
                self.tabs.setCurrentWidget(self.editor)
            except OSError as exc:
                self.log(f"无法创建文件：{exc}")
        self.after_save(create)

    def new_window(self):
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
        self.after_save(lambda: self._start_script(False))

    def debug_script(self):
        self.after_save(lambda: self._start_script(True))

    def _start_script(self, debug):
        if self.runner.active:
            raise RuntimeError("脚本已在运行")
        self.preview()
        self.runner.start(self.project, debug=debug, breakpoints={p: sorted(v) for p, v in self.breakpoints.items()},
                          keep_alive=True, on_message=self.signals.message.emit,
                          on_done=lambda code, state: self.signals.done.emit(self.runner.session, code, state.error))

    def stop_script(self):
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

    def preview(self):
        forms = {}
        for path in self.project.window_paths():
            try:
                forms[str(path.resolve())] = copy.deepcopy(self.project.load_window(path))
            except (ProjectError, OSError, ValueError) as exc:
                self.log(str(exc))
        key = str(self.current_form_path.resolve())
        forms.setdefault(key, copy.deepcopy(self.designer.form))
        if self.runtime_manager:
            self.runtime_manager.close()
        self.runtime_manager = RuntimeWindowManager(forms, self._event, self)
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
            try:
                found = self.runtime_manager.update_control(message["id"], message.get("properties", {}), message.get("window"))
                if not found:
                    raise ValueError(f"unknown UI control: {message['id']}")
            except ValueError as exc:
                self.log(str(exc))
        elif kind == "paused":
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
            self.log(f"退出 {code}" + (f": {error}" if error else ""))

    def goto_stack(self, item, _column):
        frame = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            self.editor.load(frame["file"])
            self.editor.goto(frame["line"])
            self.tabs.setCurrentWidget(self.editor)
        except OSError as exc:
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
        if self.closing or token != self.token:
            return
        if self.task_result and not error:
            self.task_result(result)
            self.task_result = None
            return
        self.log(error or json.dumps(result, ensure_ascii=False, default=str, indent=2))
        self.task_result = None
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

    def unload_plugins(self):
        self.submit(lambda: (self.registry.close(), {"status": "unloaded"})[1])

    def build(self):
        from pcide.core.builder import BuildManager
        project = self.project
        self.after_save(lambda: self.submit(lambda: BuildManager(self.paths).build(project, "standalone")))

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
            self.output_panel.appendPlainText(value[:16000])
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
    for mode in ("worker", "plugin_host"):
        if f"--{mode}" in argv:
            if mode == "worker":
                from pcide.core.worker import main as host_main
            else:
                from pcide.core.plugin_host import main as host_main
            return host_main()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--ui-smoke", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--report")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args(argv)
    if args.build and not args.smoke:
        parser.error("--build requires --smoke")
    paths = Paths().ensure()
    target = paths.project("HelloAutomation")
    project = Project.open(args.project or target) if args.project or (target / ".pcide" / "project.json").is_file() else Project.create(paths, "HelloAutomation")
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
            from pcide.core.builder import BuildManager
            try:
                data["build"] = BuildManager(paths).build(project, "standalone")
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
    window.show()
    if args.ui_smoke:
        result = {"qt": True, "monaco": False, "frozen": bool(getattr(sys, "frozen", False)),
                  "resources": str(paths.resources), "language": project.manifest["language"]}
        def finish():
            def inspected(snapshot):
                try:
                    snapshot = json.loads(snapshot)
                except (ValueError, TypeError):
                    snapshot = None
                result["monaco"] = isinstance(snapshot, dict) and snapshot.get("text") == project.entry_path.read_text(encoding="utf-8")
                if args.screenshot:
                    window.grab().save(args.screenshot)
                atomic_write_json(args.report or paths.logs / "ui-smoke.json", result)
                window.close()
                app.exit(0 if result["monaco"] else 2)
            window.editor.page.runJavaScript("JSON.stringify(pcide.snapshot())", inspected)
        def ready():
            QTimer.singleShot(800, finish)
        window.editor.ready.connect(ready)
        def timeout():
            atomic_write_json(args.report or paths.logs / "ui-smoke.json", result)
            window.close()
            app.exit(2)
        QTimer.singleShot(15000, timeout)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
