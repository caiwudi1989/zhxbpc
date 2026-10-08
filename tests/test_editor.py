from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPlainTextEdit

from pcide.ui.editor import CodeEditor, _webengine_blocked
from tests.test_core import WorkspaceCase


class EditorBackendTests(unittest.TestCase):
    def test_known_restricted_hosts_choose_native_and_false_flags_do_not(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_webengine_blocked())
            for name in ("PCIDE_DISABLE_WEBENGINE", "PCIDE_NO_WEBENGINE",
                         "CODEX_WINDOWS_SANDBOX_PACKAGE", "CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY",
                         "CODEX_WINDOWS_RESTRICTED_TOKEN", "CI", "GITHUB_ACTIONS"):
                with self.subTest(name=name), patch.dict(os.environ, {name: "1"}):
                    self.assertTrue(_webengine_blocked())
                with self.subTest(name=name, disabled=True), patch.dict(os.environ, {name: "false"}):
                    self.assertFalse(_webengine_blocked())
            for platform in ("offscreen", "minimal"):
                with patch.dict(os.environ, {"QT_QPA_PLATFORM": platform}):
                    self.assertTrue(_webengine_blocked())


class NativeEditorTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        with patch.dict(os.environ, {"PCIDE_EDITOR_BACKEND": "native"}):
            self.editor = CodeEditor(self.paths)
        self.assertIsInstance(self.editor.view, QPlainTextEdit)
        self.assertIsNone(self.editor.profile)

    def tearDown(self):
        self.editor.shutdown()
        self.editor.close()
        self.editor.deleteLater()
        self.app.processEvents()
        super().tearDown()

    def test_save_keeps_raw_chinese_identifiers_and_updates_dirty_state(self):
        project = self.project(source='如果 = "原文"\n返回 = 如果\n')
        self.editor.load(project.entry_path)
        changed = []
        self.editor.changed.connect(changed.append)
        updated = '如果 = "更新"\n返回 = 如果\nprint(返回)\n'
        self.editor.set_value(updated)
        self.assertIn(str(project.entry_path), changed)
        captured = []
        self.editor.capture(lambda: captured.append(True))
        self.assertTrue(captured)
        self.editor.save()
        self.assertEqual(project.entry_path.read_text(encoding="utf-8"), updated)

    def test_switch_navigation_insert_and_close_leave_no_stale_document(self):
        project = self.project(source="value = 1\nsecond = 2\n")
        self.editor.load(project.entry_path)
        positions = []
        self.editor.cursor.connect(lambda path, line: positions.append((path, line)))
        self.editor.goto(2)
        self.assertEqual(positions[-1], (str(project.entry_path), 2))
        self.editor.insert_text("# 注释\n")
        self.assertIn("# 注释", self.editor.documents[str(project.entry_path)])
        other = project.root / "src" / "other.py"
        other.write_text("other = 3\n", encoding="utf-8")
        self.editor.load(other)
        self.assertEqual(self.editor.view.toPlainText(), "other = 3\n")
        self.editor.close_project()
        self.assertEqual(self.editor.view.toPlainText(), "")
        self.assertFalse(self.editor.documents)
        self.assertFalse(self.editor.saved)
        self.assertIsNone(self.editor.path)

    def test_native_find_replace_format_completion_and_breakpoint(self):
        project = self.project(source="value = 1   \nvalue = 1\n")
        self.editor.load(project.entry_path)
        self.editor.set_completion_items([{"label": "value", "kind": "variable"}])
        self.editor.replace("value", "total", replace_all=True)
        self.assertEqual(self.editor.documents[str(project.entry_path)].count("total"), 2)
        self.editor.format_document()
        self.assertTrue(self.editor.documents[str(project.entry_path)].endswith("\n"))
        toggled = []
        self.editor.breakpoint.connect(lambda path, line: toggled.append((path, line)))
        self.editor.goto(2)
        self.editor.toggle_breakpoint_at_cursor()
        self.assertEqual(toggled[-1], (str(project.entry_path), 2))


if __name__ == "__main__":
    unittest.main()
