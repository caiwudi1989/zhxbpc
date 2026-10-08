from __future__ import annotations

import copy
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout, QLabel, QLineEdit,
    QScrollArea, QSpinBox, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from pcide.core.control_catalog import CHOICES, INTEGER_RANGES, control_defaults
from pcide.core.project import EVENT_TYPES

TYPE_LABELS = {"Button": "按钮", "Label": "标签", "Entry": "输入框", "Text": "多行文本",
               "CheckBox": "复选框", "RadioButton": "单选框", "ComboBox": "下拉框", "ListBox": "列表框",
               "Tree": "树形", "Table": "表格", "ProgressBar": "进度条", "Slider": "滑块", "SpinBox": "数字输入",
               "DateTime": "日期时间", "Frame": "分组框", "Tabs": "标签页", "Canvas": "画布", "Image": "图片",
               "RichText": "富文本", "WebView": "网页视图", "MenuBar": "菜单栏", "ToolBar": "工具栏",
               "StatusBar": "状态栏", "Calendar": "日历", "Splitter": "分割器", "ScrollArea": "滚动区", "Timer": "定时器"}
PROPERTY_LABELS = {"name": "名称", "parent": "父组件", "x": "横坐标", "y": "纵坐标", "width": "宽度",
                   "height": "高度", "text": "文本", "visible": "可见", "enabled": "启用", "background": "背景色",
                   "foreground": "文字颜色", "tooltip": "提示文本", "placeholder": "占位提示", "read_only": "只读",
                   "checked": "选中", "items": "项目（用 | 分隔）", "columns": "列数", "rows": "行数",
                   "value": "当前值", "minimum": "最小值", "maximum": "最大值", "step": "步长",
                   "source": "资源路径", "url": "网址", "interval": "定时周期（毫秒）", "auto_start": "自动启动",
                   "orientation": "方向", "alignment": "对齐方式", "font_size": "字号", "format": "显示格式",
                   "tab_names": "分组页名称（用 | 分隔）", "current_tab": "当前分组页", "border_style": "边框样式",
                   "anchor": "锚点", "auto_fill": "自动填充", "title": "标题", "min_width": "最小宽度",
                   "min_height": "最小高度", "max_width": "最大宽度", "max_height": "最大高度",
                   "fixed_width": "固定宽度", "fixed_height": "固定高度", "resizable": "允许调整大小",
                   "anchor_window": "窗口锚点", "dock": "停靠方式", "auto_fill_window": "窗口自动填充"}
PROPERTY_LABELS.update({
    "font_family": "字体", "font_bold": "粗体", "font_italic": "斜体", "tab_stop": "允许获得焦点",
    "checkable": "可勾选", "default_button": "默认按钮", "word_wrap": "自动换行", "max_length": "最大长度",
    "echo_mode": "显示模式", "tristate": "三态", "auto_exclusive": "自动互斥", "current_index": "当前项目",
    "editable": "允许编辑", "max_visible_items": "最大显示项目数", "current_row": "当前行", "selection_mode": "选择模式",
    "sorting": "允许排序", "headers": "表头（用 | 分隔）", "header_visible": "显示表头", "text_visible": "显示文字",
    "prefix": "前缀", "suffix": "后缀", "calendar_popup": "弹出日历", "tab_position": "标签位置",
    "tab_closable": "允许关闭标签", "source": "资源路径", "scaled_contents": "缩放内容", "zoom": "缩放比例",
    "items": "项目（用 | 分隔）", "icon_size": "图标大小", "size_grip": "显示尺寸柄", "selected_date": "选中日期",
    "grid_visible": "显示网格", "navigation_visible": "显示导航", "handle_width": "分隔条宽度",
    "children_collapsible": "允许折叠子项", "widget_resizable": "内容可缩放", "horizontal_scroll": "水平滚动",
    "vertical_scroll": "垂直滚动", "single_shot": "单次触发", "tab_names": "分组页名称（用 | 分隔）",
})
EVENT_LABELS = {"click": "点击", "double_click": "双击", "change": "变更", "load": "加载",
                "mouse_down": "按下鼠标", "key_down": "按下按键", "resize": "尺寸改变", "close": "关闭"}


class PropertyPanel(QTabWidget):
    property_changed = Signal(str, dict)
    form_changed = Signal(dict)
    event_changed = Signal(str, str, str)
    event_requested = Signal(str, str)
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.control_id = ""
        self.loading = False
        self.properties = QWidget()
        self.prop_form = QFormLayout(self.properties)
        self.prop_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.properties)
        self.addTab(self.scroll, "属性")
        self.events = QWidget()
        self.event_form = QFormLayout(self.events)
        self.addTab(self.events, "事件")
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(lambda item, _: self.selected.emit(item.data(0, Qt.ItemDataRole.UserRole) or ""))
        self.addTab(self.tree, "组件树")

    def show_selection(self, form, control_id="", handlers=()):
        self.loading = True
        self.control_id = control_id
        while self.prop_form.rowCount():
            self.prop_form.removeRow(0)
        while self.event_form.rowCount():
            self.event_form.removeRow(0)
        data = next((c for c in form["controls"] if c["id"] == control_id), None)
        self.prop_form.addRow(QLabel((TYPE_LABELS.get(data["type"], data["type"]) + " · " + data["id"]) if data else "主窗体"))
        if data:
            id_box = QLineEdit(data["id"])
            id_box.setReadOnly(True)
            id_box.setToolTip("控件唯一标识，代码和事件通过此标识访问")
            self.prop_form.addRow("控件编号", id_box)
        values = {k: data[k] for k in ("name", "parent", "x", "y", "width", "height")} if data else dict(form["form"])
        if data:
            props = data["properties"]
            values.update({"text": props.get("text", ""), "visible": props.get("visible", True),
                           "enabled": props.get("enabled", True), "background": props.get("background", "#ffffff"),
                           "foreground": props.get("foreground", "#26313d"), "tooltip": props.get("tooltip", ""),
                           "anchor": props.get("anchor", ""), "auto_fill": props.get("auto_fill", False),
                           "alignment": props.get("alignment", "left"), "font_size": props.get("font_size", 9)})
            for key, default in control_defaults(data["type"]).items():
                if key not in values:
                    current = props.get(key, default)
                    values[key] = "|".join(map(str, current)) if isinstance(current, list) else current
            if data["type"] in {"Entry", "Text", "ComboBox", "ListBox", "Tree", "Table"}:
                values["items"] = props.get("items", "") if isinstance(props.get("items", ""), str) else "|".join(map(str, props.get("items", [])))
            if data["type"] in {"Entry", "Text", "ComboBox"}:
                values["placeholder"] = props.get("placeholder", "")
                values["read_only"] = props.get("read_only", False)
            if data["type"] in {"CheckBox", "RadioButton"}:
                values["checked"] = props.get("checked", False)
            if data["type"] in {"ProgressBar", "Slider", "SpinBox"}:
                values.update({"value": props.get("value", 0), "minimum": props.get("minimum", 0),
                               "maximum": props.get("maximum", 100), "step": props.get("step", 1)})
            if data["type"] in {"Image", "WebView"}:
                values["source"] = props.get("source", "")
            if data["type"] == "WebView":
                values["url"] = props.get("url", "")
            if data["type"] == "Timer":
                values.update({"interval": props.get("interval", 1000), "auto_start": props.get("auto_start", False)})
            if data["type"] == "DateTime":
                values["format"] = props.get("format", "yyyy-MM-dd HH:mm:ss")
            if data["type"] == "Table":
                values.update({"columns": props.get("columns", 3), "rows": props.get("rows", 2)})
            if data["type"] in {"Slider", "Splitter"}:
                values["orientation"] = props.get("orientation", "horizontal")
            if data["type"] == "Tabs":
                values["tab_names"] = data["properties"].get("tab_names", "第一页")
                values["current_tab"] = data["properties"].get("current_tab", 0)
            elif data["type"] == "Frame":
                values["border_style"] = data["properties"].get("border_style", "styled")
        values.pop("events", None)
        window_values = values.pop("window", {}) if not data else {}
        if not data:
            values["允许最大化"] = window_values.get("maximize", True)
            values["允许最小化"] = window_values.get("minimize", True)
            values["resizable"] = window_values.get("resizable", True)
            values["fixed_width"] = window_values.get("fixed_width") or 0
            values["fixed_height"] = window_values.get("fixed_height") or 0
            values["min_width"] = window_values.get("min_width", 100)
            values["min_height"] = window_values.get("min_height", 100)
            values["max_width"] = window_values.get("max_width", 10000)
            values["max_height"] = window_values.get("max_height", 10000)
            values["anchor_window"] = window_values.get("anchor", "center")
            values["dock"] = window_values.get("dock", "none")
            values["auto_fill_window"] = window_values.get("auto_fill", False)
        self.widgets = {}
        for key, value in values.items():
            if key in {"允许最大化", "允许最小化", "resizable", "auto_fill_window", "read_only", "checked", "auto_start"}:
                widget = QCheckBox()
                widget.setChecked(bool(value))
                target = {"允许最大化": "maximize", "允许最小化": "minimize", "resizable": "resizable", "auto_fill_window": "auto_fill",
                          "read_only": "read_only", "checked": "checked", "auto_start": "auto_start"}[key]
                widget.toggled.connect(lambda val, k=target: self.form_changed.emit({"window": {k: val}}) if not self.loading else None)
                if data:
                    widget.toggled.disconnect()
                    widget.toggled.connect(lambda val, k=target: self._emit(k, val))
            elif key in {"x", "y", "width", "height", "fixed_width", "fixed_height", "min_width", "min_height", "max_width", "max_height",
                         "current_tab", "value", "minimum", "maximum", "step", "columns", "rows", "interval", "font_size",
                         "max_length", "current_index", "current_row", "max_visible_items", "zoom", "icon_size", "handle_width"}:
                widget = QSpinBox()
                if key in INTEGER_RANGES:
                    lower, upper = INTEGER_RANGES[key]
                else:
                    lower = 0 if key in {"x", "y", "fixed_width", "fixed_height"} else 20 if data else 100
                    upper = 10000
                widget.setRange(lower, upper)
                widget.setSpecialValueText("自动" if key in {"fixed_width", "fixed_height"} else "")
                widget.setValue(int(value or 0))
                if data:
                    widget.editingFinished.connect(lambda k=key, w=widget: self._emit(k, w.value()))
                else:
                    widget.editingFinished.connect(lambda k=key, w=widget: self.form_changed.emit({"window": {k: (w.value() or None) if k in {"fixed_width", "fixed_height"} else w.value()}}) if not self.loading else None)
            elif key in CHOICES:
                widget = QComboBox()
                for label, value_id in CHOICES[key]:
                    widget.addItem(label, value_id)
                widget.setCurrentIndex(max(0, widget.findData(value)))
                widget.currentIndexChanged.connect(lambda _, k=key, w=widget: self._emit(k, w.currentData()))
            elif key == "anchor_window":
                widget = QComboBox()
                widget.addItem("居中", "center")
                widget.addItem("左上", "top_left")
                widget.addItem("右上", "top_right")
                widget.addItem("左下", "bottom_left")
                widget.addItem("右下", "bottom_right")
                widget.setCurrentIndex(max(0, widget.findData(value)))
                widget.currentIndexChanged.connect(lambda _, w=widget: self.form_changed.emit({"window": {"anchor": w.currentData()}}) if not self.loading else None)
            elif key == "dock":
                widget = QComboBox()
                for label, dock in (("不自动停靠", "none"), ("左侧", "left"), ("右侧", "right"), ("顶部", "top"), ("底部", "bottom"), ("填充", "fill")):
                    widget.addItem(label, dock)
                widget.setCurrentIndex(max(0, widget.findData(value)))
                widget.currentIndexChanged.connect(lambda _, w=widget: self.form_changed.emit({"window": {"dock": w.currentData()}}) if not self.loading else None)
            elif key == "parent":
                widget = QComboBox()
                widget.addItem("（无父控件）", "")
                for candidate in form["controls"]:
                    if candidate["id"] != control_id:
                        widget.addItem(candidate["name"] + " · " + TYPE_LABELS.get(candidate["type"], candidate["type"]), candidate["id"])
                widget.setCurrentIndex(max(0, widget.findData(value)))
                widget.currentIndexChanged.connect(lambda _, k=key, w=widget: self._emit(k, w.currentData()))
            elif isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
                widget.toggled.connect(lambda val, k=key: self._emit(k, val))
            elif key in {"background", "foreground"}:
                widget = QToolButton()
                widget.setToolTip(PROPERTY_LABELS.get(key, key))
                widget.setStyleSheet(f"background:{value}; min-width:28px; min-height:20px")
                widget.clicked.connect(lambda _, k=key, val=value: self._pick_color(k, val))
            else:
                widget = QLineEdit(str(value))
                widget.editingFinished.connect(lambda k=key, w=widget: self._emit(k, w.text()))
            self.widgets[key] = widget
            self.prop_form.addRow(PROPERTY_LABELS.get(key, key), widget)
        events = data["events"] if data else form["form"].get("events", {})
        self.event_widgets = {}
        for key in EVENT_TYPES if data else ("load", "resize", "close"):
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItem("")
            combo.addItems(list(handlers))
            combo.setCurrentText(events.get(key, ""))
            combo.lineEdit().editingFinished.connect(lambda k=key, w=combo: self.event_changed.emit(self.control_id, k, w.currentText()) if not self.loading else None)
            button = QToolButton()
            button.setText("...")
            button.setToolTip("进入事件代码")
            button.clicked.connect(lambda _, k=key: self.event_requested.emit(self.control_id, k))
            row = QWidget()
            from PySide6.QtWidgets import QHBoxLayout
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(combo)
            layout.addWidget(button)
            self.event_widgets[key] = combo
            self.event_form.addRow(EVENT_LABELS.get(key, key), row)
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem(self.tree, [form["form"]["title"]])
        nodes = {"": root}
        pending = list(form["controls"])
        while pending:
            for data in list(pending):
                if data["parent"] in nodes:
                    item = QTreeWidgetItem(nodes[data["parent"]], [data["name"] + "：" + TYPE_LABELS.get(data["type"], data["type"])])
                    item.setData(0, Qt.ItemDataRole.UserRole, data["id"])
                    nodes[data["id"]] = item
                    pending.remove(data)
        self.tree.expandAll()
        if control_id in nodes:
            self.tree.setCurrentItem(nodes[control_id])
        self.tree.blockSignals(False)
        self.loading = False

    def _emit(self, key, value):
        if self.loading:
            return
        if self.control_id:
            self.property_changed.emit(self.control_id, {key: value})
        else:
            self.form_changed.emit({key: value})

    def _pick_color(self, key, value):
        color = QColorDialog.getColor(QColor(value), self)
        if color.isValid():
            self._emit(key, color.name())
