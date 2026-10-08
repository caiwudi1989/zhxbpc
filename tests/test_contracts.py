from __future__ import annotations

import copy
import ast
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pcide.core.data import DataError, generate_code, validate_data
from pcide.core.i18n import IdentifierMap, make_id
from pcide.core.paths import Paths
from pcide.core.project import Project, ProjectError, validate_form
from pcide.core.runtime_api import ui


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="contract-extra-", dir=Paths().ensure().cache))
        self.paths = Paths(self.temp).ensure()

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_data_scopes_api_contract_and_generation(self):
        model = validate_data({
            "variables": [{"name": "用户数", "type": "整数", "scope": "局部", "default": "3"}],
            "constants": [{"name": "版本", "value": "1"}],
            "apis": [{"name": "打开窗口", "library": "user32.dll", "return": "整数", "calling": "stdcall",
                      "permissions": ["ui.window"], "dependencies": ["user32"],
                      "params": [{"name": "句柄", "type": "整数"}]}],
        })
        self.assertEqual({item["scope"] for item in model["variables"]}, {"local"})
        self.assertEqual(model["apis"][0]["calling_convention"], "stdcall")
        self.assertEqual(len(model["apis"][0]["parameters"]), 1)
        for language in ("python", "javascript", "typescript"):
            source = generate_code(model, language)
            self.assertIn("打开窗口", source)
            self.assertIn(model["apis"][0]["id"], source)
        with self.assertRaises(DataError):
            validate_data({"variables": [{"id": "same", "label": "甲"}], "constants": [{"id": "same", "label": "乙"}]})

    def test_generation_literals_follow_declared_types(self):
        model = validate_data({
            "variables": [
                {"id": "text_value", "label": "文本", "type": "文本", "default": "1"},
                {"id": "count", "label": "数量", "type": "整数", "default": "7"},
                {"id": "enabled", "label": "启用", "type": "布尔", "default": "true"},
                {"id": "options", "label": "选项", "type": "对象", "default": '{"mode":"safe"}'},
            ],
            "constants": [{"id": "version", "label": "版本", "type": "文本", "value": "1"}],
        })
        python_source = generate_code(model, "python")
        ast.parse(python_source)
        self.assertIn('text_value: str = \'1\'', python_source)
        self.assertIn("count: int = 7", python_source)
        self.assertIn("enabled: bool = True", python_source)
        self.assertIn("options: dict = {'mode': 'safe'}", python_source)
        javascript_source = generate_code(model, "javascript")
        node = Paths().root / "runtime" / "node" / "node.exe"
        if node.is_file():
            script = self.temp / "generated.js"
            script.write_text(javascript_source, encoding="utf-8")
            result = subprocess.run([str(node), "--check", str(script)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        typescript_source = generate_code(model, "typescript")
        self.assertIn('let text_value: string = "1";', typescript_source)
        self.assertIn("let count: number = 7;", typescript_source)
        self.assertIn("let enabled: boolean = true;", typescript_source)

    def test_chinese_id_mapping_is_bidirectional(self):
        self.assertEqual(make_id("运行按钮", prefix="value", used=("value",)), "value_2")
        mapping = IdentifierMap([{"id": "Button1", "label": "运行按钮"}])
        self.assertEqual(mapping.to_id("运行按钮"), "Button1")
        self.assertEqual(mapping.to_label("Button1"), "运行按钮")
        with self.assertRaises(ValueError):
            mapping.add("Button1", "另一个名称")
        self.assertEqual(ui.open("settings.form.json"), {"kind": "ui.window.open", "window": "settings.form.json"})
        self.assertEqual(ui.close("settings.form.json"), {"kind": "ui.window.close", "window": "settings.form.json"})
        with self.assertRaises(ValueError):
            ui.open("")

    def test_independent_windows_and_layout_contract(self):
        project = Project.create(self.paths, "windows")
        secondary = copy.deepcopy(project.load_form())
        secondary["form"]["title"] = "设置窗口"
        secondary["form"]["window"].update({"fixed_width": 500, "fixed_height": 300, "anchor": "bottom_right", "dock": "none"})
        secondary["controls"][0]["properties"].update({"anchor": "bottom_right", "auto_fill": False})
        project.save_window("settings.form.json", secondary)
        self.assertEqual([path.name for path in project.window_paths()], ["main.form.json", "settings.form.json"])
        self.assertIn("ui/settings.form.json", {path.relative_to(project.root).as_posix() for path in project.input_files_for_build()})
        loaded = project.load_window("settings.form.json")
        self.assertEqual(loaded["form"]["window"]["fixed_width"], 500)
        with self.assertRaises(ProjectError):
            project.load_window("../outside.form.json")
        secondary["form"]["events"].update({"resize": "on_resize", "close": "on_close"})
        self.assertEqual(validate_form(secondary)["form"]["events"]["close"], "on_close")
        invalid = copy.deepcopy(secondary)
        invalid["form"]["window"]["fixed_width"] = 50
        with self.assertRaises(ProjectError):
            validate_form(invalid)
        invalid = copy.deepcopy(secondary)
        invalid["form"]["window"].update({"fixed_width": 900, "max_width": 800})
        with self.assertRaises(ProjectError):
            validate_form(invalid)


if __name__ == "__main__":
    unittest.main()
