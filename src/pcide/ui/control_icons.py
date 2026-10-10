"""Small code-native control glyphs; each toolbox kind has its own symbol."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

SYMBOLS = {"Button": "OK", "Label": "A", "Entry": "I_", "Text": "≡", "CheckBox": "✓",
           "RadioButton": "●", "ComboBox": "⌄", "ListBox": "☷", "Tree": "⊢", "Table": "▦",
           "ProgressBar": "▰", "Slider": "—●", "SpinBox": "↕", "DateTime": "12", "Frame": "□",
           "Tabs": "▤", "Canvas": "✎", "Image": "▧", "RichText": "B", "WebView": "@",
           "MenuBar": "☰", "ToolBar": "⚒", "StatusBar": "…", "Calendar": "31", "Splitter": "║",
           "ScrollArea": "↔", "Timer": "◷"}


def control_icon(kind):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#537363"), 1))
    painter.setBrush(QColor("#edf4ef"))
    painter.drawRoundedRect(1, 1, 22, 22, 3, 3)
    painter.setPen(QColor("#254536"))
    painter.setFont(QFont("Segoe UI Symbol", 10, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, SYMBOLS[kind])
    painter.end()
    return QIcon(pixmap)
