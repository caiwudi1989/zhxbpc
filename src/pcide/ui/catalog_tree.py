from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import QTreeWidget

class LibraryTree(QTreeWidget):
    """One catalog item becomes a plain text code drag in both editor backends."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def mimeData(self, items):
        data = QMimeData()
        if items:
            code = items[0].data(0, Qt.ItemDataRole.UserRole)
            if code:
                data.setText(str(code))
        return data

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction
