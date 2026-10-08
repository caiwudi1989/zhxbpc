from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QDateTime, QEvent, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCalendarWidget, QCheckBox, QComboBox, QDateTimeEdit, QFrame, QGroupBox, QLabel, QLineEdit, QListWidget,
    QMenuBar, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QSplitter, QStatusBar,
    QTabWidget, QTableWidget, QTextBrowser, QTextEdit, QToolBar, QTreeWidget, QTreeWidgetItem, QWidget)

from pcide.core.project import validate_form


class Canvas(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f7fafc"))
        painter.setPen(QColor("#2a826b"))
        painter.drawLine(10, self.height() - 15, self.width() // 2, 20)
        painter.drawLine(self.width() // 2, 20, self.width() - 10, self.height() // 2)


def create_control(kind, parent, props):
    text = str(props.get("text", ""))
    items = props.get("items", [text])
    if isinstance(items, str):
        items = [value.strip() for value in items.split("|") if value.strip()]
    if kind == "Button":
        widget = QPushButton(text, parent)
    elif kind == "Label":
        widget = QLabel(text, parent)
    elif kind == "Entry":
        widget = QLineEdit(text, parent)
    elif kind == "Text":
        widget = QTextEdit(parent)
        widget.setPlainText(text)
    elif kind in {"CheckBox", "RadioButton"}:
        widget = (QCheckBox if kind == "CheckBox" else QRadioButton)(text, parent)
        widget.setChecked(bool(props.get("checked", False)))
    elif kind == "ComboBox":
        widget = QComboBox(parent)
        widget.addItems([str(v) for v in items])
    elif kind == "ListBox":
        widget = QListWidget(parent)
        widget.addItems([str(v) for v in items])
    elif kind == "Tree":
        widget = QTreeWidget(parent)
        widget.setHeaderLabel(text)
        for label in items or ["Item"]:
            QTreeWidgetItem(widget, [str(label)])
    elif kind == "Table":
        widget = QTableWidget(3, 2, parent)
    elif kind == "ProgressBar":
        widget = QProgressBar(parent)
        widget.setValue(int(props.get("value", 50)))
    elif kind == "Slider":
        widget = QSlider(Qt.Orientation.Horizontal, parent)
        widget.setValue(int(props.get("value", 50)))
    elif kind == "SpinBox":
        widget = QSpinBox(parent)
        widget.setRange(0, 10000)
        widget.setValue(int(props.get("value", 0)))
    elif kind == "DateTime":
        widget = QDateTimeEdit(QDateTime.currentDateTime(), parent)
    elif kind == "Tabs":
        widget = QTabWidget(parent)
        names = [name.strip() for name in str(props.get("tab_names", text or "第一页")).split("|") if name.strip()]
        for name in names or ["第一页"]:
            widget.addTab(QWidget(widget), name)
        widget.setCurrentIndex(max(0, min(int(props.get("current_tab", 0)), widget.count() - 1)))
    elif kind == "Frame":
        widget = QGroupBox(text or "分组框", parent)
    elif kind == "Canvas":
        widget = Canvas(parent)
    elif kind == "Image":
        widget = QLabel(text or "图片", parent)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setFrameShape(QFrame.Shape.StyledPanel)
    elif kind == "RichText":
        widget = QTextBrowser(parent)
        widget.setHtml(text)
    elif kind == "WebView":
        widget = QTextBrowser(parent)
        widget.setPlainText(text or "网页视图")
    elif kind == "MenuBar":
        widget = QMenuBar(parent)
        widget.addMenu(text or "菜单")
    elif kind == "ToolBar":
        widget = QToolBar(text or "工具栏", parent)
    elif kind == "StatusBar":
        widget = QStatusBar(parent)
        widget.showMessage(text or "就绪")
    elif kind == "Calendar":
        widget = QCalendarWidget(parent)
    elif kind == "Splitter":
        widget = QSplitter(Qt.Orientation.Horizontal, parent)
        widget.addWidget(QFrame(widget))
        widget.addWidget(QFrame(widget))
    elif kind == "ScrollArea":
        widget = QScrollArea(parent)
        content = QLabel(text or "滚动内容")
        content.setMinimumSize(260, 180)
        widget.setWidget(content)
        widget.setWidgetResizable(True)
    elif kind == "Timer":
        widget = QLabel(text or "定时器", parent)
        widget.setFrameShape(QFrame.Shape.StyledPanel)
    else:
        widget = QFrame(parent)
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
    return widget


class RuntimeForm(QWidget):
    event = Signal(str, dict)
    closed = Signal()

    def __init__(self, form, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.form = validate_form(form)
        metadata = form["form"]
        window = metadata.get("window", {})
        flags = (Qt.WindowType.Window | Qt.WindowType.WindowTitleHint |
                 Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        if window.get("minimize", True):
            flags |= Qt.WindowType.WindowMinimizeButtonHint
        if window.get("maximize", True):
            flags |= Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle(metadata["title"])
        self.resize(metadata["width"], metadata["height"])
        self.window_id = metadata.get("id", metadata.get("title", "MainForm"))
        if not window.get("resizable", True):
            self.setFixedSize(metadata["width"], metadata["height"])
        else:
            fixed_width, fixed_height = window.get("fixed_width"), window.get("fixed_height")
            min_width = fixed_width or window.get("min_width", 100)
            min_height = fixed_height or window.get("min_height", 100)
            max_width = fixed_width or window.get("max_width", 10000)
            max_height = fixed_height or window.get("max_height", 10000)
            self.setMinimumSize(min_width, min_height)
            self.setMaximumSize(max_width, max_height)
            self.resize(fixed_width or metadata["width"], fixed_height or metadata["height"])
        self._apply_anchor(window)
        self.setStyleSheet(f"RuntimeForm {{background:{metadata.get('background', '#fff')};}}")
        self.widgets = {}
        self.event_data = {}
        remaining = list(form["controls"])
        while remaining:
            ready = [c for c in remaining if not c["parent"] or c["parent"] in self.widgets]
            for data in ready:
                control_parent = self.widgets.get(data["parent"], self)
                widget = create_control(data["type"], control_parent, data["properties"])
                widget.setObjectName(data["name"])
                widget.setGeometry(data["x"], data["y"], data["width"], data["height"])
                self.widgets[data["id"]] = widget
                self.update_control(data["id"], data["properties"])
                self._connect_events(widget, data)
                self.event_data[widget] = data
                widget.installEventFilter(self)
                remaining.remove(data)

    def _apply_anchor(self, window):
        anchor = window.get("anchor", "center")
        screen = self.screen().availableGeometry() if self.screen() else None
        if not screen:
            return
        margin = 12
        dock = window.get("dock", "none")
        if dock == "fill":
            self.setGeometry(screen)
            return
        if dock in {"left", "right"}:
            self.resize(self.width(), screen.height() - 2 * margin)
            self.move(screen.left() + margin if dock == "left" else screen.right() - self.width() - margin, screen.top() + margin)
            return
        if dock in {"top", "bottom"}:
            self.resize(screen.width() - 2 * margin, self.height())
            self.move(screen.left() + margin, screen.top() + margin if dock == "top" else screen.bottom() - self.height() - margin)
            return
        if anchor == "center":
            return
        x = screen.left() + margin if "left" in anchor else screen.right() - self.width() - margin if "right" in anchor else screen.center().x() - self.width() // 2
        y = screen.top() + margin if "top" in anchor else screen.bottom() - self.height() - margin if "bottom" in anchor else screen.center().y() - self.height() // 2
        self.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        metadata = self.form["form"]
        window = metadata.get("window", {})
        for data in self.form["controls"]:
            if data["id"] not in self.widgets:
                continue
            props = data["properties"]
            if props.get("auto_fill") or (window.get("auto_fill") and not data["parent"]):
                self.widgets[data["id"]].setGeometry(0, 0, self.width(), self.height())
                continue
            anchor = props.get("anchor", "")
            if not anchor:
                continue
            width, height = data["width"], data["height"]
            x, y = data["x"], data["y"]
            if "right" in anchor:
                x = self.width() - width - data["x"]
            elif "center" in anchor:
                x = (self.width() - width) // 2
            if "bottom" in anchor:
                y = self.height() - height - data["y"]
            elif anchor == "center":
                y = (self.height() - height) // 2
            self.widgets[data["id"]].setGeometry(x, y, width, height)
        handler = metadata.get("events", {}).get("resize")
        if handler and hasattr(self, "event_data"):
            self.event.emit(handler, {"id": self.window_id, "event": "resize",
                                       "width": self.width(), "height": self.height()})

    def _connect_events(self, widget, data):
        events = data["events"]
        if events.get("click") and hasattr(widget, "clicked"):
            widget.clicked.connect(lambda *_, d=data: self.event.emit(d["events"]["click"], {"id": d["id"], "event": "click"}))
        elif events.get("click"):
            signal = next((getattr(widget, name, None) for name in ("itemClicked", "activated")
                           if getattr(widget, name, None) is not None), None)
            if signal:
                signal.connect(lambda *_, d=data: self.event.emit(d["events"]["click"], {"id": d["id"], "event": "click"}))
        if events.get("change"):
            signal = next((getattr(widget, name, None) for name in
                           ("textChanged", "valueChanged", "currentIndexChanged", "currentRowChanged", "currentChanged",
                            "itemSelectionChanged", "toggled", "stateChanged") if getattr(widget, name, None) is not None), None)
            if signal:
                signal.connect(lambda *values, d=data: self.event.emit(d["events"]["change"], {"id": d["id"], "event": "change", "value": str(values[0]) if values else ""}))

    def load_event(self):
        handler = self.form["form"].get("events", {}).get("load")
        if handler:
            self.event.emit(handler, {"id": self.window_id, "event": "load"})
        for data in self.form["controls"]:
            if data["events"].get("load"):
                self.event.emit(data["events"]["load"], {"id": data["id"], "event": "load"})

    def eventFilter(self, widget, event):
        data = self.event_data.get(widget)
        if data:
            kind = {QEvent.Type.MouseButtonDblClick: "double_click", QEvent.Type.MouseButtonPress: "mouse_down",
                    QEvent.Type.KeyPress: "key_down", QEvent.Type.Resize: "resize"}.get(event.type())
            if event.type() == QEvent.Type.MouseButtonRelease and not hasattr(widget, "clicked"):
                kind = "click"
            handler = data["events"].get(kind)
            if handler:
                payload = {"id": data["id"], "event": kind}
                if kind == "key_down":
                    payload.update(key=event.key(), text=event.text())
                elif kind == "resize":
                    payload.update(width=widget.width(), height=widget.height())
                else:
                    payload.update(x=event.position().x(), y=event.position().y(), button=event.button().value)
                self.event.emit(handler, payload)
        return super().eventFilter(widget, event)

    def update_control(self, control_id, properties):
        if control_id not in self.widgets:
            raise ValueError(f"unknown UI control: {control_id}")
        widget = self.widgets[control_id]
        widget.blockSignals(True)
        try:
            if "text" in properties:
                method = getattr(widget, "setText", None) or getattr(widget, "setPlainText", None)
                if method:
                    method(str(properties["text"]))
            if "enabled" in properties:
                widget.setEnabled(bool(properties["enabled"]))
            if "visible" in properties:
                widget.setVisible(bool(properties["visible"]))
            if "tooltip" in properties:
                widget.setToolTip(str(properties["tooltip"]))
            if "placeholder" in properties and hasattr(widget, "setPlaceholderText"):
                widget.setPlaceholderText(str(properties["placeholder"]))
            if "read_only" in properties and hasattr(widget, "setReadOnly"):
                widget.setReadOnly(bool(properties["read_only"]))
            if "checked" in properties and hasattr(widget, "setChecked"):
                widget.setChecked(bool(properties["checked"]))
            for key, setter in (("minimum", "setMinimum"), ("maximum", "setMaximum"), ("step", "setSingleStep"),
                                ("value", "setValue")):
                if key in properties and hasattr(widget, setter):
                    getattr(widget, setter)(int(properties[key]))
            if "orientation" in properties and hasattr(widget, "setOrientation"):
                orientation = Qt.Orientation.Vertical if properties["orientation"] == "vertical" else Qt.Orientation.Horizontal
                widget.setOrientation(orientation)
            if "alignment" in properties and hasattr(widget, "setAlignment"):
                alignment = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                             "right": Qt.AlignmentFlag.AlignRight}.get(properties["alignment"], Qt.AlignmentFlag.AlignLeft)
                widget.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
            if "word_wrap" in properties and hasattr(widget, "setWordWrap"):
                widget.setWordWrap(bool(properties["word_wrap"]))
            if "editable" in properties and isinstance(widget, QComboBox):
                widget.setEditable(bool(properties["editable"]))
            if "tab_position" in properties and isinstance(widget, QTabWidget):
                position = {"top": QTabWidget.TabPosition.North, "bottom": QTabWidget.TabPosition.South,
                            "left": QTabWidget.TabPosition.West, "right": QTabWidget.TabPosition.East}.get(
                                properties["tab_position"], QTabWidget.TabPosition.North)
                widget.setTabPosition(position)
            if "tab_closable" in properties and isinstance(widget, QTabWidget):
                widget.setTabsClosable(bool(properties["tab_closable"]))
            if "scaled_contents" in properties and isinstance(widget, QLabel):
                widget.setScaledContents(bool(properties["scaled_contents"]))
            if "prefix" in properties and isinstance(widget, QSpinBox):
                widget.setPrefix(str(properties["prefix"]))
            if "suffix" in properties and isinstance(widget, QSpinBox):
                widget.setSuffix(str(properties["suffix"]))
            if "items" in properties:
                items = properties["items"]
                if isinstance(items, str):
                    items = [part.strip() for part in items.split("|") if part.strip()]
                items = [str(item) for item in items]
                if isinstance(widget, QComboBox):
                    current = widget.currentIndex()
                    widget.clear()
                    widget.addItems(items)
                    if items:
                        widget.setCurrentIndex(max(0, min(current, len(items) - 1)))
                elif isinstance(widget, QListWidget):
                    widget.clear()
                    widget.addItems(items)
                elif isinstance(widget, QTreeWidget):
                    widget.clear()
                    for item in items:
                        QTreeWidgetItem(widget, [item])
                elif isinstance(widget, QMenuBar):
                    widget.clear()
                    for item in items:
                        widget.addMenu(item)
                elif isinstance(widget, QToolBar):
                    widget.clear()
                    widget.addAction(" | ".join(items))
            if "headers" in properties:
                headers = properties["headers"]
                if isinstance(headers, str):
                    headers = [part.strip() for part in headers.split("|") if part.strip()]
                if isinstance(widget, QTableWidget):
                    widget.setHorizontalHeaderLabels([str(item) for item in headers])
                elif isinstance(widget, QTreeWidget):
                    widget.setHeaderLabels([str(item) for item in headers])
            if isinstance(widget, QTableWidget):
                if "rows" in properties:
                    widget.setRowCount(int(properties["rows"]))
                if "columns" in properties:
                    widget.setColumnCount(int(properties["columns"]))
            if "tab_names" in properties and isinstance(widget, QTabWidget):
                names = properties["tab_names"]
                if isinstance(names, str):
                    names = [part.strip() for part in names.split("|") if part.strip()]
                while widget.count() < len(names):
                    widget.addTab(QWidget(widget), "")
                while widget.count() > len(names):
                    widget.removeTab(widget.count() - 1)
                for index, name in enumerate(names):
                    widget.setTabText(index, str(name))
            if "current_tab" in properties and isinstance(widget, QTabWidget) and widget.count():
                widget.setCurrentIndex(max(0, min(int(properties["current_tab"]), widget.count() - 1)))
            if "format" in properties and isinstance(widget, QDateTimeEdit):
                widget.setDisplayFormat(str(properties["format"]))
            if "calendar_popup" in properties and isinstance(widget, QDateTimeEdit):
                widget.setCalendarPopup(bool(properties["calendar_popup"]))
            if "text_visible" in properties and isinstance(widget, QProgressBar):
                widget.setTextVisible(bool(properties["text_visible"]))
            if "grid_visible" in properties and isinstance(widget, QCalendarWidget):
                widget.setGridVisible(bool(properties["grid_visible"]))
            if "navigation_visible" in properties and isinstance(widget, QCalendarWidget):
                widget.setNavigationBarVisible(bool(properties["navigation_visible"]))
            if "url" in properties and isinstance(widget, QTextBrowser):
                widget.setPlainText(str(properties["url"]))
            if "source" in properties and isinstance(widget, QLabel):
                source = str(properties["source"])
                if source:
                    widget.setToolTip(source)
            if any(key in properties for key in ("font_family", "font_size", "font_bold", "font_italic")):
                font = widget.font()
                if "font_family" in properties:
                    font.setFamily(str(properties["font_family"]))
                if "font_size" in properties:
                    font.setPointSize(int(properties["font_size"]))
                if "font_bold" in properties:
                    font.setBold(bool(properties["font_bold"]))
                if "font_italic" in properties:
                    font.setItalic(bool(properties["font_italic"]))
                widget.setFont(font)
            if "background" in properties or "foreground" in properties:
                background = QColor(properties.get("background", "#ffffff"))
                foreground = QColor(properties.get("foreground", "#26313d"))
                if not background.isValid() or not foreground.isValid():
                    raise ValueError("invalid background color")
                widget.setStyleSheet(f"background-color:{background.name()}; color:{foreground.name()}")
        finally:
            widget.blockSignals(False)

    def closeEvent(self, event):
        handler = self.form["form"].get("events", {}).get("close")
        if handler:
            self.event.emit(handler, {"id": self.window_id, "event": "close"})
        self.closed.emit()
        event.accept()


class RuntimeWindowManager:
    """Owns independent runtime forms and routes their events to one runner."""

    def __init__(self, forms, event_handler=None, parent=None):
        self.forms = {str(key): copy.deepcopy(value) for key, value in forms.items()}
        self.event_handler = event_handler
        self.parent = parent
        self.windows = {}
        self.aliases = {}
        for key in self.forms:
            self.aliases[key] = key
            aliases = {Path(key).name, Path(key).as_posix()}
            if Path(key).name.endswith(".form.json"):
                aliases.add(Path(key).name[:-10])
            form_id = self.forms[key].get("form", {}).get("id")
            if isinstance(form_id, str) and form_id:
                aliases.add(form_id)
            title = self.forms[key].get("form", {}).get("title")
            if isinstance(title, str) and title:
                aliases.add(title)
            for alias in aliases:
                current = self.aliases.get(alias)
                if current is None:
                    self.aliases[alias] = key
                elif current != key:
                    self.aliases.pop(alias, None)

    def _resolve(self, window_id):
        if not isinstance(window_id, str):
            raise KeyError(window_id)
        return self.aliases.get(window_id, window_id)

    def open(self, window_id):
        window_id = self._resolve(window_id)
        if window_id not in self.forms:
            raise KeyError(window_id)
        current = self.windows.get(window_id)
        if current is not None:
            current.show()
            current.raise_()
            current.activateWindow()
            return current
        form = self.forms[window_id]
        form.setdefault("form", {})["id"] = window_id
        window = RuntimeForm(form, self.parent)
        if self.event_handler:
            window.event.connect(self.event_handler)
        window.closed.connect(lambda wid=window_id: self._closed(wid))
        self.windows[window_id] = window
        window.show()
        return window

    def _closed(self, window_id):
        self.windows.pop(window_id, None)

    def close(self, window_id=None):
        targets = list(self.windows) if window_id is None else [self._resolve(window_id)]
        for key in targets:
            window = self.windows.pop(key, None)
            if window:
                window.close()

    def load_event(self, window_id=None):
        if window_id is not None:
            window_id = self._resolve(window_id)
        for key, window in list(self.windows.items()):
            if window_id is None or key == window_id:
                window.load_event()

    def update_control(self, control_id, properties, window_id=None):
        if window_id is not None:
            try:
                window_id = self._resolve(window_id)
            except KeyError:
                return False
        targets = [self.windows[window_id]] if window_id in self.windows else list(self.windows.values()) if window_id is None else []
        for window in targets:
            if control_id in window.widgets:
                window.update_control(control_id, properties)
                return True
        return False
