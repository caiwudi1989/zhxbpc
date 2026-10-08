from __future__ import annotations

import copy
import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import Paths, atomic_write_json, read_json
from .control_catalog import control_defaults, validate_properties

CONTROL_TYPES = ("Button", "Label", "Entry", "Text", "CheckBox", "RadioButton", "ComboBox",
                 "ListBox", "Tree", "Table", "ProgressBar", "Slider", "SpinBox", "DateTime", "Frame", "Tabs", "Canvas",
                 "Image", "RichText", "WebView", "MenuBar", "ToolBar", "StatusBar", "Calendar", "Splitter", "ScrollArea", "Timer")
EVENT_TYPES = ("click", "double_click", "change", "load", "mouse_down", "key_down", "resize", "close")
DEFAULT_FORM = {"version": 1, "form": {"title": "MainForm", "width": 760, "height": 440,
                "background": "#ffffff", "events": {"load": "on_main_form_load"},
                "window": {"maximize": True, "minimize": True, "resizable": True,
                            "fixed_width": None, "fixed_height": None, "min_width": 100,
                            "min_height": 100, "max_width": 10000, "max_height": 10000,
                            "anchor": "center", "dock": "none", "auto_fill": False}},
                "controls": [], "grid": {"enabled": True, "size": 10, "snap": True}}


class ProjectError(ValueError):
    pass


MAX_PROJECT_IMPORT_FILES = 10000
MAX_PROJECT_IMPORT_BYTES = 512 * 1024 * 1024


def relative_file(root: Path, value: str | Path) -> Path:
    if not isinstance(value, (str, Path)):
        raise ProjectError("relative path must be text")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not str(value).strip():
        raise ProjectError(f"invalid relative path: {value}")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ProjectError(f"path escapes root: {value}")
    return target


def valid_name(value: str) -> bool:
    return isinstance(value, str) and len(value) <= 64 and value.isidentifier()


def valid_file_name(value: str) -> bool:
    """Validate one user supplied path component without allowing traversal."""
    if not isinstance(value, str) or not value.strip() or value in {".", ".."}:
        return False
    if value != value.strip() or Path(value).name != value or any(char in value for char in '<>:"/\\|?*\x00'):
        return False
    stem = value.split(".", 1)[0].casefold()
    if stem in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}:
        return False
    if len(value) > 255 or value.endswith((".", " ")):
        return False
    return True


@dataclass
class ControlModel:
    id: str
    type: str
    name: str
    x: int = 40
    y: int = 40
    width: int = 120
    height: int = 34
    parent: str = ""
    properties: dict[str, Any] = field(default_factory=lambda: {"text": "", "visible": True, "enabled": True})
    events: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return copy.deepcopy(self.__dict__)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ProjectError("control must be an object")
        control = cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})
        if control.type not in CONTROL_TYPES or not valid_name(control.id) or not valid_name(control.name):
            raise ProjectError(f"invalid control type/identity: {control.id}")
        if not isinstance(control.parent, str):
            raise ProjectError("control parent must be an ID")
        for name, minimum in (("x", 0), ("y", 0), ("width", 20), ("height", 18)):
            number = getattr(control, name)
            if type(number) is not int or not minimum <= number <= 10000:
                raise ProjectError(f"invalid control {name}")
        validate_events(control.events)
        if not isinstance(control.properties, dict):
            raise ProjectError("control properties must be an object")
        try:
            validate_properties(control.type, control.properties)
        except ValueError as exc:
            raise ProjectError(str(exc)) from exc
        for key in ("auto_fill",):
            if key in control.properties and type(control.properties[key]) is not bool:
                raise ProjectError(f"invalid control {key}")
        for key in ("anchor", "dock"):
            if key in control.properties and (not isinstance(control.properties[key], str) or len(control.properties[key]) > 32):
                raise ProjectError(f"invalid control {key}")
        return control


def validate_events(events):
    if not isinstance(events, dict) or any(key not in EVENT_TYPES for key in events):
        raise ProjectError("invalid event type")
    if any(not isinstance(value, str) or (value and not valid_name(value)) for value in events.values()):
        raise ProjectError("event handler must be an identifier")


def validate_form(value):
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ProjectError("unsupported form schema")
    metadata = value.get("form")
    if not isinstance(metadata, dict):
        raise ProjectError("form metadata required")
    if not isinstance(metadata.get("title"), str):
        raise ProjectError("form title must be text")
    for key in ("width", "height"):
        if type(metadata.get(key)) is not int or not 100 <= metadata[key] <= 10000:
            raise ProjectError(f"invalid form {key}")
    validate_events(metadata.get("events", {}))
    window = metadata.get("window", {})
    if not isinstance(window, dict) or any(type(window.get(key, True)) is not bool for key in ("maximize", "minimize", "resizable", "auto_fill")):
        raise ProjectError("invalid window settings")
    for key in ("fixed_width", "fixed_height"):
        window_value = window.get(key)
        if window_value is not None and (type(window_value) is not int or not 100 <= window_value <= 10000):
            raise ProjectError(f"invalid window {key}")
    for key in ("min_width", "min_height", "max_width", "max_height"):
        window_value = window.get(key, 100 if key.startswith("min") else 10000)
        if type(window_value) is not int or not 100 <= window_value <= 10000:
            raise ProjectError(f"invalid window {key}")
    if window.get("fixed_width") and window["fixed_width"] < window.get("min_width", 100):
        raise ProjectError("fixed width is below minimum")
    if window.get("fixed_height") and window["fixed_height"] < window.get("min_height", 100):
        raise ProjectError("fixed height is below minimum")
    if window.get("fixed_width") and window["fixed_width"] > window.get("max_width", 10000):
        raise ProjectError("fixed width is above maximum")
    if window.get("fixed_height") and window["fixed_height"] > window.get("max_height", 10000):
        raise ProjectError("fixed height is above maximum")
    if window.get("min_width", 100) > window.get("max_width", 10000) or window.get("min_height", 100) > window.get("max_height", 10000):
        raise ProjectError("invalid window size range")
    if window.get("anchor", "center") not in {"center", "top_left", "top_right", "bottom_left", "bottom_right"}:
        raise ProjectError("invalid window anchor")
    if window.get("dock", "none") not in {"none", "left", "right", "top", "bottom", "fill"}:
        raise ProjectError("invalid window dock")
    if not isinstance(value.get("controls"), list):
        raise ProjectError("form controls must be an array")
    controls = [ControlModel.from_dict(c) for c in value["controls"]]
    if len(controls) > 1000:
        raise ProjectError("form limit: 1000 controls")
    ids = {c.id for c in controls}
    if len(ids) != len(controls) or len({c.name for c in controls}) != len(controls):
        raise ProjectError("duplicate control ID/name")
    parent_map = {c.id: c.parent for c in controls}
    for control in controls:
        current = control.parent
        seen = {control.id}
        while current:
            if current not in ids or current in seen:
                raise ProjectError("invalid/cyclic control parent")
            seen.add(current)
            current = parent_map[current]
    grid = value.get("grid", {})
    if not isinstance(grid, dict):
        raise ProjectError("grid must be an object")
    if type(grid.get("size", 10)) is not int or not 1 <= grid.get("size", 10) <= 100:
        raise ProjectError("grid size must be 1..100")
    if any(type(grid.get(key, True)) is not bool for key in ("enabled", "snap")):
        raise ProjectError("grid flags must be boolean")
    normalized = copy.deepcopy(value)
    normalized["form"].setdefault("window", {})
    normalized["form"]["window"].setdefault("resizable", True)
    normalized["form"]["window"].setdefault("fixed_width", None)
    normalized["form"]["window"].setdefault("fixed_height", None)
    normalized["form"]["window"].setdefault("min_width", 100)
    normalized["form"]["window"].setdefault("min_height", 100)
    normalized["form"]["window"].setdefault("max_width", 10000)
    normalized["form"]["window"].setdefault("max_height", 10000)
    normalized["form"]["window"].setdefault("anchor", "center")
    normalized["form"]["window"].setdefault("dock", "none")
    normalized["form"]["window"].setdefault("auto_fill", False)
    normalized["controls"] = [control.to_dict() for control in controls]
    return normalized


class Project:
    def __init__(self, root: str | Path, manifest: dict[str, Any]):
        self.root = Path(root).resolve()
        self.manifest = manifest
        if not isinstance(manifest, dict) or manifest.get("schema") != 1:
            raise ProjectError("unsupported project schema")
        if manifest.get("language") not in {"python", "javascript", "typescript", "zhxb"}:
            raise ProjectError("unsupported script language")
        if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
            raise ProjectError("project name required")
        execution = manifest.get("execution", {})
        if not isinstance(execution, dict):
            raise ProjectError("execution settings must be an object")
        timeout = execution.get("timeout_seconds", 60)
        output = execution.get("max_output_lines", 5000)
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or not 0 < timeout <= 86400:
            raise ProjectError("execution timeout must be finite and in (0, 86400]")
        if type(output) is not int or not 1 <= output <= 50000:
            raise ProjectError("output limit must be 1..50000")
        for field in ("modules", "permissions", "plugins"):
            if not isinstance(manifest.get(field, []), list) or any(not isinstance(v, str) for v in manifest.get(field, [])):
                raise ProjectError(f"{field} must be an array of strings")
        from .platform import validate_platform
        try:
            self.manifest["platform"] = validate_platform(manifest.get("platform"))
        except ValueError as exc:
            raise ProjectError(str(exc)) from exc
        self.entry_path

    @property
    def ide_dir(self):
        return self.root / ".pcide"

    @property
    def entry_path(self):
        return relative_file(self.root, self.manifest.get("entry", ""))

    @property
    def form_path(self):
        return self.root / "ui" / "main.form.json"

    @property
    def flow_path(self):
        return self.root / "flows" / "main.flow.json"

    @property
    def data_path(self):
        return self.root / ".pcide" / "data.json"

    def load_data(self):
        from .data import validate_data
        return validate_data(read_json(self.data_path, {"version": 1, "variables": [], "constants": [], "apis": []}))

    def save_data(self, value):
        from .data import DataError, validate_data
        try:
            normalized = validate_data(value)
        except DataError as exc:
            raise ProjectError(str(exc)) from exc
        atomic_write_json(self.data_path, normalized)

    def window_paths(self):
        """Return all independent form files, with main form first."""
        ui = self.root / "ui"
        if not ui.exists():
            return []
        paths = sorted(p for p in ui.rglob("*.form.json") if p.is_file() and not p.is_symlink())
        if self.form_path in paths:
            paths.remove(self.form_path)
            paths.insert(0, self.form_path)
        return paths

    def load_window(self, path_or_name):
        path = Path(path_or_name)
        if not path.is_absolute():
            path = self.root / "ui" / path
        path = path.resolve()
        if not path.is_relative_to((self.root / "ui").resolve()) or path.suffixes[-2:] != [".form", ".json"]:
            raise ProjectError("invalid window path")
        if not path.is_file() or path.is_symlink():
            raise ProjectError("window file missing")
        try:
            return validate_form(read_json(path))
        except (TypeError, AttributeError) as exc:
            raise ProjectError("invalid window file") from exc

    def save_window(self, path_or_name, value):
        path = Path(path_or_name)
        if not path.is_absolute():
            path = self.root / "ui" / path
        path = path.resolve()
        if not path.is_relative_to((self.root / "ui").resolve()) or path.suffixes[-2:] != [".form", ".json"]:
            raise ProjectError("invalid window path")
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, validate_form(value))

    def _project_path(self, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ProjectError("path escapes project")
        return path

    def protected_path_reason(self, value: str | Path) -> str | None:
        """Return a user-facing reason when a project path must not be changed."""
        path = self._project_path(value)
        protected = {
            self.root: "项目根目录",
            self.ide_dir: "项目配置目录",
            self.ide_dir / "project.json": "项目配置文件",
            self.entry_path: "项目入口文件",
            self.form_path: "主窗口",
            self.flow_path: "主流程",
        }
        for target, label in protected.items():
            if path == target.resolve():
                return f"不能修改{label}"
        for required in (self.root / "src", self.root / "ui", self.root / "flows"):
            if path == required.resolve():
                return f"不能删除项目必需目录：{required.name}"
        if path.is_relative_to(self.ide_dir.resolve()):
            return "不能修改项目内部配置"
        return None

    def rename_path(self, value: str | Path, new_name: str) -> Path:
        source = self._project_path(value)
        if not source.exists() or source.is_symlink():
            raise ProjectError("源路径不存在或不受支持")
        reason = self.protected_path_reason(source)
        if reason:
            raise ProjectError(reason)
        if not valid_file_name(new_name):
            raise ProjectError("名称包含非法字符")
        target = source.parent / new_name
        if target.exists() or target.is_symlink():
            raise ProjectError("目标名称已存在")
        source.rename(target)
        return target

    def delete_path(self, value: str | Path) -> Path:
        target = self._project_path(value)
        if not target.exists() or target.is_symlink():
            raise ProjectError("目标路径不存在或不受支持")
        reason = self.protected_path_reason(target)
        if reason:
            raise ProjectError(reason)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return target

    def save_manifest(self):
        from .platform import validate_platform
        self.manifest["platform"] = validate_platform(self.manifest.get("platform"))
        atomic_write_json(self.ide_dir / "project.json", self.manifest)

    @classmethod
    def copy_to(cls, source: str | Path, destination: str | Path):
        """Copy a project after validating symlink and size boundaries."""
        source = Path(source).resolve()
        destination = Path(destination).resolve()
        if not source.is_dir() or source.is_symlink():
            raise ProjectError("项目目录不存在或不受支持")
        if destination.exists() or destination.is_symlink() or destination == source:
            raise ProjectError("目标项目目录已存在")
        files = []
        total = 0
        for path in source.rglob("*"):
            if path.is_symlink():
                raise ProjectError(f"项目包含不允许的符号链接：{path.name}")
            if path.is_file():
                total += path.stat().st_size
                files.append(path)
                if len(files) > MAX_PROJECT_IMPORT_FILES:
                    raise ProjectError("项目文件数量超过导入上限")
                if total > MAX_PROJECT_IMPORT_BYTES:
                    raise ProjectError("项目体积超过导入上限")
        if not (source / ".pcide" / "project.json").is_file():
            raise ProjectError("缺少 .pcide/project.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=False)
        return cls.open(destination)

    def platform_providers(self):
        from .platform import discover_providers
        return discover_providers(self.root)

    def load_form(self):
        return validate_form(read_json(self.form_path, copy.deepcopy(DEFAULT_FORM)))

    def save_form(self, value):
        atomic_write_json(self.form_path, validate_form(value))

    def load_flow(self):
        return read_json(self.flow_path, {"version": 1, "nodes": [], "edges": []})

    def save_flow(self, value):
        from .flow import validate_flow
        atomic_write_json(self.flow_path, validate_flow(value))

    def scripts(self):
        return sorted(p for p in (self.root / "src").rglob("*") if p.is_file() and p.suffix in {".py", ".js", ".ts", ".zhxb"})

    def input_files_for_build(self):
        files = [self.ide_dir / "project.json", self.flow_path]
        ui = self.root / "ui"
        if ui.exists():
            files.extend(p for p in ui.rglob("*.form.json") if p.is_file() and not p.is_symlink())
        for folder in ("src", "plugins", "providers", "resources", "database", "api", "models", "game"):
            directory = self.root / folder
            if directory.exists():
                files.extend(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for path in files:
            if not path.resolve().is_relative_to(self.root) or path.is_symlink():
                raise ProjectError(f"build path escapes project: {path}")
        return [p for p in files if p.is_file()]

    def add_control(self, control_type: str, **kwargs):
        form = self.load_form()
        ids = {c["id"] for c in form["controls"]}
        name = unique_control_name(control_type, ids)
        if control_type not in CONTROL_TYPES:
            raise ProjectError(f"invalid control type: {control_type}")
        properties = control_defaults(control_type)
        properties["text"] = name
        properties.update(kwargs.pop("properties", {}) or {})
        control = ControlModel(id=name, type=control_type, name=name,
                               properties=properties, **kwargs)
        form["controls"].append(control.to_dict())
        self.save_form(form)
        return control

    @classmethod
    def create(cls, paths: Paths, name: str, language="python"):
        if language not in {"python", "javascript", "typescript", "zhxb"}:
            raise ProjectError("unsupported language")
        if not name.strip() or name in {".", ".."} or any(c in name for c in '\\/:*?"<>|'):
            raise ProjectError("invalid project name")
        root = paths.project(name)
        if root.exists() and any(root.iterdir()):
            raise ProjectError("project directory is not empty")
        ext = {"python": "py", "javascript": "js", "typescript": "ts", "zhxb": "zhxb"}[language]
        project = cls(root, {"schema": 1, "name": root.name, "language": language, "entry": f"src/main.{ext}",
                            "modules": [], "execution": {"timeout_seconds": 60, "max_output_lines": 5000},
                            "permissions": ["vision.simulated"], "plugins": []})
        for directory in (".pcide", "src", "ui", "flows", "plugins", "providers", "resources", "database", "api", "models", "game", "vision/dataset"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        if language == "zhxb":
            source = (".版本 2\n.程序集 窗口程序集1\n.子程序 主程序\n输出(\"脚本已就绪\")\n")
        elif language == "python":
            source = ("from pcide.runtime_api import ocr_mock, yolo_mock, ui\n\n"
                      "def on_main_form_load(event=None):\n    print('主窗体已加载')\n\n"
                      "def on_Button1_click(event=None):\n    result = ocr_mock('demo screenshot', 'Hello')\n"
                      "    print(result)\n    print(yolo_mock('demo screenshot'))\n"
                      "    ui.set('Label1', text='事件已执行')\n\n"
                      "if __name__ == '__main__':\n    print('脚本已就绪')\n")
        else:
            source = ("const {ocrMock, yoloMock, ui} = require('pcide');\n"
                      "function on_main_form_load(event) { console.log('主窗体已加载'); }\n"
                      "function on_Button1_click(event) {\n  console.log(ocrMock('screen','Hello'));\n"
                      "  console.log(yoloMock('screen'));\n  ui.set('Label1',{text:'事件已执行'});\n}\n"
                      "console.log('脚本已就绪');\n")
        project.entry_path.write_text(source, encoding="utf-8")
        project.save_manifest()
        form = copy.deepcopy(DEFAULT_FORM)
        if language == "zhxb":
            form["form"]["events"] = {}
        form["controls"] = [ControlModel("Button1", "Button", "Button1", x=30, y=30,
                           properties={"text": "运行事件", "visible": True, "enabled": True},
                           events={"click": "on_Button1_click"}).to_dict(),
                           ControlModel("Label1", "Label", "Label1", x=30, y=85, width=260,
                           properties={"text": "就绪", "visible": True, "enabled": True}).to_dict()]
        if language == "zhxb":
            form["controls"][0]["events"] = {}
        project.save_form(form)
        project.save_flow({"version": 1, "nodes": [
            {"id": "start", "kind": "log", "label": "开始", "position": [30, 30], "config": {"message": "流程已开始"}},
            {"id": "ocr", "kind": "ocr.mock", "label": "OCR", "position": [245, 30], "config": {"text": "demo"}},
            {"id": "yolo", "kind": "yolo.mock", "label": "YOLO", "position": [460, 30], "config": {"label": "button"}}],
            "edges": [["start", "ocr"], ["ocr", "yolo"]]})
        return project

    @classmethod
    def open(cls, path):
        root = Path(path).resolve()
        if not root.is_dir() or root.is_symlink():
            raise ProjectError(f"项目目录不存在或不受支持: {root}")
        manifest = read_json(root / ".pcide" / "project.json")
        if manifest is None:
            raise ProjectError(f"not a PCIDE project: {root}")
        project = cls(root, manifest)
        if not project.entry_path.is_file():
            raise ProjectError("project entry file missing")
        project.load_form()
        from .flow import validate_flow
        validate_flow(project.load_flow())
        return project


def unique_control_name(prefix, ids):
    index = 1
    while f"{prefix}{index}" in ids:
        index += 1
    return f"{prefix}{index}"
