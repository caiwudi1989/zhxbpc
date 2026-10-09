from __future__ import annotations

import json
import copy
import threading
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pcide.core.project import Project
from pcide.core.paths import Paths
from pcide.main import MainWindow
from pcide.ui.designer import MIME_CONTROL
from pcide.ui.editor import register_editor_scheme
from pcide.ui.form_runtime import RuntimeForm, RuntimeWindowManager
from tests.test_core import WorkspaceCase


class UiTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):
        register_editor_scheme()
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.window = MainWindow(self.project(), Paths().ensure())
        self.window.show()
        self.until(lambda: self.window.editor.loaded)

    def tearDown(self):
        self.window.dirty = False
        self.window.close()
        self.app.processEvents()
        super().tearDown()

    def until(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(10)
        self.fail("Qt operation did not complete")

    def test_editor_python_projection_regex_is_unicode_safe(self):
        """The Monaco bundle must parse before it can create the code model."""
        source = (Path(__file__).resolve().parents[1] / "src" / "pcide" / "ui" / "editor.html").read_text(encoding="utf-8")
        token_line = next(line for line in source.splitlines() if "const tokens=currentLanguage" in line)
        self.assertNotIn(r"/\#", token_line)
        self.assertIn("const tokens=currentLanguage==='python'?/#", token_line)

    def test_editor_routine_zone_is_after_declaration(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "pcide" / "ui" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("afterLineNumber:index+1", source)
        self.assertIn("editor.setHiddenAreas(hidden)", source)
        self.assertIn("showFoldingControls:'never'", source)
        self.assertIn("lineNumbers:lineNumber=>hiddenLineNumbers.has(lineNumber)?'':String(lineNumber)", source)
        self.assertIn("routine-line-number", source)
        self.assertIn(r"\.子程序\s+", source)
        self.assertIn("if(currentLanguage==='zhxb')return text", source)
        self.assertIn("startupRoutines=Array.isArray(data.startupRoutines)", source)
        self.assertIn("routine-local-name", source)
        self.assertIn("逻辑型(布尔型)", source)

    def test_startup_handler_is_the_only_special_startup_title(self):
        self.assertEqual(self.window._startup_routine_names(), ["on_main_form_load"])
        names = [self.window.routine_list.topLevelItem(i).text(0) for i in range(self.window.routine_list.topLevelItemCount())]
        self.assertEqual(names.count("_启动程序"), 1)
        self.assertIn("on_Button1_click", names)

    def test_startup_title_and_local_variables_persist(self):
        line = self.window.project.entry_path.read_text(encoding="utf-8").splitlines().index("def on_main_form_load(event=None):") + 1
        self.window._save_routine_metadata(str(self.window.project.entry_path), json.dumps({
            "line": line, "name": "软件启动", "sourceName": "on_main_form_load", "startup": True,
            "returnType": "", "public": False, "remark": "启动入口",
            "locals": [{"name": "启动参数", "type": "文本型", "defaultValue": "", "remark": ""}],
        }, ensure_ascii=False))
        saved = self.window._routine_metadata_index()
        value = saved[f"src/main.py:{line}"]
        self.assertEqual(value["name"], "软件启动")
        self.assertEqual(value["locals"][0]["name"], "启动参数")

    def test_visible_code_pane_has_source_and_fitting_routine_tables(self):
        self.window.tabs.setCurrentWidget(self.window.editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.until(lambda: self.window.editor.view.isVisible())
        snapshot = json.loads(self.javascript("JSON.stringify(pcide.snapshot())"))
        self.assertEqual(snapshot["text"], self.window.project.entry_path.read_text(encoding="utf-8"))
        if self.window.editor._fallback:
            return
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-zone').length") >= 2)
        self.assertEqual(self.javascript("JSON.stringify([...document.querySelectorAll('.routine-zone')[0].querySelectorAll('input')].map(x=>x.className))"), '["routine-name","routine-public","routine-remark"]')
        self.assertEqual(self.javascript("document.querySelector('.routine-zone .routine-return').tagName"), "SELECT")
        self.assertTrue(int(self.javascript("document.querySelector('.routine-zone .routine-line-number').textContent")) >= 1)
        layout = json.loads(self.javascript("JSON.stringify([...document.querySelectorAll('.routine-zone')].map(node=>({"
            "zoneBottom:node.getBoundingClientRect().bottom,"
            "bottom:node.lastElementChild.getBoundingClientRect().bottom"
            "})))"))
        self.assertGreaterEqual(len(layout), 2)
        for block in layout:
            self.assertLessEqual(block["bottom"], block["zoneBottom"], block)

    def test_routine_metadata_can_collapse_and_expand(self):
        if self.window.editor._fallback:
            self.skipTest("子程序信息区折叠属于 Monaco 视图")
        self.window.tabs.setCurrentWidget(self.window.editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-toggle').length") >= 2)
        self.javascript("document.querySelector('.routine-toggle').click(); 'clicked'")
        self.until(lambda: self.javascript("document.querySelector('.routine-toggle').textContent") == "▸")
        self.assertEqual(self.javascript("document.querySelector('.routine-content').hidden"), True)
        self.javascript("document.querySelector('.routine-toggle').click(); 'clicked'")
        self.until(lambda: self.javascript("document.querySelector('.routine-toggle').textContent") == "▾")
        self.assertEqual(self.javascript("document.querySelector('.routine-content').hidden"), False)

    def test_routine_public_name_return_and_remark_are_editable(self):
        if self.window.editor._fallback:
            self.skipTest("子程序元数据编辑属于 Monaco 视图")
        self.window.tabs.setCurrentWidget(self.window.editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-zone').length") >= 2)
        self.assertEqual(self.javascript("document.querySelector('.routine-zone .routine-name').tagName"), "INPUT")
        self.assertEqual(self.javascript("document.querySelector('.routine-zone .routine-return').tagName"), "SELECT")
        self.assertEqual(self.javascript("document.querySelector('.routine-zone .routine-remark').tagName"), "INPUT")
        self.assertEqual(self.javascript("document.querySelector('.routine-public').type"), "checkbox")
        self.javascript("const p=document.querySelector('.routine-public'); p.click(); 'ok'")
        self.assertEqual(self.javascript("document.querySelector('.routine-public').checked"), True)
        self.assertEqual(self.javascript("document.querySelector('.routine-return').options.length >= 10"), True)
        self.javascript("const ret=document.querySelector('.routine-return'); ret.value='文本型'; ret.dispatchEvent(new Event('change',{bubbles:true})); 'ok'")
        self.assertEqual(self.javascript("document.querySelector('.routine-return').value"), "文本型")
        self.assertEqual(self.javascript("document.querySelector('.routine-zone .routine-locals') !== null"), True)
        self.assertEqual(self.javascript("getComputedStyle(document.querySelector('.routine-zone')).pointerEvents"), "auto")

    def test_public_routine_is_project_completion_symbol(self):
        other = self.window.project.root / "src" / "other.py"
        other.write_text("def 工具函数():\n    return 1\n", encoding="utf-8")
        self.window._save_routine_metadata(str(other), json.dumps({
            "line": 1, "name": "工具函数", "returnType": "整数型",
            "public": True, "remark": "跨文件调用"
        }, ensure_ascii=False))
        self.assertTrue(any(item["label"] == "工具函数" and item["detail"] == "公开子程序"
                            for item in self.window.editor.completion_items))

    def javascript(self, code):
        values = []
        self.window.editor.page.runJavaScript(code, values.append)
        self.until(lambda: bool(values))
        return values[0]

    def test_monaco_edit_save_models_navigation(self):
        editor = self.window.editor
        snapshot = json.loads(self.javascript("JSON.stringify(pcide.snapshot())"))
        self.assertIn("脚本已就绪", snapshot["text"])
        editor.set_value(snapshot["text"] + "\n# saved by UI test\n")
        saved = []
        self.window.after_save(lambda: saved.append(True))
        self.until(lambda: bool(saved))
        self.assertIn("saved by UI test", self.window.project.entry_path.read_text(encoding="utf-8"))
        second = self.window.project.root / "src/second.py"
        second.write_text("second = 2\n", encoding="utf-8")
        editor.load(second)
        self.assertEqual(json.loads(self.javascript("JSON.stringify(pcide.snapshot())"))["text"], "second = 2\n")
        self.window.goto_event("Button1", "click")
        self.until(lambda: self.window.current_control == "Button1")
        self.assertEqual(editor.path, str(self.window.project.entry_path))
        editor.goto(7)
        self.assertEqual(json.loads(self.javascript("JSON.stringify(pcide.snapshot())"))["position"]["lineNumber"], 7)
        self.window.save_all()
        self.until(lambda: not self.window.dirty)

    def test_designer_drop_move_resize_copy_undo_roundtrip(self):
        designer = self.window.designer
        mime = QMimeData()
        mime.setData(MIME_CONTROL, b"Entry")
        entry = QDragEnterEvent(QPoint(320, 170), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        designer.dragEnterEvent(entry)
        self.assertTrue(entry.isAccepted())
        drop = QDropEvent(QPointF(320, 170), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        designer.dropEvent(drop)
        self.assertIn("Entry1", designer.items_by_id)
        item = designer.items_by_id["Entry1"]
        start = designer.mapFromScene(item.pos() + QPointF(30, 15))
        QTest.mousePress(designer.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(designer.viewport(), start + QPoint(40, 30), 40)
        QTest.mouseRelease(designer.viewport(), Qt.MouseButton.LeftButton, pos=start + QPoint(40, 30))
        self.assertGreaterEqual(item.data["x"], 350)
        start = designer.mapFromScene(item.pos() + QPointF(item.data["width"]-2, item.data["height"]-2))
        width = item.data["width"]
        QTest.mousePress(designer.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(designer.viewport(), start + QPoint(30, 20), 40)
        QTest.mouseRelease(designer.viewport(), Qt.MouseButton.LeftButton, pos=start + QPoint(30, 20))
        self.assertGreater(item.data["width"], width)
        designer.select("Entry1")
        designer.duplicate()
        self.assertIn("Entry2", designer.items_by_id)
        designer.undo()
        self.assertNotIn("Entry2", designer.items_by_id)
        designer.redo()
        self.assertIn("Entry2", designer.items_by_id)
        self.window.save_all()
        self.until(lambda: not self.window.dirty)
        self.assertEqual(Project.open(self.window.project.root).load_form(), designer.form)

    def test_real_click_updates_runtime_control(self):
        self.window.run_script()
        self.until(lambda: any(m["kind"] == "ready" for m in self.window.runner.messages))
        runtime = self.window.runtime_form
        QTest.mouseClick(runtime.widgets["Button1"], Qt.MouseButton.LeftButton)
        self.until(lambda: runtime.widgets["Label1"].text() == "事件已执行")
        self.assertTrue(any(m["kind"] == "event.done" for m in self.window.runner.messages))
        self.window.stop_script()
        self.window.runner.wait()
        self.assertFalse(self.window.runner.active)

    def test_runtime_window_constraints_and_lifecycle(self):
        form = copy.deepcopy(self.window.project.load_form())
        form["form"]["window"].update({"fixed_width": 500, "fixed_height": None})
        width_locked = RuntimeForm(form)
        self.assertEqual((width_locked.minimumWidth(), width_locked.maximumWidth()), (500, 500))
        width_locked.close()
        form["form"]["window"].update({"fixed_width": None, "fixed_height": 300})
        height_locked = RuntimeForm(form)
        self.assertEqual((height_locked.minimumHeight(), height_locked.maximumHeight()), (300, 300))
        height_locked.close()

        secondary = copy.deepcopy(self.window.project.load_form())
        secondary["form"]["title"] = "设置窗口"
        path = self.window.project.root / "ui" / "settings.form.json"
        self.window.project.save_window(path, secondary)
        forms = {str(p.resolve()): self.window.project.load_window(p) for p in self.window.project.window_paths()}
        manager = RuntimeWindowManager(forms, parent=self.window)
        main = manager.open(str(self.window.project.form_path.resolve()))
        settings = manager.open("settings")
        self.assertIs(manager.open("settings.form.json"), settings)
        self.assertEqual(set(manager.windows), set(forms))
        manager.close("settings")
        self.assertNotIn(str(path.resolve()), manager.windows)
        manager.close()
        self.assertFalse(manager.windows)

    def test_runtime_form_window_resize_and_close_events(self):
        form = copy.deepcopy(self.window.project.load_form())
        form["form"]["events"].update({"resize": "on_resize", "close": "on_close"})
        runtime = RuntimeForm(form)
        runtime.show()
        self.app.processEvents()
        events = []
        runtime.event.connect(lambda handler, payload: events.append((handler, payload["event"])))
        runtime.resize(500, 300)
        self.app.processEvents()
        runtime.close()
        self.app.processEvents()
        self.assertIn(("on_resize", "resize"), events)
        self.assertIn(("on_close", "close"), events)
        flags = runtime.windowFlags()
        self.assertTrue(flags & Qt.WindowType.WindowCloseButtonHint)
        self.assertTrue(flags & Qt.WindowType.WindowMinimizeButtonHint)
        self.assertTrue(flags & Qt.WindowType.WindowMaximizeButtonHint)

    def test_designer_shows_window_chrome_and_client_coordinates(self):
        form = copy.deepcopy(self.window.project.load_form())
        form["form"]["window"].update({"minimize": True, "maximize": True})
        self.window.designer.load(form)
        origin = self.window.designer.client_origin()
        item = self.window.designer.items_by_id["Button1"]
        self.assertEqual((item.pos().x(), item.pos().y()), (origin.x() + item.data["x"], origin.y() + item.data["y"]))
        scene = self.window.designer.sceneRect()
        self.assertGreater(scene.height(), form["form"]["height"] + 32)
        self.assertGreater(scene.width(), form["form"]["width"])
        labels = self.window.designer._window_button_labels()
        self.assertEqual(labels[-1], "×")
        self.assertIn("—", labels)
        self.assertIn("□", labels)

    def test_double_click_window_file_stays_in_designer_view(self):
        target = None
        stack = [self.window.project_tree.invisibleRootItem()]
        while stack:
            parent = stack.pop()
            for index in range(parent.childCount()):
                item = parent.child(index)
                if item.text(0) == "main.form.json":
                    target = item
                    break
                stack.append(item)
            if target:
                break
        self.assertIsNotNone(target)
        self.window.open_file(target)
        self.assertIs(self.window.tabs.currentWidget(), self.window.output)
        self.assertEqual(self.window.current_form_path.resolve(), self.window.project.form_path.resolve())

    def test_new_window_is_loaded_in_designer_view(self):
        form = copy.deepcopy(self.window.project.load_form())
        target = self.window.project.root / "ui" / "settings.form.json"
        form["form"]["id"] = "settings"
        form["form"]["title"] = "设置窗口"
        self.window.project.save_window(target, form)
        self.window.switch_window(target)
        self.assertEqual(self.window.current_form_path.resolve(), target.resolve())
        self.assertEqual(self.window.designer.form["form"]["title"], "设置窗口")
        self.assertIs(self.window.tabs.currentWidget(), self.window.output)

    def test_window_menu_exposes_rename_and_delete(self):
        labels = [action.text() for action in self.window.window_menu.actions()]
        self.assertIn("新建窗口", labels)
        self.assertIn("重命名当前窗口", labels)
        self.assertIn("删除当前窗口", labels)

    def test_project_and_editor_menus_expose_lifecycle_actions(self):
        menus = {menu.title(): menu for menu in self.window.menuBar().findChildren(type(self.window.window_menu))}
        project_menu = menus["项目"]
        project_labels = [action.text() for action in project_menu.actions()]
        for label in ("项目另存为", "导入项目", "重命名项目", "关闭项目", "删除项目"):
            self.assertIn(label, project_labels)
        code_menu = menus["代码"]
        code_labels = [action.text() for action in code_menu.actions()]
        self.assertIn("查找替换", code_labels)
        self.assertIn("保存当前文件为", code_labels)

    def test_categorized_toolbox_and_reactive_control_properties(self):
        groups = [self.window.toolbox.topLevelItem(index).text(0) for index in range(self.window.toolbox.topLevelItemCount())]
        self.assertEqual(groups, ["基本组件", "数据与视图", "容器与布局", "高级控件"])
        self.assertGreaterEqual(self.window.toolbox.topLevelItem(3).childCount(), 7)
        self.window.designer.select("Button1")
        self.until(lambda: self.window.current_control == "Button1")
        self.assertIs(self.window.left_catalog.currentWidget(), self.window.properties)
        width = self.window.properties.widgets["width"]
        width.setValue(width.value() + 20)
        expected_width = width.value()
        width.editingFinished.emit()
        self.until(lambda: self.window.designer.items_by_id["Button1"].data["width"] == expected_width)
        text = self.window.properties.widgets["text"]
        text.setText("已修改")
        text.editingFinished.emit()
        self.until(lambda: self.window.designer.items_by_id["Button1"].data["properties"]["text"] == "已修改")

    def test_monaco_typescript_worker_diagnostics(self):
        if self.window.editor._fallback:
            self.skipTest("受限环境使用原生编辑器；Monaco TypeScript worker 需正常桌面验收")
        path = self.window.project.root / "src/diagnostic.ts"
        path.write_text("const value: number = 'invalid';\n", encoding="utf-8")
        self.window.editor.load(path)
        self.javascript("window.pcideDiagnostics=null; monaco.languages.typescript.getTypeScriptWorker().then(factory=>{const model=monaco.editor.getModels().find(m=>m.getLanguageId()==='typescript');return factory(model.uri).then(worker=>worker.getSemanticDiagnostics(model.uri.toString()));}).then(result=>window.pcideDiagnostics=result, error=>window.pcideDiagnostics={error:String(error)}); 'started'")
        result = []
        def found():
            value = self.javascript("JSON.stringify(window.pcideDiagnostics)")
            data = json.loads(value)
            if data is not None:
                result.append(data)
                return True
            return False
        self.until(found, timeout=15)
        self.assertIsInstance(result[0], list, result[0])
        self.assertTrue(any(item["code"] == 2322 for item in result[0]), result[0])


if __name__ == "__main__":
    unittest.main()

