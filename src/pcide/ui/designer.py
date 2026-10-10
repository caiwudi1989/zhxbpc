from __future__ import annotations

import copy

from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QFont, QIcon, QPainter, QPen, QKeySequence
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView, QMenu,
                               QMessageBox, QStyle, QTreeWidget, QTreeWidgetItem)

from pcide.core.control_catalog import control_defaults, CONTROL_LABELS
from .control_icons import control_icon
from pcide.core.project import CONTROL_TYPES, ControlModel, unique_control_name, validate_form

MIME_CONTROL = "application/x-pcide-control"
ARRANGEMENTS = (
    ("左对齐", "left"), ("右对齐", "right"), ("上对齐", "top"), ("下对齐", "bottom"),
    ("水平居中对齐", "horizontal"), ("垂直居中对齐", "vertical"),
    ("等宽", "width"), ("等高", "height"), ("等大", "size"),
    ("水平等间距", "distribute_x"), ("垂直等间距", "distribute_y"),
    ("在父容器中水平居中", "parent_x"), ("在父容器中垂直居中", "parent_y"),
)

# The designer shows the complete window chrome while keeping form coordinates
# relative to the client area, just like the runtime window.
FRAME_MARGIN = 10
TITLE_BAR_HEIGHT = 32


CONTROL_GROUPS = {
    "基本组件": ("Button", "Label", "Entry", "Text", "CheckBox", "RadioButton", "ComboBox", "ListBox"),
    "数据与视图": ("Tree", "Table", "ProgressBar", "Slider", "SpinBox", "DateTime", "Calendar"),
    "容器与布局": ("Frame", "Tabs", "Splitter", "ScrollArea", "Canvas"),
    "高级控件": ("Image", "RichText", "WebView", "MenuBar", "ToolBar", "StatusBar", "Timer"),
}


class Toolbox(QTreeWidget):
    controlRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self._display_mode = "text"
        for group, controls in CONTROL_GROUPS.items():
            parent_item = QTreeWidgetItem(self, [group])
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsDragEnabled)
            parent_item.setExpanded(True)
            for name in controls:
                item = QTreeWidgetItem(parent_item, [CONTROL_LABELS[name]])
                item.setData(0, Qt.ItemDataRole.UserRole, name)
        self.set_display_mode("text")
        self.setDragEnabled(True)

    def set_display_mode(self, mode):
        """Switch the toolbox between a compact icon list and plain text."""
        mode = "icon" if str(mode).lower() in {"icon", "icons", "图标"} else "text"
        self._display_mode = mode
        for group_index in range(self.topLevelItemCount()):
            group = self.topLevelItem(group_index)
            for item_index in range(group.childCount()):
                item = group.child(item_index)
                item.setIcon(0, control_icon(item.data(0, Qt.ItemDataRole.UserRole)) if mode == "icon" else QIcon())
        # QTreeWidget has no separate icon-only mode; the menu below provides
        # the compact icon presentation while this view remains keyboard and
        # drag friendly.  Keep indentation stable for text users.
        self.setIndentation(10 if mode == "icon" else 16)

    def menu(self, parent=None):
        """Create a categorized popup menu for click-to-add controls."""
        popup = QMenu(parent or self)
        popup._categories = []  # Retain Python wrappers for Qt submenu ownership.
        for group, controls in CONTROL_GROUPS.items():
            submenu = QMenu(group, popup)
            popup.addMenu(submenu)
            popup._categories.append(submenu)
            for name in controls:
                action = submenu.addAction(control_icon(name), CONTROL_LABELS[name])
                action.setData(name)
                action.triggered.connect(lambda _checked=False, kind=name: self.controlRequested.emit(kind))
        return popup

    def startDrag(self, actions):
        if self.currentItem() and self.currentItem().data(0, Qt.ItemDataRole.UserRole):
            mime = QMimeData()
            mime.setData(MIME_CONTROL, self.currentItem().data(0, Qt.ItemDataRole.UserRole).encode())
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)


class ControlItem(QGraphicsObject):
    def __init__(self, data, designer):
        super().__init__()
        self.data = data
        self.designer = designer
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        origin = designer.control_origin(data)
        self.setPos(origin.x() + data["x"], origin.y() + data["y"])
        self.resize_mode = False

    def boundingRect(self):
        return QRectF(-3, -3, self.data["width"] + 7, self.data["height"] + 7)

    def paint(self, painter, option, widget=None):
        props = self.data["properties"]
        rect = QRectF(0, 0, self.data["width"], self.data["height"])
        kind = self.data["type"]
        painter.setPen(QPen(QColor("#9ba8b5"), 1))
        painter.setBrush(QColor(props.get("background", "#f3f5f7" if kind == "Button" else "#ffffff")))
        painter.drawRect(rect)
        painter.setPen(QColor(props.get("foreground", "#26313d")))
        font = QFont(painter.font())
        font.setPointSize(max(1, int(props.get("font_size", 9))))
        font.setBold(bool(props.get("font_bold", False)))
        font.setItalic(bool(props.get("font_italic", False)))
        if props.get("font_family"):
            font.setFamily(str(props["font_family"]))
        painter.setFont(font)
        alignment = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                     "right": Qt.AlignmentFlag.AlignRight}.get(props.get("alignment", "left"), Qt.AlignmentFlag.AlignLeft)
        if kind == "Frame":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 8, -1, -1))
            painter.fillRect(QRectF(10, 0, min(rect.width() - 20, 120), 18), QColor("#ffffff"))
            painter.drawText(QRectF(14, 0, rect.width() - 28, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             str(props.get("text") or self.data["name"]))
        elif kind == "Tabs":
            names = [name.strip() for name in str(props.get("tab_names", "第一页")).split("|") if name.strip()] or ["第一页"]
            tab_width = max(70, min(140, int(rect.width() / max(1, len(names)))))
            for index, name in enumerate(names):
                tab = QRectF(index * tab_width, 0, tab_width, 24)
                painter.setBrush(QColor("#dce9f8" if index == int(props.get("current_tab", 0)) else "#edf1f5"))
                painter.drawRect(tab)
                painter.setPen(QColor("#26313d"))
                painter.drawText(tab, Qt.AlignmentFlag.AlignCenter, name)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 23, -1, -1))
        else:
            painter.drawText(rect.adjusted(8, 2, -5, -2), Qt.AlignmentFlag.AlignVCenter | alignment,
                             str(props.get("text") or self.data["name"]))
        if self.data["type"] in {"CheckBox", "RadioButton"}:
            painter.drawRect(QRectF(4, 7, 10, 10))
        if self.isSelected():
            painter.setPen(QPen(QColor("#176ac6"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            painter.fillRect(QRectF(rect.right() - 5, rect.bottom() - 5, 8, 8), QColor("#176ac6"))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            size = self.designer.form.get("grid", {}).get("size", 10)
            snap = self.designer.form.get("grid", {}).get("snap", True)
            origin = self.designer.control_origin(self.data)
            x, y = max(0, value.x() - origin.x()), max(0, value.y() - origin.y())
            if snap:
                x, y = round(x / size) * size, round(y / size) * size
            return QPointF(origin.x() + min(x, 10000), origin.y() + min(y, 10000))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            origin = self.designer.control_origin(self.data)
            self.data["x"], self.data["y"] = round(self.pos().x() - origin.x()), round(self.pos().y() - origin.y())
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.designer.begin_edit()
        self.resize_mode = event.pos().x() > self.data["width"] - 9 and event.pos().y() > self.data["height"] - 9
        self.resize_start = event.scenePos()
        self.original_size = (self.data["width"], self.data["height"])
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_mode:
            delta = event.scenePos() - self.resize_start
            self.prepareGeometryChange()
            self.data["width"] = min(10000, max(20, round(self.original_size[0] + delta.x())))
            self.data["height"] = min(10000, max(18, round(self.original_size[1] + delta.y())))
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.resize_mode = False
        self.designer.commit_edit()

    def mouseDoubleClickEvent(self, event):
        self.designer.event_requested.emit(self.data["id"], "click")
        event.accept()

    def contextMenuEvent(self, event):
        self.setSelected(True)
        self.designer.show_control_menu(self, event.screenPos())
        event.accept()


class FormDesigner(QGraphicsView):
    changed = Signal()
    selected = Signal(str)
    event_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.form = {}
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.items_by_id = {}
        self.undo_states = []
        self.redo_states = []
        self.before = None
        self.loading = False
        self.clipboard = []
        self.scene_obj.selectionChanged.connect(self._selection_changed)

    def load(self, form, preserve_history=False):
        self.loading = True
        self.form = copy.deepcopy(validate_form(form))
        self.scene_obj.clear()
        self.items_by_id.clear()
        metadata = self.form["form"]
        self.scene_obj.setSceneRect(0, 0, metadata["width"] + FRAME_MARGIN * 2 + 30,
                                    metadata["height"] + TITLE_BAR_HEIGHT + FRAME_MARGIN * 2 + 30)
        origin = self.client_origin()
        backdrop = self.scene_obj.addRect(origin.x(), origin.y(), metadata["width"], metadata["height"],
                                         QPen(QColor("#bac3cd")), QBrush(QColor(metadata.get("background", "#fff"))))
        backdrop.setZValue(-2)
        remaining = list(self.form["controls"])
        while remaining:
            ready = [data for data in remaining if not data["parent"] or data["parent"] in self.items_by_id]
            for data in ready:
                item = ControlItem(data, self)
                if data["parent"]:
                    item.setParentItem(self.items_by_id[data["parent"]])
                else:
                    self.scene_obj.addItem(item)
                self.items_by_id[data["id"]] = item
                remaining.remove(data)
        if not preserve_history:
            self.undo_states.clear()
            self.redo_states.clear()
        self.loading = False
        self.selected.emit("")

    def client_origin(self):
        return QPointF(FRAME_MARGIN, TITLE_BAR_HEIGHT + FRAME_MARGIN)

    def _window_button_labels(self):
        window = self.form.get("form", {}).get("window", {})
        labels = []
        if window.get("minimize", True):
            labels.append("—")
        if window.get("maximize", True):
            labels.append("□")
        labels.append("×")
        return labels

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#e9edf1"))
        if not self.form:
            return
        metadata = self.form["form"]
        origin = self.client_origin()
        client = QRectF(origin.x(), origin.y(), metadata["width"], metadata["height"])
        window_rect = client.adjusted(-FRAME_MARGIN, -TITLE_BAR_HEIGHT - FRAME_MARGIN, FRAME_MARGIN, FRAME_MARGIN)
        painter.fillRect(window_rect, QColor("#ffffff"))
        painter.fillRect(QRectF(window_rect.left(), window_rect.top(), window_rect.width(), TITLE_BAR_HEIGHT), QColor("#e7ebf0"))
        painter.setPen(QPen(QColor("#7c8794"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(window_rect)
        painter.setPen(QColor("#27313b"))
        title = str(metadata.get("title", "窗口"))
        painter.drawText(QRectF(window_rect.left() + 10, window_rect.top(), window_rect.width() - 150, TITLE_BAR_HEIGHT),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
        labels = self._window_button_labels()
        button_width = 34
        right = window_rect.right() - 2
        for label in reversed(labels):
            button = QRectF(right - button_width + 1, window_rect.top() + 2, button_width, TITLE_BAR_HEIGHT - 4)
            if label == "×":
                painter.setBrush(QColor("#d9534f"))
                painter.setPen(QColor("#ffffff"))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QColor("#27313b"))
            painter.drawRect(button)
            painter.drawText(button, Qt.AlignmentFlag.AlignCenter, label)
            right -= button_width
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor("#bac3cd"))
        painter.drawRect(client)

    def drawForeground(self, painter, rect):
        if not self.form.get("grid", {}).get("enabled", True):
            return
        painter.setPen(QColor("#d9e0e6"))
        size = self.form.get("grid", {}).get("size", 10)
        metadata = self.form["form"]
        origin = self.client_origin()
        left = max(origin.x(), origin.x() + int((rect.left() - origin.x()) // size * size))
        top = max(origin.y(), origin.y() + int((rect.top() - origin.y()) // size * size))
        for x in range(int(left), int(origin.x() + metadata["width"]) + 1, size):
            for y in range(int(top), int(origin.y() + metadata["height"]) + 1, size):
                painter.drawPoint(x, y)

    def _selection_changed(self):
        if not self.loading:
            selected = self.selected_items()
            self.selected.emit(selected[0].data["id"] if selected else "")

    def selected_items(self):
        return sorted((i for i in self.scene_obj.selectedItems() if isinstance(i, ControlItem)), key=lambda i: i.data["id"])

    def control_origin(self, data):
        return QPointF(0, 0) if data["parent"] else self.client_origin()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selected()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_controls()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def select(self, control_id):
        self.scene_obj.clearSelection()
        if control_id in self.items_by_id:
            item = self.items_by_id[control_id]
            item.setSelected(True)
            self.ensureVisible(item)

    def begin_edit(self):
        self.before = copy.deepcopy(self.form)

    def commit_edit(self):
        if self.before is not None and self.before != self.form:
            validate_form(self.form)
            self.undo_states.append(self.before)
            self.undo_states = self.undo_states[-50:]
            self.redo_states.clear()
            self.changed.emit()
            self._selection_changed()
        self.before = None

    def add(self, kind, x=40, y=40):
        self.begin_edit()
        name = unique_control_name(kind, set(self.items_by_id))
        properties = control_defaults(kind)
        properties["text"] = CONTROL_LABELS[kind]
        control = ControlModel(name, kind, name, x=max(0, int(x)), y=max(0, int(y)), properties=properties)
        self.form["controls"].append(control.to_dict())
        self.commit_edit()
        self.load(self.form, True)
        self.select(name)
        return name

    def update_control(self, control_id, changes):
        candidate = copy.deepcopy(self.form)
        data = next(c for c in candidate["controls"] if c["id"] == control_id)
        for key, value in changes.items():
            if key in {"name", "parent", "x", "y", "width", "height", "events"}:
                data[key] = value
            else:
                data["properties"][key] = value
        validate_form(candidate)
        self.begin_edit()
        self.form = candidate
        self.commit_edit()
        self.load(self.form, True)
        self.select(control_id)

    def duplicate(self):
        if not self.selected_items():
            return
        self.copy_selected()
        self.paste_controls()

    def copy_selected(self):
        selected_ids = {item.data["id"] for item in self.selected_items()}
        # 复制容器时自动带上全部后代，保持粘贴后的完整控件树。
        changed = True
        while changed:
            changed = False
            for data in self.form.get("controls", []):
                if data["parent"] in selected_ids and data["id"] not in selected_ids:
                    selected_ids.add(data["id"])
                    changed = True
        order = {data["id"]: index for index, data in enumerate(self.form["controls"])}
        self.clipboard = [copy.deepcopy(data) for data in sorted(
            (data for data in self.form["controls"] if data["id"] in selected_ids),
            key=lambda data: order[data["id"]])]

    def paste_controls(self):
        if not self.clipboard:
            return
        self.begin_edit()
        used = {c["id"] for c in self.form["controls"]}
        copied_ids = {c["id"] for c in self.clipboard}
        clones = {}
        for source in self.clipboard:
            data = copy.deepcopy(source)
            name = unique_control_name(data["type"], used)
            used.add(name)
            clones[data["id"]] = name
            offset = 0 if data["parent"] in copied_ids else 20
            data.update(id=name, name=name, x=data["x"] + offset, y=data["y"] + offset)
            self.form["controls"].append(data)
        for data in self.form["controls"]:
            if data["id"] in clones.values() and data["parent"] in clones:
                data["parent"] = clones[data["parent"]]
        self.commit_edit()
        self.load(self.form, True)
        self.select(next(iter(clones.values())))

    def show_control_menu(self, item, position):
        menu = QMenu(self)
        copy_action = menu.addAction("复制控件")
        paste_action = menu.addAction("粘贴控件")
        paste_action.setEnabled(bool(self.clipboard))
        if hasattr(self, "arrangement_actions"):
            arrange_menu = menu.addMenu("排列")
            arrange_menu.addActions(self.arrangement_actions)
        menu.addSeparator()
        click_event = menu.addAction("编辑单击事件")
        double_click_event = menu.addAction("编辑双击事件")
        change_event = menu.addAction("编辑状态改变事件")
        from .properties import control_events
        change_event.setEnabled('change' in control_events(item.data['type']))
        menu.addSeparator()
        delete_action = menu.addAction("删除控件")
        chosen = menu.exec(position)
        if chosen == copy_action:
            self.copy_selected()
        elif chosen == paste_action:
            self.paste_controls()
        elif chosen == click_event:
            self.event_requested.emit(item.data["id"], "click")
        elif chosen == double_click_event:
            self.event_requested.emit(item.data["id"], "double_click")
        elif chosen == change_event:
            self.event_requested.emit(item.data["id"], "change")
        elif chosen == delete_action:
            self.delete_selected()

    def delete_selected(self, confirm=True):
        removed = {i.data["id"] for i in self.selected_items()}
        if not removed:
            return
        if confirm:
            answer = QMessageBox.question(self, "删除控件", f"确定删除选中的 {len(removed)} 个控件吗？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.begin_edit()
        self.form["controls"] = [c for c in self.form["controls"] if c["id"] not in removed]
        for data in self.form["controls"]:
            if data["parent"] in removed:
                data["parent"] = ""
                position = self.items_by_id[data["id"]].scenePos() - self.client_origin()
                data["x"], data["y"] = max(0, min(10000, round(position.x()))), max(0, min(10000, round(position.y())))
        self.commit_edit()
        self.load(self.form, True)

    def align(self, mode):
        if mode not in {value for _, value in ARRANGEMENTS}:
            raise ValueError("不支持的排列方式")
        identities = {item.data["id"] for item in self.selected_items()}
        if not identities:
            return
        candidate = copy.deepcopy(self.form)
        groups = {}
        for data in candidate["controls"]:
            if data["id"] in identities:
                groups.setdefault(data["parent"], []).append(data)
        for parent, selected in groups.items():
            anchor = selected[0]
            if mode.startswith("distribute"):
                if len(selected) < 3:
                    continue
                axis, dimension = ("x", "width") if mode.endswith("x") else ("y", "height")
                selected.sort(key=lambda c: c[axis])
                start = selected[0][axis]
                end = selected[-1][axis] + selected[-1][dimension]
                gap = (end - start - sum(c[dimension] for c in selected)) / (len(selected) - 1)
                position = start
                for data in selected:
                    data[axis] = max(0, min(10000, round(position)))
                    position += data[dimension] + gap
                continue
            container = next((c for c in candidate["controls"] if c["id"] == parent), candidate["form"])
            for data in selected:
                if mode in {"width", "size"}:
                    data["width"] = anchor["width"]
                if mode in {"height", "size"}:
                    data["height"] = anchor["height"]
                if mode in {"left", "top"}:
                    axis = "x" if mode == "left" else "y"
                    data[axis] = anchor[axis]
                elif mode in {"right", "bottom", "horizontal", "vertical"}:
                    axis, dimension = ("x", "width") if mode in {"right", "horizontal"} else ("y", "height")
                    factor = .5 if mode in {"horizontal", "vertical"} else 1
                    data[axis] = max(0, min(10000, round(anchor[axis] + (anchor[dimension] - data[dimension]) * factor)))
                elif mode in {"parent_x", "parent_y"}:
                    axis, dimension = ("x", "width") if mode == "parent_x" else ("y", "height")
                    data[axis] = max(0, (container[dimension] - data[dimension]) // 2)
        validate_form(candidate)
        self.begin_edit()
        self.form = candidate
        self.commit_edit()
        self.load(self.form, True)
        for identity in identities:
            self.items_by_id[identity].setSelected(True)

    def select_all(self):
        for item in self.items_by_id.values():
            item.setSelected(True)

    def change_order(self, front):
        identities = {item.data["id"] for item in self.selected_items()}
        if not identities:
            return
        selected = [c for c in self.form["controls"] if c["id"] in identities]
        remaining = [c for c in self.form["controls"] if c["id"] not in identities]
        self.begin_edit()
        self.form["controls"] = remaining + selected if front else selected + remaining
        self.commit_edit()
        self.load(self.form, True)
        for identity in identities:
            self.items_by_id[identity].setSelected(True)

    def undo(self):
        if self.undo_states:
            self.redo_states.append(copy.deepcopy(self.form))
            self.load(self.undo_states.pop(), True)
            self.changed.emit()

    def redo(self):
        if self.redo_states:
            self.undo_states.append(copy.deepcopy(self.form))
            self.load(self.redo_states.pop(), True)
            self.changed.emit()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_CONTROL):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_CONTROL):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_CONTROL):
            kind = bytes(event.mimeData().data(MIME_CONTROL)).decode()
            if kind in CONTROL_TYPES:
                position = self.mapToScene(event.position().toPoint()) - self.client_origin()
                self.add(kind, position.x(), position.y())
                event.acceptProposedAction()
        else:
            super().dropEvent(event)
