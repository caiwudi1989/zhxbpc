from __future__ import annotations

import copy
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QTableWidget, QTableWidgetItem,
    QLabel, QMessageBox, QToolButton, QVBoxLayout, QWidget)

from pcide.core.data import DataError, SCOPE_LABELS, TYPES, generate_code, reference_name, validate_data
from pcide.core.i18n import make_id


class DataPanel(QWidget):
    changed = Signal(dict)
    generated = Signal(str, str)
    HEADERS = ["名称", "代码名称", "类别", "类型/返回值", "初始值/库", "作用域", "参数/成员", "调用约定", "权限/依赖", "备注", "所属窗口/模块/子程序", "静态", "数组维数"]

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.data = {"version": 1, "variables": [], "constants": [], "apis": []}
        self.group = QComboBox()
        for title, value in (("全局变量表", "global"), ("窗口变量表", "window"), ("程序集变量表", "module"),
                             ("局部变量表", "local"), ("常量表", "constants"), ("自定义数据类型表", "types"), ("DLL 命令表", "apis")):
            self.group.addItem(title, value)
        self.group.currentIndexChanged.connect(lambda _: self.load(self.data))
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.itemChanged.connect(self._changed)
        bar = QHBoxLayout()
        bar.addWidget(self.group)
        for text, kind in (("添加变量", "variable"), ("添加常量", "constant"), ("添加数据类型", "type"), ("添加 DLL/API", "api"), ("删除", "delete")):
            button = QToolButton(text=text)
            button.clicked.connect(lambda _, k=kind: self._add(k) if k != "delete" else self._delete())
            bar.addWidget(button)
        self.language = QComboBox()
        self.language.addItems(["python", "javascript", "typescript"])
        generate = QToolButton(text="生成代码")
        generate.clicked.connect(lambda: self.generated.emit(self.language.currentText(), generate_code(self.data, self.language.currentText())))
        bar.addWidget(self.language)
        bar.addWidget(generate)
        bar.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.table)
        self.hint = QLabel("双击单元格编辑；类型和作用域使用下拉选择。代码引用使用“代码名称”，窗口/程序集使用“所属名称.代码名称”。")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    def select_group(self, group):
        self.group.setCurrentIndex(max(0, self.group.findData(group)))

    def _visible(self, key, item):
        selected = self.group.currentData()
        return key == selected or key == "variables" and item["scope"] == selected

    def load(self, data):
        try:
            self.data = validate_data(data or {})
        except DataError as exc:
            QMessageBox.warning(self, "数据错误", str(exc))
            return
        rows = []
        self.row_items = []
        for item in self.data["variables"]:
            if self._visible("variables", item):
                rows.append([item["label"], item["id"], "变量", item["type"], item["default"], SCOPE_LABELS[item["scope"]], "", "", "", item["description"], item["owner"], str(item["static"]), item["array"]])
                self.row_items.append(("variables", item["id"]))
        for item in self.data["constants"]:
            if self._visible("constants", item):
                rows.append([item["label"], item["id"], "常量", item["type"], item["value"], SCOPE_LABELS[item["scope"]], "", "", "", item["description"], item["owner"], str(item["static"]), item["array"]])
                self.row_items.append(("constants", item["id"]))
        for item in self.data["apis"]:
            if not self._visible("apis", item):
                continue
            params = json.dumps(item["parameters"], ensure_ascii=False, separators=(",", ":"))
            grants = ",".join(item["permissions"]) + (" / " + ",".join(item["dependencies"]) if item["dependencies"] else "")
            rows.append([item["label"], item["id"], "DLL/API", item["return_type"], item["library"], "公共", params, item["calling_convention"], grants, item["description"], "", "False", ""])
            self.row_items.append(("apis", item["id"]))
        for item in self.data["types"]:
            if self._visible("types", item):
                rows.append([item["label"], item["id"], "数据类型", "结构", "", "公共", json.dumps(item["members"], ensure_ascii=False), "", "", item["description"], "", "False", ""])
                self.row_items.append(("types", item["id"]))
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
                if c == 2:
                    self.table.item(r, c).setFlags(self.table.item(r, c).flags() & ~Qt.ItemFlag.ItemIsEditable)
            for col, options in ((3, list(TYPES) + [item["id"] for item in self.data["types"]]), (5, list(SCOPE_LABELS.values())), (11, ["False", "True"])):
                if values[2] in {"DLL/API", "数据类型"} and col in {5, 11}:
                    continue
                box = QComboBox()
                box.setEditable(col == 3)
                box.addItems(options)
                box.setCurrentText(str(values[col]))
                box.currentTextChanged.connect(lambda value, row=r, column=col: self.table.item(row, column).setText(value))
                self.table.setCellWidget(r, col, box)
        self.table.blockSignals(False)

    def _add(self, kind):
        label, ok = QInputDialog.getText(self, "添加数据项", "中文名称")
        if not ok or not label.strip():
            return
        used = {item["id"] for key in ("variables", "constants", "apis", "types") for item in self.data[key]}
        item_id = label.strip() if label.strip().isidentifier() and label.strip() not in used else make_id(label, "api" if kind == "api" else "value", used)
        scope = self.group.currentData() if self.group.currentData() in SCOPE_LABELS else "global"
        if kind == "variable":
            self.data["variables"].append({"id": item_id, "label": label.strip(), "type": "文本", "default": "", "scope": scope, "description": ""})
            self.select_group(scope)
        elif kind == "constant":
            self.data["constants"].append({"id": item_id, "label": label.strip(), "type": "文本", "value": "", "scope": "global", "description": ""})
            self.select_group("constants")
        elif kind == "type":
            self.data["types"].append({"id": item_id, "label": label.strip(), "members": [], "description": ""})
            self.select_group("types")
        else:
            self.data["apis"].append({"id": item_id, "label": label.strip(), "library": "", "entry": item_id, "return_type": "整数", "parameters": [], "calling_convention": "cdecl", "permissions": [], "dependencies": [], "description": ""})
            self.select_group("apis")
        self.load(self.data)
        self.changed.emit(copy.deepcopy(self.data))

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        if row < len(self.row_items):
            key, identity = self.row_items[row]
            item = next(item for item in self.data[key] if item["id"] == identity)
            self.data[key].remove(item)
            self.load(self.data)
            self.changed.emit(copy.deepcopy(self.data))

    def _changed(self, _item):
        rows = []
        for row in range(self.table.rowCount()):
            rows.append([self.table.item(row, col).text() if self.table.item(row, col) else "" for col in range(len(self.HEADERS))])
        candidate = copy.deepcopy(self.data)
        for index, (label, item_id, category, typ, value, scope, params, calling, grants, description, owner, static, array) in enumerate(rows):
            if not item_id:
                continue
            scope_id = next((key for key, text in SCOPE_LABELS.items() if text == scope), scope or "global")
            key, identity = self.row_items[index]
            item = next(item for item in candidate[key] if item["id"] == identity)
            item.update({"id": item_id, "label": label, "description": description})
            if category in {"变量", "常量"}:
                item.update({"type": typ, "value" if category == "常量" else "default": value, "scope": scope_id,
                             "owner": owner, "static": static == "True", "array": array})
            elif category == "数据类型":
                try:
                    item["members"] = json.loads(params or "[]")
                except json.JSONDecodeError:
                    self.hint.setText("成员数据不是有效 JSON；本次修改未保存。")
                    return
            elif category == "DLL/API":
                permissions, _, dependencies = grants.partition("/")
                try:
                    parameter_list = json.loads(params or "[]")
                except json.JSONDecodeError:
                    self.hint.setText("参数数据不是有效 JSON；本次修改未保存。")
                    return
                item.update({"return_type": typ, "library": value,
                             "parameters": parameter_list, "calling_convention": calling or "cdecl",
                             "permissions": [v.strip() for v in permissions.split(",") if v.strip()],
                             "dependencies": [v.strip() for v in dependencies.split(",") if v.strip()], "description": description})
        try:
            self.data = validate_data(candidate)
        except DataError as exc:
            self.hint.setText(f"本次修改未保存：{exc}")
            return
        self.hint.setText("已保存。引用代码名称；窗口/程序集使用 所属名称.代码名称。")
        self.changed.emit(copy.deepcopy(self.data))
