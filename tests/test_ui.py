from __future__ import annotations

import json
import copy
import threading
import time
import unittest

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

