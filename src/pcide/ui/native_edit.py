"""Source-preserving native editor with line numbers and hidden declarations."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QTextCursor, QTextDocument
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#eef2ef"))
        painter.setPen(QColor("#697970"))
        block = self.editor.firstVisibleBlock()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = int(self.editor.blockBoundingRect(block).height())
            if block.isVisible():
                painter.drawText(0, top, self.width()-6, self.editor.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber()+1))
            top += height
            block = block.next()


class NativeEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(self.update_gutter)
        self.updateRequest.connect(lambda rect, dy: self.gutter.scroll(0, dy) if dy else self.gutter.update(0, rect.y(), self.gutter.width(), rect.height()))
        self.update_gutter()

    def update_gutter(self, *_):
        width = 14 + self.fontMetrics().horizontalAdvance("9") * max(2, len(str(self.blockCount())))
        self.setViewportMargins(width, 0, 0, 0)
        self.gutter.setGeometry(0, 0, width, self.contentsRect().height())
        self.gutter.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_gutter()

    def mousePressEvent(self, event):
        self.parent()._ensure_native_editable()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.parent()._accept_native_completion(event):
            return
        modifiers = event.modifiers()
        plain = not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
        edit = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Tab)
        paste = bool(modifiers & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V
        if plain and (event.text() or edit) or paste:
            self.parent()._ensure_native_editable()
        super().keyPressEvent(event)

    def inputMethodEvent(self, event):
        if event.preeditString():
            self.parent()._fallback_ime_composing = True
        if event.commitString() or event.preeditString():
            self.parent()._ensure_native_editable()
        super().inputMethodEvent(event)
        if event.commitString():
            self.parent()._fallback_ime_composing = False
            # The commit is applied by Qt after this event returns.  Refresh
            # the popup on the next turn so Chinese text can immediately
            # filter the same system-function list as ASCII input.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.parent()._refresh_native_completion)

    def hide_lines(self, hidden):
        changed = False
        block = self.document().begin()
        while block.isValid():
            visible = block.blockNumber()+1 not in hidden
            if block.isVisible() != visible:
                changed = True
                block.setVisible(visible)
                block.setLineCount(1 if visible else 0)
            block = block.next()
        if not changed:
            return
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()
        self.gutter.update()


class FindDialog(QDialog):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.query = QLineEdit()
        self.replacement = QLineEdit()
        self.replace_label = QLabel('替换为')
        self.message = QLabel()
        fields = QFormLayout()
        fields.addRow('查找', self.query)
        fields.addRow(self.replace_label, self.replacement)
        actions = QHBoxLayout()
        self.replace_buttons = []
        for title, callback, replace in [('上一个', lambda: self.find(True), False), ('下一个', self.find, False), ('替换当前', self.replace_current, True), ('全部替换', self.replace_all, True)]:
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, action=callback: action())
            actions.addWidget(button)
            if replace:
                self.replace_buttons.append(button)
        self.query.returnPressed.connect(self.find)
        layout = QVBoxLayout(self)
        layout.addLayout(fields)
        layout.addLayout(actions)
        layout.addWidget(self.message)

    def open_find(self, replace):
        self.setWindowTitle('查找替换' if replace else '查找')
        self.replacement.setVisible(replace)
        self.replace_label.setVisible(replace)
        for button in self.replace_buttons:
            button.setVisible(replace)
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()

    def reject(self):
        super().reject()
        self.editor.window().activateWindow()
        self.editor.focus_editor()

    def find(self, backward=False):
        if not self.query.text():
            return
        view = self.editor.view
        flags = QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if not view.find(self.query.text(), flags):
            previous = view.textCursor()
            cursor = view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start)
            view.setTextCursor(cursor)
            if not view.find(self.query.text(), flags):
                view.setTextCursor(previous)
                self.message.setText('未找到匹配内容')
                return
        self.message.setText('已定位匹配内容（区分大小写）')
        match = view.textCursor()
        self.editor._fallback_goto(match.blockNumber() + 1)
        view.setTextCursor(match)
        view.ensureCursorVisible()
        self.query.setFocus()

    def replace_current(self):
        self.editor._ensure_native_editable()
        cursor = self.editor.view.textCursor()
        if cursor.selectedText() == self.query.text() and self.query.text():
            cursor.insertText(self.replacement.text())
            self.editor.view.setTextCursor(cursor)
        self.find()

    def replace_all(self):
        query = self.query.text()
        if not query:
            return
        self.editor._ensure_native_editable()
        view = self.editor.view
        source = view.toPlainText()
        count = source.count(query)
        if count:
            cursor = view.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(source.replace(query, self.replacement.text()))
            cursor.endEditBlock()
            view.setTextCursor(cursor)
        self.message.setText(f'已替换 {count} 处')
