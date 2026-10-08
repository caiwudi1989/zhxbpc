"""Shared, editable control contracts for the designer and runtime."""
from __future__ import annotations

import copy

CONTROL_LABELS = {
    "Button": "按钮", "Label": "标签", "Entry": "编辑框", "Text": "多行编辑框",
    "CheckBox": "复选框", "RadioButton": "单选框", "ComboBox": "组合框", "ListBox": "列表框",
    "Tree": "树形框", "Table": "表格", "ProgressBar": "进度条", "Slider": "滑块",
    "SpinBox": "数字输入", "DateTime": "日期时间", "Frame": "分组框", "Tabs": "分组夹", "Canvas": "画板",
    "Image": "图片框", "RichText": "富文本框", "WebView": "网页浏览器", "MenuBar": "菜单栏",
    "ToolBar": "工具栏", "StatusBar": "状态栏", "Calendar": "月历", "Splitter": "分割器",
    "ScrollArea": "滚动区", "Timer": "时钟",
}
CONTROL_GROUPS = {
    "基本组件": ("Button", "Label", "Entry", "Text", "CheckBox", "RadioButton", "ComboBox", "ListBox"),
    "数据与视图": ("Tree", "Table", "ProgressBar", "Slider", "SpinBox", "DateTime", "Calendar"),
    "容器与布局": ("Frame", "Tabs", "Splitter", "ScrollArea", "Canvas"),
    "高级组件": ("Image", "RichText", "WebView", "MenuBar", "ToolBar", "StatusBar", "Timer"),
}
COMMON_PROPERTIES = {"text": "", "visible": True, "enabled": True, "tooltip": "", "background": "#ffffff",
                     "foreground": "#26313d", "font_family": "Microsoft YaHei UI", "font_size": 9,
                     "font_bold": False, "font_italic": False, "tab_stop": True, "anchor": "", "auto_fill": False}
CONTROL_PROPERTIES = {
    "Button": {"checkable": False, "checked": False, "default_button": False},
    "Label": {"alignment": "left", "word_wrap": False},
    "Entry": {"alignment": "left", "placeholder": "", "read_only": False, "max_length": 32767, "echo_mode": "normal"},
    "Text": {"placeholder": "", "read_only": False, "word_wrap": True},
    "CheckBox": {"checked": False, "tristate": False}, "RadioButton": {"checked": False, "auto_exclusive": True},
    "ComboBox": {"items": [], "current_index": -1, "editable": False, "placeholder": "", "max_visible_items": 10},
    "ListBox": {"items": [], "current_row": -1, "selection_mode": "single", "sorting": False},
    "Tree": {"items": [], "headers": ["名称"], "selection_mode": "single", "sorting": False, "header_visible": True},
    "Table": {"items": [], "headers": ["列1", "列2"], "rows": 3, "columns": 2, "read_only": False,
              "selection_mode": "single", "sorting": False, "header_visible": True},
    "ProgressBar": {"minimum": 0, "maximum": 100, "value": 50, "text_visible": True, "format": "%p%", "orientation": "horizontal"},
    "Slider": {"minimum": 0, "maximum": 100, "value": 50, "step": 1, "orientation": "horizontal"},
    "SpinBox": {"minimum": 0, "maximum": 100, "value": 0, "step": 1, "prefix": "", "suffix": "", "read_only": False},
    "DateTime": {"format": "yyyy-MM-dd HH:mm:ss", "date_time": "", "calendar_popup": True},
    "Frame": {"border_style": "styled", "checkable": False, "checked": True},
    "Tabs": {"tab_names": "第一页|第二页", "current_tab": 0, "tab_position": "top", "tab_closable": False},
    "Canvas": {}, "Image": {"source": "", "scaled_contents": True, "alignment": "center"},
    "RichText": {"read_only": False, "word_wrap": True}, "WebView": {"url": "about:blank", "zoom": 100},
    "MenuBar": {"items": ["文件", "编辑"]}, "ToolBar": {"items": ["工具1", "工具2"], "orientation": "horizontal", "icon_size": 16},
    "StatusBar": {"size_grip": True}, "Calendar": {"selected_date": "", "grid_visible": False, "navigation_visible": True},
    "Splitter": {"orientation": "horizontal", "handle_width": 4, "children_collapsible": True},
    "ScrollArea": {"widget_resizable": True, "horizontal_scroll": "as_needed", "vertical_scroll": "as_needed"},
    "Timer": {"interval": 1000, "auto_start": False, "single_shot": False},
}
CONTAINERS = {"Frame", "Tabs", "Splitter", "ScrollArea"}
CHOICES = {
    "alignment": (("左对齐", "left"), ("居中", "center"), ("右对齐", "right")),
    "orientation": (("水平", "horizontal"), ("垂直", "vertical")),
    "border_style": (("有边框", "styled"), ("平面", "flat")),
    "echo_mode": (("普通", "normal"), ("密码", "password"), ("不显示", "none")),
    "selection_mode": (("单选", "single"), ("多选", "multi"), ("扩展选择", "extended")),
    "tab_position": (("顶部", "top"), ("底部", "bottom"), ("左侧", "left"), ("右侧", "right")),
    "anchor": (("不锚定", ""), ("左上", "top_left"), ("右上", "top_right"), ("左下", "bottom_left"),
               ("右下", "bottom_right"), ("居中", "center")),
    "horizontal_scroll": (("自动", "as_needed"), ("始终显示", "always"), ("隐藏", "off")),
    "vertical_scroll": (("自动", "as_needed"), ("始终显示", "always"), ("隐藏", "off")),
}
INTEGER_RANGES = {"font_size": (1, 200), "max_length": (0, 1000000), "interval": (1, 2147483647),
                  "rows": (0, 1000), "columns": (0, 1000), "current_tab": (0, 999),
                  "current_index": (-1, 9999), "current_row": (-1, 9999), "zoom": (25, 500),
                  "max_visible_items": (1, 1000), "icon_size": (1, 256), "handle_width": (1, 100),
                  "minimum": (-1000000, 1000000), "maximum": (-1000000, 1000000),
                  "value": (-1000000, 1000000), "step": (1, 1000000)}
LIST_PROPERTIES = {"items", "headers"}


def control_defaults(kind):
    values = copy.deepcopy(COMMON_PROPERTIES)
    values.update(copy.deepcopy(CONTROL_PROPERTIES[kind]))
    values["text"] = CONTROL_LABELS[kind]
    return values


def list_values(value):
    return [part.strip() for part in value.split("|") if part.strip()] if isinstance(value, str) else list(value)


def validate_properties(kind, props):
    defaults = control_defaults(kind)
    for key, value in props.items():
        if key not in defaults:
            continue  # Preserve application-defined properties already permitted by the form schema.
        expected = defaults[key]
        if key in LIST_PROPERTIES:
            if not isinstance(value, (str, list)) or len(list_values(value)) > 1000 or any(not isinstance(v, str) for v in list_values(value)):
                raise ValueError(f"invalid control {key}")
        elif isinstance(expected, bool):
            if type(value) is not bool:
                raise ValueError(f"invalid control {key}")
        elif isinstance(expected, int):
            low, high = INTEGER_RANGES.get(key, (0, 10000))
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"invalid control {key}")
        elif not isinstance(value, str) or len(value) > 1048576:
            raise ValueError(f"invalid control {key}")
        if key in CHOICES and value not in dict(CHOICES[key]).values():
            raise ValueError(f"invalid control {key}")
    if kind in {"ProgressBar", "Slider", "SpinBox"}:
        low, high, val = (props.get(k, defaults[k]) for k in ("minimum", "maximum", "value"))
        if low > high or not low <= val <= high:
            raise ValueError("control value must be within minimum and maximum")
    if kind == "Table" and props.get("rows", defaults["rows"]) * props.get("columns", defaults["columns"]) > 10000:
        raise ValueError("table limit: 10000 cells")
    if kind == "Tabs":
        names = list_values(props.get("tab_names", defaults["tab_names"]))
        if not names or props.get("current_tab", 0) >= len(names):
            raise ValueError("current tab must name an existing page")
