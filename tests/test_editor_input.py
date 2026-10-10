import json

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pcide.ui.input_probe import exercise_editor_input
import tests.test_ui as ui_tests


class EditorInputTests(ui_tests.UiTests):
    def test_each_routine_pointer_typing_ime_shortcuts_and_save(self):
        source = '\n\n'.join(f'def {name}(event=None):\n    print("BODY_{index}")' for index, name in enumerate(['on_main_form_load', 'on_Button1_click', 'on_Label1_click', 'on_Button2_click'])) + '\n'
        self.window.project.entry_path.write_text(source, encoding='utf-8')
        self.window.editor.close_project()
        self.window.editor.load(self.window.project.entry_path)
        self.window.show_page('code')
        self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'] == source)
        report = exercise_editor_input(self.window)
        self.assertTrue(report['ok'])
        self.assertEqual(len(report['routines']), 4)

    def test_all_collapsed_source_input_opens_visible_editable_body(self):
        window = self.window
        window.show_page('code')
        window.editor.fold_all(True)
        if not window.editor._fallback:
            self.until(lambda: all(item['collapsed'] for item in json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['routines']))
        window.editor.focus_editor()
        self.app.processEvents()
        QTest.qWait(100)
        snapshot = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))
        self.assertFalse(snapshot['readOnly'])
        target = self.app.focusWidget()
        QTest.keyClicks(target, '# AUTO_OPEN_abc123 ')
        self.until(lambda: 'AUTO_OPEN_abc123' in json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'])
        if window.editor._fallback:
            self.assertFalse(window.editor.routine_panel.collapsed.issuperset({window.editor.routine_panel.collapse_key(window.editor.routine_panel.value['sourceName'])}))
        else:
            self.assertTrue(self.javascript("document.querySelector('.view-lines').textContent.includes('AUTO_OPEN_abc123')"))
            self.assertFalse(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['readOnly'])


for _name in dir(ui_tests.UiTests):
    if _name.startswith('test_') and _name not in EditorInputTests.__dict__:
        setattr(EditorInputTests, _name, None)
