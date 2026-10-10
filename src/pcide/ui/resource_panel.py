from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class ResourcePanel(QWidget):
    import_requested = Signal()
    delete_requested = Signal(object)
    rename_requested = Signal(object)
    changed = Signal()

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索资源相对路径或文件类型')
        self.search.textChanged.connect(self.filter_rows)
        bar.addWidget(self.search, 1)
        for label, callback in (('导入文件', self.import_requested.emit), ('刷新', self.changed.emit),
                                ('复制相对路径', self.copy_path), ('重命名', self.rename_selected), ('删除', self.delete_selected)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        note = QLabel('外部文件导入后存放在工程 resources 目录；与资源统一管理。此页显示实际文件，不执行 DLL 或 EXE。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['工程相对路径', '文件类型', '大小（字节）'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.currentCellChanged.connect(lambda *_: self.preview_selected())
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_host = QWidget()
        preview_layout = QVBoxLayout(preview_host)
        preview_layout.addWidget(self.image)
        preview_layout.addWidget(self.preview, 1)
        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(preview_host)
        split.setSizes([600, 350])
        layout.addWidget(split, 1)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.set_project(project)

    def set_project(self, project):
        self.project = project
        base = (project.root / 'resources').resolve()
        root = project.root.resolve()
        self.paths = []
        pending = [base] if base.is_relative_to(root) and base.is_dir() else []
        while pending and len(self.paths) < 10000:
            folder = pending.pop()
            for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
                if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(base):
                    continue
                if path.is_dir():
                    pending.append(path)
                elif path.is_file():
                    self.paths.append(path)
                    if len(self.paths) == 10000:
                        break
        self.paths.sort(key=lambda p: p.relative_to(root).as_posix().casefold())
        self.table.setRowCount(len(self.paths))
        for row, path in enumerate(self.paths):
            values = (path.relative_to(root).as_posix(), path.suffix.lower() or '无扩展名', str(path.stat().st_size))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 120)
        self.preview.clear()
        self.image.clear()
        self.image.hide()
        self.filter_rows()
        self.status.setText(f'{len(self.paths)} 个实际文件' + ('；达到 10000 项显示上限' if len(self.paths) == 10000 else ''))

    def filter_rows(self, _text=None):
        query = self.search.text().strip().casefold()
        for row in range(self.table.rowCount()):
            values = [self.table.item(row, column) for column in (0, 1)]
            self.table.setRowHidden(row, bool(query) and not any(item and query in item.text().casefold() for item in values))

    def selected_path(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.paths):
            path = self.paths[row]
            if path.is_file() and path.resolve().is_relative_to((self.project.root / 'resources').resolve()):
                return path
        return None

    def copy_path(self):
        path = self.selected_path()
        if path:
            QApplication.clipboard().setText(path.relative_to(self.project.root).as_posix())

    def rename_selected(self):
        path = self.selected_path()
        if path:
            self.rename_requested.emit(path)

    def delete_selected(self):
        path = self.selected_path()
        if path:
            self.delete_requested.emit(path)

    def preview_selected(self):
        path = self.selected_path()
        self.image.clear()
        self.image.hide()
        if not path:
            self.preview.clear()
            return
        try:
            size = path.stat().st_size
            details = f'路径：{path.relative_to(self.project.root).as_posix()}\n大小：{size} 字节\n'
            if size <= 16 * 1024 * 1024:
                reader = QImageReader(str(path))
                dimensions = reader.size()
                if reader.canRead() and dimensions.width() * dimensions.height() <= 16000000:
                    pixmap = QPixmap.fromImage(reader.read())
                    if not pixmap.isNull():
                        self.image.setPixmap(pixmap.scaled(360, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        self.image.show()
                        details += f'图像：{dimensions.width()} × {dimensions.height()}\n'
            with path.open('rb') as handle:
                content = handle.read(65536)
            if b'\0' not in content:
                try:
                    text = content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    text = None
                if text is not None:
                    details += '\n' + text + ('\n（仅预览前 64 KiB）' if size > len(content) else '')
            self.preview.setPlainText(details)
        except OSError as exc:
            self.preview.setPlainText(str(exc))
