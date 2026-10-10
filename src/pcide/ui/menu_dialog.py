from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from pcide.core.menus import validate_menu
from pcide.ui.development_dialogs import dialog_buttons


class MenuDialog(QDialog):
    def __init__(self, menu, handlers=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("窗口菜单编辑器")
        self.resize(950, 610)
        self.menu = copy.deepcopy(menu)
        self.current = None
        self.nodes = {}
        self.open_handler = ""
        self.loading = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("编辑菜单层级、标识、快捷键和处理子程序；保存后参与窗口预览及实际运行。"))
        bar = QHBoxLayout()
        for label, callback in (("添加同级", self.add_sibling), ("添加下级", self.add_child),
                                ("分隔线", lambda: self.add_sibling("separator")), ("删除", self.remove_selected),
                                ("上移", lambda: self.move(-1)), ("下移", lambda: self.move(1))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["菜单标题", "标识", "处理子程序", "快捷键"])
        self.tree.setColumnWidth(0, 195)
        self.tree.currentItemChanged.connect(self.select_item)
        fields = QWidget()
        form = QFormLayout(fields)
        self.identity, self.title, self.shortcut = QLineEdit(), QLineEdit(), QLineEdit()
        self.kind = QComboBox()
        for label, value in (("菜单项", "item"), ("子菜单", "menu"), ("分隔线", "separator")):
            self.kind.addItem(label, value)
        self.handler = QComboBox()
        self.handler.setEditable(True)
        self.handler.addItems([""] + sorted(set(handlers)))
        self.enabled, self.visible, self.checkable, self.checked = (QCheckBox() for _ in range(4))
        for label, field in (("标识", self.identity), ("标题", self.title), ("类型", self.kind),
                             ("快捷键", self.shortcut), ("处理子程序", self.handler), ("启用", self.enabled),
                             ("可见", self.visible), ("可勾选", self.checkable), ("当前勾选", self.checked)):
            form.addRow(label, field)
        self.kind.currentIndexChanged.connect(self.update_fields)
        self.checkable.toggled.connect(lambda checked: self.checked.setEnabled(checked and self.kind.currentData() == "item"))
        edit_event = QPushButton("创建 / 打开处理子程序")
        edit_event.clicked.connect(self.edit_event)
        form.addRow(edit_event)
        split = QSplitter()
        split.addWidget(self.tree)
        split.addWidget(fields)
        split.setSizes([620, 330])
        layout.addWidget(split, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = dialog_buttons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rebuild()

    def commit_current(self):
        if not self.current or self.loading:
            return
        node = self.node(self.current)
        node.update(id=self.identity.text().strip(), text=self.title.text(), kind=self.kind.currentData(),
                    shortcut=self.shortcut.text().strip(), handler=self.handler.currentText().strip(),
                    enabled=self.enabled.isChecked(), visible=self.visible.isChecked(),
                    checkable=self.checkable.isChecked(), checked=self.checked.isChecked())
        if node["kind"] != "item":
            node.update(shortcut="", handler="", checkable=False, checked=False)
        elif not node["checkable"]:
            node["checked"] = False
        for column, value in enumerate((node["text"] or "────", node["id"], node["handler"], node["shortcut"])):
            self.current.setText(column, value)

    def select_item(self, item, previous=None):
        self.commit_current()
        self.current = item
        self.loading = True
        node = self.node(item) if item else {}
        self.identity.setText(node.get("id", ""))
        self.title.setText(node.get("text", ""))
        self.kind.setCurrentIndex(max(0, self.kind.findData(node.get("kind", "item"))))
        self.shortcut.setText(node.get("shortcut", ""))
        self.handler.setCurrentText(node.get("handler", ""))
        for field, key in ((self.enabled, "enabled"), (self.visible, "visible"),
                           (self.checkable, "checkable"), (self.checked, "checked")):
            field.setChecked(node.get(key, key in {"enabled", "visible"}))
        self.loading = False
        self.update_fields()

    def update_fields(self, *_):
        selected = self.current is not None
        leaf = self.kind.currentData() == "item"
        for field in (self.identity, self.kind, self.enabled, self.visible):
            field.setEnabled(selected)
        self.title.setEnabled(selected and self.kind.currentData() != "separator")
        for field in (self.shortcut, self.handler, self.checkable):
            field.setEnabled(selected and leaf)
        self.checked.setEnabled(selected and leaf and self.checkable.isChecked())

    def rebuild(self, selected=None):
        self.current = None
        self.nodes = {}
        self.tree.blockSignals(True)
        self.tree.clear()
        selected_item = None
        def append(parent, nodes):
            nonlocal selected_item
            for node in nodes:
                item = QTreeWidgetItem(parent, [node.get("text") or "────", node["id"], node.get("handler", ""), node.get("shortcut", "")])
                key = len(self.nodes)
                self.nodes[key] = node
                item.setData(0, Qt.ItemDataRole.UserRole, key)
                if node is selected:
                    selected_item = item
                append(item, node.get("children", []))
                item.setExpanded(True)
        append(self.tree, self.menu)
        self.tree.blockSignals(False)
        self.tree.setCurrentItem(selected_item or self.tree.topLevelItem(0))
        if self.tree.currentItem() is None:
            self.select_item(None)

    def container(self):
        item = self.tree.currentItem()
        if item and item.parent():
            return self.node(item.parent())["children"]
        return self.menu

    def node(self, item):
        return self.nodes[item.data(0, Qt.ItemDataRole.UserRole)]

    def new_node(self, kind):
        identities = set()
        def collect(nodes):
            for node in nodes:
                identities.add(node["id"])
                collect(node.get("children", []))
        collect(self.menu)
        index = 1
        while f"menu_{index}" in identities:
            index += 1
        return {"id": f"menu_{index}", "text": "" if kind == "separator" else "新菜单" if kind == "menu" else "新菜单项",
                "kind": kind, "children": []}

    def add_sibling(self, kind="item"):
        if isinstance(kind, bool):
            kind = "item"
        self.commit_current()
        container = self.container()
        node = self.new_node("menu" if container is self.menu and kind != "separator" else kind)
        current_node = self.node(self.current) if self.current else None
        container.insert(container.index(current_node) + 1 if current_node in container else len(container), node)
        self.rebuild(node)

    def add_child(self):
        self.commit_current()
        if not self.current:
            return
        parent = self.node(self.current)
        if parent["kind"] != "menu":
            self.error.setText("请先选择子菜单；带下级项目的节点必须使用“子菜单”类型。")
            return
        node = self.new_node("item")
        parent.setdefault("children", []).append(node)
        self.rebuild(node)

    def remove_selected(self):
        if self.current:
            self.container().remove(self.node(self.current))
            self.rebuild()

    def move(self, offset):
        self.commit_current()
        if not self.current:
            return
        container = self.container()
        node = self.node(self.current)
        index = container.index(node)
        target = index + offset
        if 0 <= target < len(container):
            container[index], container[target] = container[target], container[index]
            self.rebuild(node)

    def edit_event(self):
        self.commit_current()
        if self.current and self.kind.currentData() == "item":
            self.handler.setCurrentText(self.handler.currentText().strip() or f"on_{self.identity.text().strip()}_click")
            self.save(open_event=True)

    def save(self, _checked=False, open_event=False):
        self.commit_current()
        try:
            self.result_menu = validate_menu(self.menu)
            def shortcuts(nodes):
                for node in nodes:
                    if node["shortcut"] and QKeySequence(node["shortcut"]).isEmpty():
                        raise ValueError("菜单快捷键无效")
                    shortcuts(node["children"])
            shortcuts(self.result_menu)
            if open_event:
                self.open_handler = self.handler.currentText().strip()
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))
