from __future__ import annotations

import json

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout

from pcide.core.modules import load_modules, validate_modules
from pcide.core.paths import atomic_write_json


class ModuleDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模块引用表")
        self.resize(850, 440)
        self.project = project
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("源码模块在 src 中开发；声明公开接口后用 模块名.函数 调用。修改后下次运行/构建会加载新版本。"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["模块名", "版本", "源码相对路径", "公开接口（逗号分隔）", "依赖（名称=版本）"])
        for column, width in enumerate((130, 80, 220, 190, 180)):
            self.table.setColumnWidth(column, width)
        modules=load_modules(project)['modules']
        self.known_modules={item['id'] for item in modules}
        for item in modules:
            self.add([item["id"], item["version"], item["file"], ",".join(item["exports"]), ",".join(name+"="+version for name, version in item["dependencies"].items())])
        bar = QHBoxLayout()
        for label, callback in (("加入文件/支持库", self.import_file), ("添加引用", lambda: self.add()), ("删除引用", lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= 0 else None)):
            button = QToolButton(text=label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        layout.addWidget(self.table)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def import_file(self):
        from pcide.ui.library_dialog import LibraryDialog
        dialog=LibraryDialog(self.project,self,page=1)
        def refresh():
            existing={self.table.item(row,0).text().strip() for row in range(self.table.rowCount()) if self.table.item(row,0)}
            for item in load_modules(self.project)['modules']:
                if item['id'] not in self.known_modules and item['id'] not in existing:
                    self.add([item['id'],item['version'],item['file'],','.join(item['exports']),','.join(name+'='+version for name,version in item['dependencies'].items())])
                self.known_modules.add(item['id'])
        dialog.changed.connect(refresh)
        dialog.exec()

    def add(self, values=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, text in enumerate(values or ["", "1.0.0", "src/", "", ""]):
            self.table.setItem(row, column, QTableWidgetItem(text))

    def save(self):
        try:
            modules = []
            for row in range(self.table.rowCount()):
                identity, version, file, exports, dependencies = [self.table.item(row, column).text().strip() for column in range(5)]
                pairs = [value.strip().split("=", 1) for value in dependencies.split(",") if value.strip()]
                if any(len(pair) != 2 for pair in pairs) or len({pair[0] for pair in pairs}) != len(pairs):
                    raise ValueError("依赖格式为 名称=版本，名称不得重复")
                modules.append({"id": identity, "version": version, "file": file,
                                "exports": [name.strip() for name in exports.split(",") if name.strip()], "dependencies": dict(pairs)})
            model = validate_modules({"version": 1, "modules": modules}, self.project.root)
            atomic_write_json(self.project.ide_dir / "modules.json", model)
            self.accept()
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))
