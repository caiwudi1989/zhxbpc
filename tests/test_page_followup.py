from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QTreeWidgetItem

from pcide.core.menus import validate_menu
from pcide.ui.form_runtime import RuntimeForm
from pcide.ui.menu_dialog import MenuDialog
import tests.test_ui as ui_tests


def menu_definition():
    return [{"id": "file", "text": "文件", "kind": "menu", "children": [
        {"id": "open", "text": "打开", "handler": "on_menu_open", "shortcut": "Ctrl+O"},
        {"id": "separator", "kind": "separator"},
        {"id": "options", "text": "选项", "kind": "menu", "children": [
            {"id": "checked", "text": "显示信息", "checkable": True, "checked": True, "handler": "on_checked"}]},
    ]}]


class MenuContractTests(unittest.TestCase):
    def test_menu_rejects_duplicate_ids_invalid_nesting_fields_shortcuts_and_states(self):
        invalid = [
            [{"id": "same", "text": "一"}, {"id": "same", "text": "二"}],
            [{"id": "bad", "text": "项", "children": [{"id": "child", "text": "子"}]}],
            [{"id": "bad", "text": "项", "kind": "external"}],
            [{"id": "bad", "text": "项", "execute": "cmd"}],
            [{"id": "bad", "text": "项", "enabled": 1}],
            [{"id": "bad", "text": "项", "checked": True}],
            [{"id": "a", "text": "一", "shortcut": "Ctrl+O"}, {"id": "b", "text": "二", "shortcut": "ctrl+o"}],
            [{"id": "bad", "text": "项", "handler": "x.y"}],
            [{"id": f"item{i}", "text": "项"} for i in range(257)],
        ]
        nested = {"id": "leaf", "text": "项"}
        for index in range(9):
            nested = {"id": f"level{index}", "text": "菜单", "kind": "menu", "children": [nested]}
        invalid.append([nested])
        for value in invalid:
            with self.subTest(value=str(value)[:120]), self.assertRaises(ValueError):
                validate_menu(value)
        self.assertEqual(validate_menu(menu_definition())[0]["children"][2]["children"][0]["handler"], "on_checked")


class PageFollowupUiTests(ui_tests.UiTests):
    def test_hint_page_follows_selected_library_entry_and_export_uses_shared_output(self):
        window = self.window
        pending = [window.support_library.topLevelItem(i) for i in range(window.support_library.topLevelItemCount())]
        leaf = None
        while pending:
            item = pending.pop()
            if (item.data(0, Qt.ItemDataRole.UserRole + 5) or {}).get("code"):
                leaf = item
                break
            pending.extend(item.child(i) for i in range(item.childCount()))
        self.assertIsNotNone(leaf)
        window.support_library.setCurrentItem(leaf)
        code = leaf.data(0, Qt.ItemDataRole.UserRole + 5)["code"]
        self.assertIn(code, window.hint_panel.toPlainText())
        self.assertTrue(window.show_page("hint"))
        self.assertIn(code, window.hint_panel.toPlainText())
        window.log("SHARED_OUTPUT_ONCE")
        target = self.temp / "output.txt"
        with patch("pcide.main.QFileDialog.getSaveFileName", return_value=(str(target), "")):
            window.export_output()
        self.assertEqual(target.read_text(encoding="utf-8").count("SHARED_OUTPUT_ONCE"), 1)
        window.output.clear()
        self.assertEqual(window.output_panel.toPlainText(), "")

    def test_menu_editor_changes_real_tree_values_and_preserves_source_until_acceptance(self):
        original = menu_definition()
        dialog = MenuDialog(original, ["on_menu_open"], self.window)
        dialog.show()
        item = dialog.tree.topLevelItem(0).child(0)
        dialog.tree.setCurrentItem(item)
        dialog.title.setText("打开工程")
        dialog.enabled.setChecked(False)
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        saved = dialog.result_menu[0]["children"][0]
        self.assertEqual(saved["text"], "打开工程")
        self.assertFalse(saved["enabled"])
        self.assertEqual(original, menu_definition())
        dialog.close()

    def test_menu_event_editor_creates_handler_and_saves_source_and_definition(self):
        window = self.window
        identity = window._apply_window_menu("", menu_definition())
        def edit():
            dialog = self.app.activeModalWidget()
            self.assertIsInstance(dialog, MenuDialog)
            dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0).child(0))
            dialog.handler.setCurrentText("on_created_menu_open")
            dialog.edit_event()
        QTimer.singleShot(0, edit)
        window.edit_window_menu(identity)
        entry = str(window.project.entry_path)
        self.assertIn("def on_created_menu_open(event=None):", window.editor.documents[entry])
        window._save_now()
        self.assertIn("def on_created_menu_open(event=None):", window.project.entry_path.read_text(encoding="utf-8"))
        menu = next(c for c in window.project.load_form()["controls"] if c["id"] == identity)["properties"]["menu"]
        self.assertEqual(menu[0]["children"][0]["handler"], "on_created_menu_open")

    def test_menu_save_preview_unsaved_design_and_real_callbacks(self):
        window = self.window
        identity = window._apply_window_menu("", menu_definition())
        window._save_now()
        saved = window.project.load_form()
        self.assertEqual(next(c for c in saved["controls"] if c["id"] == identity)["properties"]["menu"][0]["children"][0]["id"], "open")
        button = next(c for c in window.designer.form["controls"] if c["type"] == "Button")
        window.designer.update_control(button["id"], {"text": "未保存的新文字"})
        with patch.object(window.runner, "event") as event:
            window.preview()
            self.app.processEvents()
            self.assertEqual(window.runtime_form.widgets[button["id"]].text(), "未保存的新文字")
            action = window.runtime_form.widgets[identity].actions()[0].menu().actions()[0]
            action.trigger()
            self.app.processEvents()
            event.assert_not_called()
            window.preview(run_events=True)
            self.app.processEvents()
            action = window.runtime_form.widgets[identity].actions()[0].menu().actions()[0]
            action.trigger()
            self.app.processEvents()
            calls = [call for call in event.call_args_list if call.args[0] == "on_menu_open"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].args[1]["menu_id"], "open")
        self.assertNotEqual(next(c for c in window.project.load_form()["controls"] if c["id"] == button["id"])["properties"]["text"], "未保存的新文字")

    def test_runtime_nested_checkable_disabled_and_updated_menu_actions(self):
        identity = self.window._apply_window_menu("", menu_definition())
        runtime = RuntimeForm(self.window.designer.form)
        calls = []
        runtime.event.connect(lambda handler, payload: calls.append((handler, payload)))
        actions = runtime.widgets[identity].actions()[0].menu().actions()
        self.assertTrue(actions[1].isSeparator())
        checked = actions[2].menu().actions()[0]
        self.assertTrue(checked.isChecked())
        checked.trigger()
        self.assertEqual(calls[-1][0], "on_checked")
        self.assertFalse(calls[-1][1]["checked"])
        replacement = [{"id": "new", "text": "新项目", "handler": "on_new"}]
        runtime.update_control(identity, {"menu": replacement})
        runtime.widgets[identity].actions()[0].trigger()
        self.assertEqual(calls[-1][0], "on_new")
        self.assertEqual(calls[-1][1]["menu_id"], "new")
        runtime.close()

    def test_arrangement_spacing_order_undo_and_saved_geometry(self):
        self.app.processEvents()
        titles = [action.text() for action in self.window.arrange_menu.actions()]
        self.assertIn("左对齐", titles)
        self.assertIn("置于底层", titles)
        designer = self.window.designer
        candidate = copy.deepcopy(designer.form)
        candidate["controls"] = []
        designer.load(candidate)
        identities = [designer.add("Button", x, 30) for x in (10, 240, 390)]
        for index, identity in enumerate(identities):
            designer.update_control(identity, {"width": 50 + index * 10, "height": 24 + index * 4})
        designer.select_all()
        designer.align("height")
        self.assertEqual([c["height"] for c in designer.form["controls"]], [24, 24, 24])
        designer.align("distribute_x")
        controls = designer.form["controls"]
        gaps = [controls[i + 1]["x"] - controls[i]["x"] - controls[i]["width"] for i in range(2)]
        self.assertLessEqual(abs(gaps[0] - gaps[1]), 1)
        designer.select(identities[0])
        designer.change_order(True)
        self.assertEqual(designer.form["controls"][-1]["id"], identities[0])
        designer.undo()
        self.assertEqual(designer.form["controls"][0]["id"], identities[0])
        self.window._save_now()
        self.assertEqual(self.window.project.load_form()["controls"], designer.form["controls"])

    def test_nested_container_canvas_copy_and_detach_preserve_relative_and_visible_positions(self):
        designer = self.window.designer
        parent = designer.add("Frame", 100, 90)
        child = designer.add("Button", 30, 20)
        designer.update_control(child, {"parent": parent})
        items = designer.items_by_id
        self.assertIs(items[child].parentItem(), items[parent])
        position = items[child].scenePos() - designer.client_origin()
        self.assertEqual((position.x(), position.y()), (130, 110))
        designer.select(parent)
        designer.copy_selected()
        designer.paste_controls()
        clones = designer.form["controls"][-2:]
        self.assertEqual((clones[0]["x"], clones[0]["y"]), (120, 110))
        self.assertEqual((clones[1]["x"], clones[1]["y"]), (30, 20))
        self.assertEqual(clones[1]["parent"], clones[0]["id"])
        designer.select(parent)
        designer.delete_selected(confirm=False)
        retained = next(c for c in designer.form["controls"] if c["id"] == child)
        self.assertEqual((retained["parent"], retained["x"], retained["y"]), ("", 130, 110))
        runtime = RuntimeForm(designer.form)
        self.assertEqual((runtime.widgets[child].x(), runtime.widgets[child].y()), (130, 110))
        runtime.close()

    def test_enter_navigation_restores_code_and_rejects_external_call_positions(self):
        window = self.window
        entry = str(window.project.entry_path)
        window.toggle_breakpoint(entry, 3)
        window.show_page("debug")
        window.debug_tabs.setCurrentWidget(window.breakpoint_tree)
        window.breakpoint_tree.setCurrentItem(window.breakpoint_tree.topLevelItem(0))
        window.breakpoint_tree.setFocus()
        self.app.processEvents()
        with patch.object(window.editor, "goto") as goto:
            QTest.keyClick(window.breakpoint_tree, Qt.Key.Key_Return)
            self.app.processEvents()
            goto.assert_called_once_with(3)
        self.assertIs(window.tabs.currentWidget(), window.editor)
        frame = QTreeWidgetItem(window.stack, ["handler", "3"])
        frame.setData(0, Qt.ItemDataRole.UserRole, {"file": entry, "line": 3})
        window.show_page("debug")
        window.debug_tabs.setCurrentWidget(window.stack)
        window.stack.setCurrentItem(frame)
        window.stack.setFocus()
        with patch.object(window.editor, "goto") as goto:
            QTest.keyClick(window.stack, Qt.Key.Key_Return)
            self.app.processEvents()
            goto.assert_called_once_with(3)
        frame.setData(0, Qt.ItemDataRole.UserRole, {"file": str(self.temp.parent / "outside.py"), "line": 3})
        with patch.object(window.editor, "load") as load:
            window.goto_stack(frame, 0)
            load.assert_not_called()


for _name in dir(ui_tests.UiTests):
    if _name.startswith("test_") and _name not in PageFollowupUiTests.__dict__:
        setattr(PageFollowupUiTests, _name, None)
