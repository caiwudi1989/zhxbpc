from __future__ import annotations

import copy
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QInputDialog, QMenu,
    QTableWidget, QTableWidgetItem, QLabel, QMessageBox, QToolButton, QVBoxLayout, QWidget,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QCheckBox)

from pcide.core.data import DataError, SCOPE_LABELS, TYPES, generate_code, reference_name, validate_data
from pcide.core.i18n import make_id
from pcide.core.libraries import TYPE_LABELS
from pcide.core.dll import SCALARS, validate_signature


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
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemChanged.connect(self._changed)
        self.table.itemDoubleClicked.connect(lambda item: self._edit_members() if item.column() == 6 else None)
        bar = QHBoxLayout()
        bar.addWidget(self.group)
        for text, kind in (("添加当前类别", "current"), ("复制", "copy"), ("编辑成员/参数", "members"), ("删除", "delete")):
            button = QToolButton(text=text)
            button.clicked.connect(lambda _, k=kind: self._delete() if k == "delete" else self._duplicate() if k == "copy" else self._edit_members() if k == "members" else self._add({'constants':'constant','types':'type','apis':'api'}.get(self.group.currentData(),'variable')))
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
        selection = self.group.currentData()
        visible = {0,1,3,4,9} | ({6} if selection=='types' else {6,7,8} if selection=='apis' else {5,10,12})
        if selection == 'types':
            visible = {0,1,6,9}
        if selection in {'local','module'}:
            visible.add(11)
        headers = list(self.HEADERS)
        headers[3] = '返回 ABI' if selection=='apis' else '数据类型'
        headers[4] = 'DLL 文件' if selection=='apis' else '常量值' if selection=='constants' else '初始值'
        headers[6] = '成员（双击编辑）' if selection=='types' else '参数（双击编辑）'
        self.table.setHorizontalHeaderLabels(headers)
        for column in range(len(headers)):
            self.table.setColumnHidden(column, column not in visible)
        self.table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
                if c == 2:
                    self.table.item(r, c).setFlags(self.table.item(r, c).flags() & ~Qt.ItemFlag.ItemIsEditable)
            options_type = sorted(SCALARS)+['void'] if selection=='apis' else list(TYPE_LABELS)+[item['id'] for item in self.data['types']]
            for col, options in ((3, options_type), (5, list(SCOPE_LABELS.values())), (11, ["否", "是"])):
                if values[2] in {"DLL/API", "数据类型"} and col in {5, 11}:
                    continue
                box = QComboBox()
                box.setEditable(col == 3)
                box.addItems(options)
                current = ('是' if values[col]=='True' else '否') if col==11 else str(values[col])
                if current not in options:
                    box.addItem(current)
                box.setCurrentText(current)
                self.table.item(r,col).setText(current)
                box.currentTextChanged.connect(lambda value, row=r, column=col: self.table.item(row, column).setText(value))
                self.table.setCellWidget(r, col, box)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        for column,width in ((0,120),(1,120),(3,150),(4,160),(5,100),(10,200),(12,100)):
            self.table.setColumnWidth(column,width)
        self.table.setColumnWidth(9,180)

    def _add(self, kind):
        dialog=QDialog(self)
        dialog.setWindowTitle({'variable':'添加变量','constant':'添加常量','type':'添加数据类型','api':'添加 DLL 命令'}[kind])
        layout=QVBoxLayout(dialog)
        form=QFormLayout()
        fields={}
        def line(label,name,text=''):
            field=QLineEdit(text)
            field.setObjectName(name)
            fields[name]=field
            form.addRow(label,field)
            return field
        line('中文名称','label')
        line('代码名称（留空自动生成）','id')
        typ=QComboBox()
        typ.setObjectName('type')
        typ.addItems(sorted(SCALARS)+['void'] if kind=='api' else ['文本型']+[v for v in TYPE_LABELS if v!='文本型']+[v['id'] for v in self.data['types']])
        scope=QComboBox()
        for value,label in SCOPE_LABELS.items():
            scope.addItem(label,value)
        scope.setCurrentIndex(max(0,scope.findData(self.group.currentData())))
        owner=QComboBox()
        owner.setEditable(True)
        owner.setObjectName('owner')
        def owners():
            previous=owner.currentText()
            choices=[]
            if scope.currentData()=='window':
                choices=[path.name.split('.')[0] for path in self.project.window_paths()]
            elif scope.currentData()=='module':
                from pcide.core.modules import load_modules
                choices=[item['id'] for item in load_modules(self.project)['modules']]
            elif scope.currentData()=='local':
                from pcide.core.routines import scan
                choices=[item['sourceName'] for path in self.project.scripts() if path.suffix!='.pyc' for item in scan(path.read_text(encoding='utf-8'),path.suffix)]
            owner.clear()
            owner.addItems(list(dict.fromkeys(choices)))
            if previous:
                owner.setCurrentText(previous)
            owner.setEnabled(scope.currentData()!='global')
        if kind!='type':
            form.addRow('返回 ABI' if kind=='api' else '数据类型',typ)
        if kind in {'variable','constant'}:
            line('常量值' if kind=='constant' else '初始值','value')
            form.addRow('作用域',scope)
            form.addRow('所属窗口/模块/子程序',owner)
            scope.currentIndexChanged.connect(owners)
            owners()
            array=line('数组维数（例：3,4）','array')
            array.setPlaceholderText('留空为普通值；最多 10000 个元素')
        static=QCheckBox('静态（局部变量保留值）')
        if kind=='variable':
            form.addRow(static)
        if kind=='api':
            line('项目内 DLL 相对路径','library','resources/libraries/')
            line('DLL 实际导出名','entry')
            convention=QComboBox()
            convention.addItems(['cdecl','stdcall','winapi'])
            form.addRow('调用约定',convention)
        line('备注','description')
        layout.addLayout(form)
        error=QLabel()
        error.setWordWrap(True)
        layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        layout.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        def save():
            try:
                used={item['id'] for key in ('variables','constants','apis','types') for item in self.data[key]}
                label=fields['label'].text().strip()
                if not label:
                    raise DataError('请填写名称')
                identity=fields['id'].text().strip() or (label if label.isidentifier() and label not in used else make_id(label,'value',used))
                item={'id':identity,'label':label,'description':fields['description'].text()}
                key={'variable':'variables','constant':'constants','type':'types','api':'apis'}[kind]
                if kind in {'variable','constant'}:
                    selected=scope.currentData()
                    if selected!='global' and not owner.currentText().strip().isidentifier():
                        raise DataError('所属范围必须是代码名称')
                    item.update(type=typ.currentText(),scope=selected,owner=owner.currentText().strip() if selected!='global' else '',array=fields['array'].text(),static=static.isChecked() if kind=='variable' else False)
                    item['value' if kind=='constant' else 'default']=fields['value'].text()
                elif kind=='type':
                    item['members']=[]
                else:
                    item.update(library=fields['library'].text(),entry=fields['entry'].text(),return_type=typ.currentText(),parameters=[],calling_convention=convention.currentText())
                    validate_signature(item['entry'],[],item['return_type'])
                candidate=copy.deepcopy(self.data)
                candidate[key].append(item)
                normalized=validate_data(candidate)
                self.select_group(item['scope'] if kind=='variable' else key)
                self.load(normalized)
                self.changed.emit(copy.deepcopy(self.data))
                dialog.accept()
            except (ValueError,OSError) as exc:
                error.setText(str(exc))
        buttons.accepted.connect(save)
        dialog.exec()

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

    def _context_menu(self, position):
        """Expose the same table operations from a right-click menu."""
        clicked = self.table.itemAt(position)
        if clicked is not None:
            self.table.selectRow(clicked.row())
        menu = QMenu(self)
        add = menu.addAction("添加当前类别")
        duplicate = menu.addAction("复制当前行")
        members = menu.addAction("编辑成员 / DLL 导出与参数")
        delete = menu.addAction("删除当前行")
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen == add:
            selected = self.group.currentData()
            self._add("constant" if selected == "constants" else
                      "type" if selected == "types" else
                      "api" if selected == "apis" else "variable")
        elif chosen == duplicate:
            self._duplicate()
        elif chosen == delete:
            self._delete()
        elif chosen == members:
            self._edit_members()

    def _edit_members(self):
        row = self.table.currentRow()
        if not 0 <= row < len(self.row_items):
            return
        key, identity = self.row_items[row]
        if key not in {"types", "apis"}:
            return
        item = next(value for value in self.data[key] if value["id"] == identity)
        dialog = QDialog(self)
        dialog.setWindowTitle("数据类型成员" if key == "types" else "DLL 导出和参数")
        dialog.resize(700, 420)
        layout = QVBoxLayout(dialog)
        entry = QLineEdit(item.get("entry", ""))
        if key == "apis":
            form = QFormLayout()
            form.addRow("DLL 实际导出名", entry)
            layout.addLayout(form)
            layout.addWidget(QLabel("仅开放明确宽度的标量返回和文本输入；指针、结构体、文本返回及输出参数尚未开放。"))
        members_key = "members" if key == "types" else "parameters"
        names = ('label','id','type','default','description','array') if key=='types' else ('label','id','type','default','description')
        fields = QTableWidget(0, len(names))
        fields.setHorizontalHeaderLabels(["名称", "代码名称", "类型", "初始值", "备注"] + (["数组维数"] if key=='types' else []))
        if key=='apis':
            fields.setColumnHidden(3,True)
        fields.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        fields.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        def add_member(member=None):
            member = member or {}
            current = fields.rowCount()
            fields.insertRow(current)
            for column, name in enumerate(names):
                fields.setItem(current, column, QTableWidgetItem(str(member.get(name, "文本型" if name == "type" else ""))))
            box = QComboBox()
            box.setEditable(True)
            box.addItems(sorted(SCALARS)+['utf8','utf16'] if key=='apis' else list(TYPE_LABELS)+[value['id'] for value in self.data['types']])
            box.setCurrentText(fields.item(current, 2).text())
            target_item = fields.item(current,2)
            box.currentTextChanged.connect(lambda text, target=target_item: target.setText(text))
            fields.setCellWidget(current, 2, box)
        for member in item[members_key]:
            add_member(member)
        bar = QHBoxLayout()
        add = QToolButton(text="添加成员" if key == "types" else "添加参数")
        add.clicked.connect(lambda: add_member())
        remove = QToolButton(text="删除")
        remove.clicked.connect(lambda: fields.removeRow(fields.currentRow()) if fields.currentRow() >= 0 else None)
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch()
        layout.addLayout(bar)
        layout.addWidget(fields)
        error = QLabel()
        error.setWordWrap(True)
        layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.rejected.connect(dialog.reject)
        def save():
            candidate = copy.deepcopy(self.data)
            target = next(value for value in candidate[key] if value["id"] == identity)
            target[members_key] = [{name: fields.item(row, column).text() if fields.item(row,column) else '' for column, name in enumerate(names)}
                                   for row in range(fields.rowCount())]
            if key == "apis":
                target["entry"] = entry.text().strip()
            try:
                if key=='apis':
                    validate_signature(target['entry'],[p['type'] for p in target['parameters']],target['return_type'])
                normalized = validate_data(candidate)
            except ValueError as exc:
                error.setText(str(exc))
                return
            self.load(normalized)
            self.changed.emit(copy.deepcopy(self.data))
            dialog.accept()
        buttons.accepted.connect(save)
        layout.addWidget(buttons)
        dialog.exec()

    def _duplicate(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.row_items):
            return
        key, identity = self.row_items[row]
        source = next((item for item in self.data.get(key, []) if item.get("id") == identity), None)
        if source is None:
            return
        used = {item["id"] for group in ("variables", "constants", "apis", "types") for item in self.data.get(group, [])}
        clone = copy.deepcopy(source)
        clone["id"] = make_id(str(clone.get("label") or identity) + "副本", "value", used)
        clone["label"] = str(clone.get("label") or identity) + "副本"
        self.data[key].append(clone)
        self.load(self.data)
        self.changed.emit(copy.deepcopy(self.data))

    def _changed(self, _item):
        rows = []
        for row in range(self.table.rowCount()):
            rows.append([self.table.item(row, col).text() if self.table.item(row, col) else "" for col in range(len(self.HEADERS))])
        candidate = copy.deepcopy(self.data)
        id_updates = []
        for index, (label, item_id, category, typ, value, scope, params, calling, grants, description, owner, static, array) in enumerate(rows):
            if not item_id:
                continue
            scope_id = next((key for key, text in SCOPE_LABELS.items() if text == scope), scope or "global")
            key, identity = self.row_items[index]
            item = next((value for value in candidate[key] if value["id"] == identity), None)
            if item is None:
                self.hint.setText("当前行已失效，请重新选择后再编辑。")
                return
            item.update({"id": item_id, "label": label, "description": description})
            id_updates.append((index, key, item_id))
            if category in {"变量", "常量"}:
                item.update({"type": typ, "value" if category == "常量" else "default": value, "scope": scope_id,
                             "owner": owner, "static": static in {"True", "是"}, "array": array})
            elif category == "数据类型":
                try:
                    item["members"] = json.loads(params or "[]")
                except json.JSONDecodeError:
                    self.load(self.data)
                    self.hint.setText("成员数据不是有效 JSON；本次修改未保存。")
                    return
            elif category == "DLL/API":
                permissions, _, dependencies = grants.partition("/")
                try:
                    parameter_list = json.loads(params or "[]")
                except json.JSONDecodeError:
                    self.load(self.data)
                    self.hint.setText("参数数据不是有效 JSON；本次修改未保存。")
                    return
                item.update({"return_type": typ, "library": value,
                             "parameters": parameter_list, "calling_convention": calling or "cdecl",
                             "permissions": [v.strip() for v in permissions.split(",") if v.strip()],
                             "dependencies": [v.strip() for v in dependencies.split(",") if v.strip()], "description": description})
        try:
            self.data = validate_data(candidate)
        except DataError as exc:
            self.load(self.data)
            self.hint.setText(f"本次修改未保存：{exc}")
            return
        for index, key, item_id in id_updates:
            self.row_items[index] = (key, item_id)
        self.hint.setText("已保存。引用代码名称；窗口/程序集使用 所属名称.代码名称。")
        self.changed.emit(copy.deepcopy(self.data))
        if any(not self._visible(key, next(value for value in self.data[key] if value["id"] == item_id)) for _, key, item_id in id_updates):
            self.load(self.data)
