"""Native editable procedure table, backed by the same source/metadata model."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
                              QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget, QSizePolicy)

from pcide.core.routines import RETURN_TYPES, find_metadata
from .routine_ranges import scan_editor as scan


class RoutinePanel(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.editor = editor
        self.value = None
        self.routines = []
        self.loading = False
        self.collapsed = set()
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self.select)
        self.toggle = QToolButton(text="▾")
        self.toggle.clicked.connect(self.collapse)
        top = QHBoxLayout()
        top.addWidget(self.toggle)
        top.addWidget(QLabel("子程序"))
        top.addWidget(self.selector, 1)
        self.content = QWidget()
        fields = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("子程序名称")
        self.name.editingFinished.connect(self.publish)
        self.return_type = QComboBox()
        for value in RETURN_TYPES:
            self.return_type.addItem(value or "无返回值", value)
        self.return_type.currentIndexChanged.connect(self.publish)
        self.public = QCheckBox("公开")
        self.public.stateChanged.connect(self.publish)
        self.public.setStyleSheet("QCheckBox{color:#d52222}")
        self.remark = QLineEdit()
        self.remark.setPlaceholderText("备注（注释）")
        self.remark.editingFinished.connect(self.publish)
        for label, widget in (("名称", self.name), ("返回值", self.return_type), ("", self.public), ("备注", self.remark)):
            if label:
                fields.addWidget(QLabel(label))
            fields.addWidget(widget)
        self.locals = QTableWidget(0, 4)
        self.locals.setHorizontalHeaderLabels(["局部变量名", "类型", "初始值", "备注（注释）"])
        self.locals.horizontalHeader().setStretchLastSection(True)
        self.locals.itemChanged.connect(self.publish)
        actions = QHBoxLayout()
        parameters = QToolButton(text='编辑参数')
        parameters.clicked.connect(lambda: self.editor.parameters_requested.emit(self.editor.path,self.value['line']) if self.value else None)
        actions.addWidget(parameters)
        for label, callback in (("添加局部变量", self.add_local), ("删除局部变量", self.delete_local)):
            button = QToolButton(text=label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(fields)
        self.parameters=QTableWidget(0,4)
        self.parameters.setHorizontalHeaderLabels(['参数名（调用方传入）','类型','默认值','可省略'])
        self.parameters.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.parameters.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.parameters)
        self.declared_locals=QTableWidget(0,4)
        self.declared_locals.setHorizontalHeaderLabels(['源码局部变量','类型','初始值','备注（源视图编辑）'])
        self.declared_locals.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.declared_locals)
        self.scope_hint=QLabel('参数由调用方传入；局部变量在本子程序内部初始化。')
        layout.addWidget(self.scope_hint)
        layout.addWidget(self.locals)
        layout.addLayout(actions)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(3)
        outer.addLayout(top)
        outer.addWidget(self.content)

    def refresh(self):
        path = self.editor.path
        self.routines = scan(self.editor.documents.get(path, ""), Path(path).suffix) if path else []
        selected = self.value.get("sourceName") if self.value else None
        signature = json.dumps([path, self.editor.custom_types, self.editor.startup_routines,
                                [(routine['sourceName'], self.metadata(routine)) for routine in self.routines], self.editor.display_routine_metadata(path) if path else {}],
                               ensure_ascii=False, sort_keys=True)
        if signature == getattr(self, '_render_signature', None):
            with QSignalBlocker(self.selector):
                for index, routine in enumerate(self.routines):
                    label = self.selector.itemText(index).split('  子程序 ', 1)[-1]
                    self.selector.setItemText(index, f"{routine['line']}  子程序 {label}")
                    if self.value and routine['sourceName'] == selected:
                        self.value['line'] = routine['line']
            return
        self._render_signature = signature
        with QSignalBlocker(self.selector):
            self.selector.clear()
            for routine in self.routines:
                stored = self.metadata(routine)
                title = stored.get("name") or ("_启动程序" if routine["sourceName"] in self.editor.startup_routines else routine["sourceName"])
                self.selector.addItem(f"{routine['line']}  子程序 {title}", routine["sourceName"])
            self.selector.setCurrentIndex(max(0, self.selector.findData(selected)))
        self.setVisible(bool(self.routines))
        self.select(self.selector.currentIndex())

    def metadata(self, routine):
        normalized = self.editor.path.replace("\\", "/")
        index = self.editor.routine_metadata_index
        file = next((value["file"] for value in index.values() if isinstance(value, dict) and value.get("file") and normalized.endswith("/" + value["file"])), "")
        return find_metadata(index, file, routine["sourceName"], routine["line"]) if file else {}

    def select(self, index):
        if not 0 <= index < len(self.routines):
            self.value = None
            return
        routine = self.routines[index]
        value = copy.deepcopy(self.metadata(routine))
        startup = routine["sourceName"] in self.editor.startup_routines
        value.update(line=routine["line"], sourceName=routine["sourceName"], startup=startup)
        value.setdefault("name", "_启动程序" if startup else routine["sourceName"])
        value.setdefault("locals", [])
        self.value = value
        self.loading = True
        self.name.setText(value["name"])
        self.return_type.clear()
        for typ in RETURN_TYPES + self.editor.custom_types:
            self.return_type.addItem(typ or '无返回值', typ)
        self.return_type.setCurrentIndex(max(0, self.return_type.findData(value.get("returnType", ""))))
        self.public.setChecked(value.get("public", False))
        self.public.setText("公开")
        self.remark.setText(value.get("remark", ""))
        from pcide.core.routine_signatures import parameter_details
        try:
            params=parameter_details(self.editor.documents[self.editor.path],Path(self.editor.path).suffix,routine['sourceName'])
        except (ValueError,SyntaxError,StopIteration):
            params=[]
        self.parameters.setRowCount(len(params))
        for row,param in enumerate(params):
            for col,text in enumerate([param['name'],param['type'] or '自动',param['default'],'是' if param['optional'] else '否']):
                self.parameters.setItem(row,col,QTableWidgetItem(text))
        self.parameters.setVisible(bool(params))
        if params:
            self.parameters.setFixedHeight(self.parameters.horizontalHeader().height()+sum(self.parameters.rowHeight(row) for row in range(min(len(params),4)))+4)
        locals_source=[]
        if Path(self.editor.path).suffix=='.zhxb':
            try:
                from pcide.core.compiler import parse
                locals_source=next(p.locals for p in parse(self.editor.documents[self.editor.path]).procedures if p.name==routine['sourceName'])
            except (ValueError,StopIteration):
                pass
        self.declared_locals.setRowCount(len(locals_source))
        for row,local in enumerate(locals_source):
            for col,key in enumerate(['name','type','default','remark']):
                self.declared_locals.setItem(row,col,QTableWidgetItem(local.get(key,'')))
        self.declared_locals.setVisible(bool(locals_source))
        if locals_source:
            self.declared_locals.setFixedHeight(self.declared_locals.horizontalHeader().height()+sum(self.declared_locals.rowHeight(row) for row in range(min(len(locals_source),4)))+4)
        self.locals.setRowCount(len(value["locals"]))
        for row, local in enumerate(value["locals"]):
            for column, key in enumerate(("name", "type", "defaultValue", "remark")):
                self.locals.setItem(row, column, QTableWidgetItem(str(local.get(key, ""))))
            box = QComboBox()
            box.addItems(RETURN_TYPES[1:] + self.editor.custom_types)
            box.setCurrentText(local.get("type", "文本型"))
            target=self.locals.item(row,1)
            box.currentTextChanged.connect(lambda text,cell=target:cell.setText(text))
            self.locals.setCellWidget(row, 1, box)
        self.loading = False
        self._fit_locals()
        self.content.setVisible(self.collapse_key(routine['sourceName']) not in self.collapsed)
        self.toggle.setText('▸' if self.collapse_key(routine['sourceName']) in self.collapsed else '▾')
        if self.editor.path:
            self.editor._apply_native_visibility()

    def publish(self, *_):
        if self.loading or not self.value or not self.name.text().isidentifier():
            return
        value = copy.deepcopy(self.value)
        value.update(name=self.name.text(), returnType=self.return_type.currentData(), public=self.public.isChecked(), remark=self.remark.text())
        value["locals"] = [{key: self.locals.item(row, column).text() if self.locals.item(row, column) else ""
                            for column, key in enumerate(("name", "type", "defaultValue", "remark"))}
                           for row in range(self.locals.rowCount()) if self.locals.item(row, 0) and self.locals.item(row, 0).text().strip()]
        self.value = value
        self.public.setText("公开")
        self.editor.routine_metadata.emit(self.editor.path, json.dumps(value, ensure_ascii=False))
        self.selector.setItemText(self.selector.currentIndex(), f"{value['line']}  子程序 {value['name']}")

    def add_local(self):
        if self.value is None:
            return
        self.value["locals"].append({"name": "", "type": "文本型", "defaultValue": "", "remark": ""})
        # Render this unsaved row without reloading metadata from disk.
        self.loading = True
        row = self.locals.rowCount()
        self.locals.insertRow(row)
        for column, text in enumerate(("", "文本型", "", "")):
            self.locals.setItem(row, column, QTableWidgetItem(text))
        box = QComboBox()
        box.addItems(RETURN_TYPES[1:] + self.editor.custom_types)
        box.setCurrentText("文本型")
        target=self.locals.item(row,1)
        box.currentTextChanged.connect(lambda text,cell=target:cell.setText(text))
        self.locals.setCellWidget(row, 1, box)
        self.loading = False
        self._fit_locals()
        self.locals.setCurrentCell(row, 0)
        self.locals.editItem(self.locals.item(row, 0))

    def delete_local(self):
        row = self.locals.currentRow()
        if row >= 0:
            self.locals.removeRow(row)
            self._fit_locals()
            self.publish()

    def _fit_locals(self):
        rows = self.locals.rowCount()
        self.locals.setVisible(rows > 0)
        if rows:
            self.locals.setFixedHeight(self.locals.horizontalHeader().height()
                                       + sum(self.locals.rowHeight(row) for row in range(min(rows, 5))) + 4)

    def collapse_key(self, name):
        return (self.editor.path, name)

    def collapse(self):
        if self.value is None:
            return
        name = self.collapse_key(self.value['sourceName'])
        if name in self.collapsed:
            self.collapsed.remove(name)
        else:
            self.collapsed.add(name)
        self.content.setVisible(name not in self.collapsed)
        self.toggle.setText('▸' if name in self.collapsed else '▾')
        self.editor._apply_native_visibility()
