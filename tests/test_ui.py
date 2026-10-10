from __future__ import annotations

import json
import copy
import threading
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem

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
        self.window.show_page('code')
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

    def test_support_catalog_configuration_search_and_source_admission(self):
        from pcide.ui.library_dialog import LibraryDialog
        from pcide.core.libraries import load_libraries
        window=self.window
        def labels(item):
            return [item.text(0)]+[label for index in range(item.childCount()) for label in labels(item.child(index))]
        names=[label for index in range(window.support_library.topLevelItemCount()) for label in labels(window.support_library.topLevelItem(index))]
        self.assertIn('库定义数据类型',names)
        self.assertIn('库定义常量',names)
        self.assertNotIn('项目数据',names)
        self.assertNotIn('窗口_重绘',names)
        window.support_search.setText('取绝对值')
        self.assertFalse(window.support_library.topLevelItem(0).isHidden())
        self.assertTrue(window.support_library.topLevelItem(1).isHidden())
        dialog=LibraryDialog(window.project,window,page=1)
        dialog.changed.connect(window._libraries_changed)
        source=self.temp/'math.py'
        source.write_text('def answer():\n    return 42\n',encoding='utf-8')
        dialog.source.setText(str(source))
        dialog.identity.setText('计算库')
        dialog.admit()
        self.assertEqual(dialog.example.toPlainText(),'计算库.answer()')
        self.assertIn('计算库.answer',[item['label'] for item in window._completion_items()])
        dialog.system_boxes['system.window'].setChecked(False)
        dialog.save_configuration()
        self.assertEqual(load_libraries(window.project)['system'],['system.core'])
        dialog.close()

    def test_data_groups_show_specific_fields_and_scoped_completion(self):
        window=self.window
        data={'variables':[{'id':'value','label':'窗口值','type':'整数型','scope':'window','owner':'main','default':'2'}],
              'types':[{'id':'Record','label':'记录','members':[]}]}
        window.project.save_data(data)
        window.data_panel.load(data)
        window._refresh_data_summary()
        window.data_panel.select_group('window')
        self.assertFalse(window.data_panel.table.isColumnHidden(10))
        self.assertTrue(window.data_panel.table.isColumnHidden(6))
        self.assertIn('main.value',[item['label'] for item in window._completion_items()])
        window.data_panel.select_group('types')
        self.assertFalse(window.data_panel.table.isColumnHidden(6))
        self.assertTrue(window.data_panel.table.isColumnHidden(4))

    def test_new_variable_dialog_accepts_type_default_owner_and_array(self):
        from PySide6.QtWidgets import QLineEdit, QComboBox
        panel=self.window.data_panel
        panel.select_group('window')
        errors=[]
        def fill():
            dialog=QApplication.activeModalWidget()
            try:
                dialog.findChild(QLineEdit,'label').setText('计数')
                dialog.findChild(QComboBox,'type').setCurrentText('整数型')
                dialog.findChild(QLineEdit,'value').setText('3')
                dialog.findChild(QLineEdit,'array').setText('2,3')
                dialog.findChild(QComboBox,'owner').setCurrentText('main')
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
                if dialog.isVisible():
                    errors.append('data admission was rejected')
                    dialog.reject()
            except Exception as exc:
                errors.append(str(exc))
                dialog.reject()
        QTimer.singleShot(30,fill)
        panel._add('variable')
        self.assertFalse(errors,errors)
        item=self.window.project.load_data()['variables'][0]
        self.assertEqual((item['type'],item['default'],item['array'],item['owner']),('整数型','3','2,3','main'))

    def test_type_members_array_and_combo_after_deleting_middle_row(self):
        from PySide6.QtWidgets import QComboBox, QToolButton
        panel=self.window.data_panel
        panel.load({'types':[{'id':'Record','label':'记录','members':[{'id':name,'label':name,'type':'文本型'} for name in ['a','b','c']]}]})
        panel.select_group('types')
        panel.table.selectRow(0)
        errors=[]
        def fill():
            dialog=QApplication.activeModalWidget()
            try:
                table=dialog.findChild(QTableWidget)
                table.selectRow(1)
                next(button for button in dialog.findChildren(QToolButton) if button.text()=='删除').click()
                table.cellWidget(1,2).setCurrentText('整数型')
                table.item(1,5).setText('2,3')
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
                if dialog.isVisible():
                    errors.append('member dialog rejected input')
                    dialog.reject()
            except Exception as exc:
                errors.append(str(exc))
                dialog.reject()
        QTimer.singleShot(30,fill)
        panel._edit_members()
        self.assertFalse(errors,errors)
        member=self.window.project.load_data()['types'][0]['members'][1]
        self.assertEqual((member['id'],member['type'],member['array']),('c','整数型','2,3'))

    def test_parameter_dialog_updates_real_signature_and_keeps_local_body(self):
        from pcide.ui.parameter_dialog import ParameterDialog
        from pcide.core.routine_signatures import parameter_details
        window=self.window
        source='def work(value: int):\n    local = value + 1\n    return local\n'
        path=window.project.entry_path
        path.write_text(source,encoding='utf-8')
        window.editor.load(path)
        window.editor.set_value(source)
        self.until(lambda: window.editor.documents[str(path)]==source)
        errors=[]
        def fill():
            dialog=QApplication.activeModalWidget()
            if not isinstance(dialog,ParameterDialog):
                QTimer.singleShot(20,fill)
                return
            try:
                dialog.table.item(0,2).setText('4')
                dialog.table.item(0,3).setCheckState(Qt.CheckState.Checked)
                dialog.table.item(0,5).setText('调用输入')
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
                if dialog.isVisible():
                    errors.append(dialog.error.text())
                    dialog.reject()
            except Exception as exc:
                errors.append(str(exc))
                dialog.reject()
        QTimer.singleShot(20,fill)
        window.edit_routine_parameters(str(path),1)
        self.until(lambda:'value: int=4' in path.read_text(encoding='utf-8') or bool(errors))
        self.assertFalse(errors,errors)
        saved=path.read_text(encoding='utf-8')
        self.assertIn('local = value + 1',saved)
        self.assertTrue(parameter_details(saved,'.py','work')[0]['optional'])
        self.assertEqual(next(iter(window._routine_metadata_index().values()))['parameterNotes']['value'],'调用输入')

    def test_shortcuts_have_no_collisions_and_switch_view_without_closing_project(self):
        from PySide6.QtGui import QAction
        actions=self.window.findChildren(QAction)
        seen={}
        for action in actions:
            shortcut=action.shortcut().toString()
            if not shortcut:
                continue
            self.assertNotIn(shortcut,seen,shortcut)
            seen[shortcut]=action
        self.assertEqual(seen['Ctrl+W'].text(),'关闭当前代码页')
        self.assertEqual(seen['Ctrl+Alt+P'].text(),'编辑当前子程序参数')
        self.assertEqual(seen['Del'].shortcutContext(),Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.window.workspace_tabs.setCurrentWidget(self.window.designer)
        self.window.designer.setFocus()
        QTest.keyClick(self.window.designer,Qt.Key.Key_E,Qt.KeyboardModifier.ControlModifier)
        self.until(lambda:self.window.workspace_tabs.currentWidget() is self.window.tabs)
        self.assertFalse(self.window._project_closed)

    def test_dll_import_parameters_are_edited_as_a_table(self):
        from pcide.ui.library_dialog import LibraryDialog
        from PySide6.QtWidgets import QToolButton
        dialog=LibraryDialog(self.window.project,self.window,page=1)
        dialog.dll_entry.setText('example_export')
        errors=[]
        def fill():
            modal=QApplication.activeModalWidget()
            try:
                next(button for button in modal.findChildren(QToolButton) if button.text()=='添加参数').click()
                table=modal.findChild(QTableWidget)
                table.item(0,0).setText('数值')
                table.item(0,1).setText('value')
                table.cellWidget(0,2).setCurrentText('int32')
                modal.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
                if modal.isVisible():
                    errors.append('DLL parameter declaration was rejected')
                    modal.reject()
            except Exception as exc:
                errors.append(str(exc))
                modal.reject()
        QTimer.singleShot(30,fill)
        dialog.edit_dll_parameters()
        self.assertFalse(errors,errors)
        self.assertEqual(json.loads(dialog.parameters.text())[0]['type'],'int32')
        self.assertIn('1 项',dialog.parameter_button.text())
        dialog.close()

    def test_editor_python_projection_regex_is_unicode_safe(self):
        """The Monaco bundle must parse before it can create the code model."""
        source = (Path(__file__).resolve().parents[1] / "src" / "pcide" / "ui" / "editor.html").read_text(encoding="utf-8")
        token_line = next(line for line in source.splitlines() if "const tokens=currentLanguage" in line)
        self.assertNotIn(r"/\#", token_line)
        self.assertIn("const tokens=currentLanguage==='python'?/#", token_line)

    def test_editor_routine_zone_is_after_declaration(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "pcide" / "ui" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("afterLineNumber:index+1", source)
        self.assertIn("editor.setHiddenAreas(merged.map", source)
        self.assertIn("showFoldingControls:'never'", source)
        self.assertIn("lineNumbers:lineNumber=>hiddenLineNumbers.has(lineNumber)?'':String(lineNumber)", source)
        self.assertIn("routine-line-number", source)
        self.assertIn(r"\.子程序\s+", source)
        self.assertIn("if(currentLanguage!=='python')return text", source)
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

    def test_startup_title_stays_editable_and_tree_uses_custom_label(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "pcide" / "ui" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("name.readOnly=false", source)
        self.assertIn("name.disabled=false", source)
        self.assertNotIn("routine-name.locked", source)
        line = self.window.project.entry_path.read_text(encoding="utf-8").splitlines().index("def on_main_form_load(event=None):") + 1
        self.window._save_routine_metadata(str(self.window.project.entry_path), json.dumps({
            "line": line, "name": "软件启动", "sourceName": "on_main_form_load", "startup": True,
            "returnType": "", "public": False, "remark": "", "locals": []
        }, ensure_ascii=False))
        saved = self.window._routine_metadata_index()
        self.assertIn(f"src/main.py:{line}", saved)
        self.assertEqual(self.window.routine_list.topLevelItem(0).text(0), "软件启动")
        self.assertEqual(self.window.routine_list.topLevelItem(0).text(1), f"第 {line} 行")
        self.assertEqual(self.window._startup_routine_names(), ["on_main_form_load"])

    def test_program_data_table_rename_and_delete_are_stable(self):
        data = {"version": 1, "variables": [{"id": "count", "label": "数量", "type": "整数", "default": "1", "scope": "global"}],
                "constants": [], "apis": [], "types": []}
        self.window.data_panel.load(data)
        self.window.data_panel.select_group("global")
        self.window.data_panel.table.item(0, 1).setText("total_count")
        self.until(lambda: self.window.project.load_data()["variables"][0]["id"] == "total_count")
        self.window.data_panel.table.selectRow(0)
        self.window.data_panel._delete()
        self.assertEqual(self.window.project.load_data()["variables"], [])

    def test_toolbox_menu_and_display_modes(self):
        menu = self.window.toolbox.menu(self.window)
        self.assertGreaterEqual(len(menu.actions()), 4)
        self.window.toolbox.set_display_mode("icon")
        self.assertEqual(self.window.toolbox._display_mode, "icon")
        self.assertFalse(self.window.toolbox.topLevelItem(0).child(0).icon(0).isNull())
        self.window.toolbox.set_display_mode("text")
        self.assertTrue(self.window.toolbox.topLevelItem(0).child(0).icon(0).isNull())

    def test_program_data_switches_project_save_target_and_navigation(self):
        old = self.window.project
        new = self.project('second')
        self.window._switch(new)
        self.window.data_panel.load({'variables': [{'id': 'count', 'label': '数量', 'type': '整数型', 'default': '1', 'scope': 'global'}]})
        self.window.data_panel.select_group('global')
        self.window.data_panel.table.item(0, 4).setText('2')
        self.assertEqual(new.load_data()['variables'][0]['default'], '2')
        self.assertEqual(old.load_data()['variables'], [])
        self.assertIs(self.window.data_panel.project, new)
        self.assertTrue(any(item['label'] == 'count' for item in self.window._completion_items()))
        self.window.data_panel.table.item(0, 4).setText('invalid')
        self.assertEqual(self.window.data_panel.table.item(0, 4).text(), '2')
        section = next(self.window.project_tree.topLevelItem(index) for index in range(self.window.project_tree.topLevelItemCount())
                       if self.window.project_tree.topLevelItem(index).text(0) == '变量 / 常量')
        self.window._open_program_item(section.child(0).child(0))
        self.assertIs(self.window.tabs.currentWidget(), self.window.data_panel)
        self.assertEqual(self.window.data_panel.table.currentRow(), 0)

    def test_native_routine_edit_save_local_scope_and_ordinary_rename(self):
        if not self.window.editor._fallback:
            self.skipTest('native procedure table')
        panel = self.window.editor.routine_panel
        self.assertFalse(panel.name.isReadOnly())
        panel.name.setText('软件启动')
        panel.publish()
        self.assertEqual(self.window._routine_metadata_index()[f'src/main.py:{panel.value["line"]}']['name'], '软件启动')
        self.assertEqual(self.window._startup_routine_names(), ['on_main_form_load'])
        panel.add_local()
        panel.locals.item(0, 0).setText('专属变量')
        self.assertFalse(any(item['label'] == '专属变量' for item in self.window._completion_items()))
        original = self.window.editor.documents[self.window.editor.path]
        self.assertIn('def on_main_form_load', original)
        self.assertEqual(self.window.editor.view.toPlainText(), original)
        declaration = original.splitlines().index('def on_main_form_load(event=None):')
        self.assertFalse(self.window.editor.view.document().findBlockByNumber(declaration).isVisible())
        self.window._save_now()
        self.window.editor.load(self.window.project.entry_path)
        self.assertEqual(panel.name.text(), '软件启动')
        second = panel.selector.findData('on_Button1_click')
        panel.selector.setCurrentIndex(second)
        panel.name.setText('on_run_click')
        panel.publish()
        self.assertIn('def on_run_click', self.window.editor.documents[self.window.editor.path])
        self.assertEqual(self.window.designer.form['controls'][0]['events']['click'], 'on_run_click')
        self.window._save_now()
        self.assertIn('def on_run_click', self.window.project.entry_path.read_text(encoding='utf-8'))
        self.assertEqual(self.window.project.load_form()['controls'][0]['events']['click'], 'on_run_click')

    def test_toolbox_menu_adds_actual_control_and_secondary_load_is_not_startup(self):
        menu = self.window.toolbox.menu(self.window)
        action = menu.actions()[0].menu().actions()[0]
        before = len(self.window.designer.form['controls'])
        action.trigger()
        self.assertEqual(len(self.window.designer.form['controls']), before+1)
        self.assertEqual(self.window.designer.form['controls'][-1]['type'], action.data())
        secondary = copy.deepcopy(self.window.project.load_form())
        secondary['form']['events']['load'] = 'on_secondary_load'
        self.window.project.save_window('secondary.form.json', secondary)
        self.window.current_form_path = self.window.project.root / 'ui/secondary.form.json'
        self.window.designer.load(secondary)
        self.assertEqual(self.window._startup_routine_names(), ['on_main_form_load'])

    def test_type_member_dialog_saves_structured_members(self):
        panel = self.window.data_panel
        panel.load({'types':[{'id':'Record','label':'记录','members':[]}]})
        panel.select_group('types')
        panel.table.selectRow(0)
        errors = []
        def fill():
            dialog = QApplication.activeModalWidget()
            try:
                self.assertIsInstance(dialog,QDialog)
                table = dialog.findChild(QTableWidget)
                table.setRowCount(1)
                for column, value in enumerate(['文本','text','文本型','hello','成员备注']):
                    table.setItem(0,column,QTableWidgetItem(value))
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            except Exception as exc:
                errors.append(str(exc))
                if dialog:
                    dialog.reject()
        def escape():
            dialog = QApplication.activeModalWidget()
            if dialog:
                errors.append('member dialog did not accept')
                dialog.reject()
        QTimer.singleShot(20,fill)
        QTimer.singleShot(1500,escape)
        panel._edit_members()
        self.assertFalse(errors,errors)
        member = self.window.project.load_data()['types'][0]['members'][0]
        self.assertEqual(member['id'],'text')
        self.assertEqual(member['default'],'hello')
        self.assertEqual(member['description'],'成员备注')

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
        self.assertTrue(int(self.javascript("document.querySelector('.routine-gutter .routine-line-number').textContent")) >= 1)
        metrics = ("JSON.stringify([...document.querySelectorAll('.routine-zone')].map(node=>({"
            "zoneBottom:node.getBoundingClientRect().bottom,"
            "bottom:node.querySelector('.routine-frame').getBoundingClientRect().bottom"
            "})))")
        # WebEngine applies ResizeObserver/view-zone measurements on the next frame.
        # The DOM can exist before those geometry updates, especially during builds.
        self.until(lambda: all(0 <= block['zoneBottom'] - block['bottom'] <= 6
                               for block in json.loads(self.javascript(metrics))))
        layout = json.loads(self.javascript(metrics))
        self.assertGreaterEqual(len(layout), 2)
        for block in layout:
            self.assertLessEqual(block["bottom"], block["zoneBottom"], block)
            self.assertLessEqual(block["zoneBottom"] - block["bottom"], 6, block)

    def test_routine_layout_is_compact_resizes_and_preserves_edits(self):
        if self.window.editor._fallback:
            self.skipTest('Monaco inline procedure geometry')
        self.window.tabs.setCurrentWidget(self.window.editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-zone').length") >= 2)
        metrics = "JSON.stringify((()=>{const n=document.querySelector('.routine-zone');return {height:n.getBoundingClientRect().height,frame:n.querySelector('.routine-frame').getBoundingClientRect().height,widths:[...n.querySelectorAll('table:not([hidden])')].map(t=>t.getBoundingClientRect().width),toggleInName:n.querySelector('.routine-name-cell').contains(n.querySelector('.routine-toggle')),duplicateTitles:n.querySelectorAll('.routine-bar').length};})())"
        self.until(lambda: 0 <= json.loads(self.javascript(metrics))['height'] - json.loads(self.javascript(metrics))['frame'] <= 6)
        initial = json.loads(self.javascript(metrics))
        self.assertTrue(initial['toggleInName'])
        self.assertEqual(initial['duplicateTitles'], 0)
        self.assertLessEqual(max(initial['widths'])-min(initial['widths']), 1)
        point = json.loads(self.javascript("JSON.stringify((()=>{const r=document.querySelector('.routine-name').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})())"))
        view = self.window.editor.view
        self.javascript("window.pcideMouse=[];document.addEventListener('mousedown',e=>window.pcideMouse.push({x:e.clientX,y:e.clientY,target:e.target.className}),true);'ok'")
        target = view.focusProxy() or view
        # WebEngine's render delegate consumes viewport coordinates directly.
        click_point = QPoint(round(point['x']),round(point['y']))
        QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=click_point)
        QTest.qWait(100)
        self.assertEqual(self.javascript("document.activeElement.className"), 'routine-name',
                         {'point':point,'events':self.javascript('JSON.stringify(window.pcideMouse)'),
                          'hit':self.javascript(f"document.elementFromPoint({point['x']},{point['y']})?.className")})
        QTest.keyClick(target, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(target, 'launch_label')
        QTest.keyClick(target, Qt.Key.Key_Tab)
        self.until(lambda: self.javascript("document.querySelector('.routine-name').value") == 'launch_label')
        self.until(lambda: any(item['name']=='launch_label' for item in self.window._routine_metadata_index().values()))
        self.javascript("document.querySelector('.routine-remark').value='saved remark';document.querySelector('.routine-remark').dispatchEvent(new Event('input',{bubbles:true}));'ok'")
        for index in range(3):
            self.javascript("document.querySelector('.routine-add-local').click();'ok'")
            self.javascript(f"(()=>{{const r=document.querySelector('.routine-locals tbody').lastElementChild;r.querySelector('.routine-local-name').value='local_{index}';r.querySelector('.routine-local-name').dispatchEvent(new Event('input',{{bubbles:true}}));}})();'ok'")
        self.until(lambda: json.loads(self.javascript(metrics))['height'] > initial['height'] + 60)
        populated = json.loads(self.javascript(metrics))
        self.assertLessEqual(populated['height']-populated['frame'], 6)
        self.assertLessEqual(max(populated['widths'])-min(populated['widths']), 1)
        self.javascript("document.querySelector('.routine-toggle').click();'ok'")
        self.until(lambda: json.loads(self.javascript(metrics))['height'] < 40)
        self.javascript("document.querySelector('.routine-toggle').click();'ok'")
        self.until(lambda: json.loads(self.javascript(metrics))['height'] > initial['height'] + 60)
        self.assertEqual(self.javascript("document.querySelector('.routine-name').value"), 'launch_label')
        self.assertEqual(self.javascript("document.querySelector('.routine-remark').value"), 'saved remark')
        original_source = self.window.project.entry_path.read_text(encoding='utf-8')
        self.window.editor.set_value('\n' + original_source)
        self.until(lambda: self.javascript("document.querySelector('.routine-name')?.value") == 'launch_label')
        self.assertEqual(self.javascript("document.querySelectorAll('.routine-zone')[0].querySelectorAll('.routine-local-name').length"), 3)
        for _ in range(3):
            self.javascript("document.querySelector('.routine-remove-local').click();'ok'")
        self.until(lambda: abs(json.loads(self.javascript(metrics))['height']-initial['height']) <= 2)
        self.window.editor.set_value(original_source)
        self.until(lambda: self.javascript("document.querySelector('.routine-name')?.value") == 'launch_label')
        self.assertEqual(self.javascript("document.querySelectorAll('.routine-zone')[0].querySelectorAll('.routine-local-name').length"), 0)
        other = self.window.project.root / 'src/switch.py'
        other.write_text('value=1\n',encoding='utf-8')
        self.window.editor.load(other)
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-zone').length") == 0)
        self.window.editor.load(self.window.project.entry_path)
        self.until(lambda: self.javascript("document.querySelector('.routine-name')?.value") == 'launch_label')
        self.assertEqual(self.javascript("document.querySelector('.routine-remark').value"), 'saved remark')
        self.assertEqual(self.window.project.load_form()['form']['events']['load'], 'on_main_form_load')
        snapshot = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))
        self.assertEqual(snapshot['text'],self.window.project.entry_path.read_text(encoding='utf-8'))

    def test_routine_metadata_can_collapse_and_expand(self):
        if self.window.editor._fallback:
            self.skipTest("子程序信息区折叠属于 Monaco 视图")
        self.window.tabs.setCurrentWidget(self.window.editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.until(lambda: self.javascript("document.querySelectorAll('.routine-toggle').length") >= 2)
        original = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text']
        body_line = original.splitlines().index('def on_main_form_load(event=None):')+2
        self.until(lambda: '主窗体已加载' in self.javascript("document.querySelector('.view-lines').textContent"))
        self.javascript("document.querySelector('.routine-toggle').click(); 'clicked'")
        self.until(lambda: self.javascript("document.querySelector('.routine-toggle').textContent") == "▸")
        self.assertEqual(self.javascript("document.querySelector('.routine-content').hidden"), True)
        self.until(lambda: '主窗体已加载' not in self.javascript("document.querySelector('.view-lines').textContent"))
        snapshot = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))
        self.assertIn(body_line, snapshot['hiddenLines'])
        self.assertEqual(snapshot['text'], original)
        self.assertIn('ocr_mock', self.javascript("document.querySelector('.view-lines').textContent"))
        self.javascript("document.querySelectorAll('.routine-toggle')[1].click();'ok'")
        self.until(lambda: 'ocr_mock' not in self.javascript("document.querySelector('.view-lines').textContent"))
        self.until(lambda: '脚本已就绪' not in self.javascript("document.querySelector('.view-lines').textContent"))
        self.assertEqual(self.javascript("document.querySelectorAll('.routine-name').length"), 2)
        self.javascript("document.querySelector('.routine-toggle').click(); 'clicked'")
        self.until(lambda: self.javascript("document.querySelector('.routine-toggle').textContent") == "▾")
        self.assertEqual(self.javascript("document.querySelector('.routine-content').hidden"), False)
        self.until(lambda: '主窗体已加载' in self.javascript("document.querySelector('.view-lines').textContent"))
        self.until(lambda: '脚本已就绪' in self.javascript("document.querySelector('.view-lines').textContent"))
        self.assertNotIn('ocr_mock', self.javascript("document.querySelector('.view-lines').textContent"))
        self.window.editor.save()
        self.assertEqual(self.window.project.entry_path.read_text(encoding='utf-8'),original)

    def test_control_double_click_enters_expanded_routine_body(self):
        editor = self.window.editor
        source = editor.documents[editor.path]
        declaration = source.splitlines().index('def on_Button1_click(event=None):')+1
        if editor._fallback:
            panel = editor.routine_panel
            panel.selector.setCurrentIndex(panel.selector.findData('on_Button1_click'))
            panel.collapse()
        else:
            self.window.tabs.setCurrentWidget(editor)
            self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
            self.until(lambda: self.javascript("document.querySelectorAll('.routine-toggle').length") == 2)
            self.javascript("document.querySelectorAll('.routine-toggle')[1].click();'ok'")
        self.window.tabs.setCurrentWidget(self.window.designer)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        designer = self.window.designer
        item = designer.items_by_id['Button1']
        point = designer.mapFromScene(item.pos()+QPointF(20,15))
        QTest.mouseDClick(designer.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.until(lambda: self.window.tabs.currentWidget() is editor)
        self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['position']['lineNumber'] == declaration+1)
        snapshot = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))
        self.assertEqual(snapshot['text'],source)
        if editor._fallback:
            self.assertTrue(editor.view.document().findBlockByNumber(declaration).isVisible())
            self.assertTrue(editor.view.hasFocus())
            self.assertNotIn(panel.collapse_key('on_Button1_click'),panel.collapsed)
        else:
            self.assertFalse(snapshot['routines'][1]['collapsed'])
            self.assertNotIn(declaration+1,snapshot['hiddenLines'])
            self.until(lambda: 'ocr_mock' in self.javascript("document.querySelector('.view-lines').textContent"))
            self.assertGreater(snapshot['position']['column'],1)

    def test_typing_and_newlines_preserve_routine_widgets(self):
        editor = self.window.editor
        self.window.tabs.setCurrentWidget(editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        self.window.goto_event('Button1','click')
        self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['position']['lineNumber'] == 7)
        if editor._fallback:
            panel = editor.routine_panel
            rendered = panel._render_signature
            panel.return_type.setProperty('preserved',True)
            target = editor.view
        else:
            self.javascript("window.preservedZones=[...document.querySelectorAll('.routine-zone')];window.zoneMutations=0;window.zoneObserver=new MutationObserver(records=>{for(const r of records)for(const n of [...r.addedNodes,...r.removedNodes])if(n.nodeType===1&&(n.matches('.routine-zone')||n.querySelector('.routine-zone')))window.zoneMutations++;});window.zoneObserver.observe(document.querySelector('.view-zones'),{childList:true,subtree:true});'ok'")
            target = editor.view.focusProxy() or editor.view
        QTest.keyClick(target,Qt.Key.Key_End)
        QTest.keyClicks(target,' # typed')
        QTest.keyClick(target,Qt.Key.Key_Return)
        QTest.keyClicks(target,'# new line')
        QTest.qWait(500)
        snapshot = json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))
        self.assertIn('# typed',snapshot['text'])
        self.assertIn('# new line',snapshot['text'])
        if editor._fallback:
            self.assertEqual(panel._render_signature,rendered)
            self.assertTrue(panel.return_type.property('preserved'))
            self.assertTrue(editor.view.hasFocus())
        else:
            self.assertEqual(self.javascript('window.zoneMutations'),0)
            self.assertTrue(self.javascript("window.preservedZones.every((n,i)=>n===document.querySelectorAll('.routine-zone')[i]&&n.isConnected)"))
            self.assertTrue(self.javascript("window.preservedZones.every(n=>n.getBoundingClientRect().height>=50)"))
            self.assertTrue(self.javascript("document.activeElement.classList.contains('inputarea')"))
            self.javascript('window.zoneObserver.disconnect();\'ok\'')

    def test_routine_code_ranges_in_all_editor_languages(self):
        fixtures = {
            '.py': 'def first(event=None):\n    if True:\n        print("FIRST_BODY")\n    note = """text\nnot_a_top_level_statement\n"""\n\ndef second(event=None):\n    print("SECOND_BODY")\n\nprint("TOP_LEVEL")\n',
            '.js': 'function first(event) {\n    const note = `} template {`; // }\n    const regex = /[{}]/;\n    console.log("FIRST_BODY");\n}\nfunction second(event) {\n    console.log("SECOND_BODY");\n}\nconsole.log("TOP_LEVEL");\n',
            '.ts': 'function first(event: unknown) {\n    const note: string = "}"; /* { */\n    console.log("FIRST_BODY");\n}\nfunction second(event: unknown) {\n    console.log("SECOND_BODY");\n}\nconsole.log("TOP_LEVEL");\n',
            '.zhxb': '.版本 2\n.程序集 main\n.子程序 first\n输出("FIRST_BODY")\n.子程序 second\n输出("SECOND_BODY")\n',
        }
        for suffix, source in fixtures.items():
            with self.subTest(suffix=suffix):
                path = self.window.project.root / ('src/range'+suffix)
                path.write_text(source,encoding='utf-8')
                self.window.editor.load(path)
                editor = self.window.editor
                self.window.tabs.setCurrentWidget(editor)
                self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
                if editor._fallback:
                    panel = editor.routine_panel
                    panel.selector.setCurrentIndex(panel.selector.findData('second'))
                    second = next(r for r in panel.routines if r['sourceName']=='second')
                    panel.collapse()
                    self.assertFalse(editor.view.document().findBlockByNumber(second['bodyLine']-1).isVisible())
                    panel.collapse()
                    self.assertTrue(editor.view.document().findBlockByNumber(second['bodyLine']-1).isVisible())
                else:
                    self.until(lambda: self.javascript("document.querySelectorAll('.routine-name').length") == 2)
                    self.javascript("document.querySelectorAll('.routine-toggle')[0].click();document.querySelectorAll('.routine-toggle')[1].click();'ok'")
                    self.until(lambda: 'SECOND_BODY' not in self.javascript("document.querySelector('.view-lines').textContent"))
                    self.assertNotIn('FIRST_BODY',self.javascript("document.querySelector('.view-lines').textContent"))
                    if suffix!='.zhxb':
                        self.assertIn('TOP_LEVEL',self.javascript("document.querySelector('.view-lines').textContent"))
                    self.javascript("document.querySelectorAll('.routine-toggle')[1].click();'ok'")
                    self.until(lambda: 'SECOND_BODY' in self.javascript("document.querySelector('.view-lines').textContent"))
                    self.assertNotIn('FIRST_BODY',self.javascript("document.querySelector('.view-lines').textContent"))
                self.assertEqual(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'],source)

    def test_startup_collapse_owns_file_initialization_and_separators(self):
        fixtures = {
            '.py': 'value = 1\n\ndef on_main_form_load(event=None):\n    print("LOAD_BODY")\n\ndef click(event=None):\n    print("CLICK_BODY")\n\nif __name__ == "__main__":\n    print("FILE_STARTUP")\n\n\n',
            '.js': 'const value = 1;\nfunction on_main_form_load(event) {\n    console.log("LOAD_BODY");\n}\nfunction click(event) {\n    console.log("CLICK_BODY");\n}\nconsole.log("FILE_STARTUP");\n\n',
            '.ts': 'const value: number = 1;\nfunction on_main_form_load(event: unknown) {\n    console.log("LOAD_BODY");\n}\nfunction click(event: unknown) {\n    console.log("CLICK_BODY");\n}\nconsole.log("FILE_STARTUP");\n\n',
        }
        editor = self.window.editor
        self.window.tabs.setCurrentWidget(editor)
        self.window.workspace_tabs.setCurrentWidget(self.window.tabs)
        cases = [(suffix, source, trailing) for suffix, source in fixtures.items() for trailing in (True, False)]
        visible = "getComputedStyle(document.querySelector('.view-lines')).visibility==='hidden'?'':document.querySelector('.view-lines').textContent"
        for suffix, fixture, trailing in cases:
            source = fixture if trailing else fixture.rstrip('\n')
            with self.subTest(suffix=suffix,trailing_newline=trailing):
                path = self.window.project.root / ('src/startup_scope_'+str(trailing)+suffix)
                path.write_text(source,encoding='utf-8')
                editor.load(path)
                if editor._fallback:
                    panel = editor.routine_panel
                    self.assertEqual(panel.value['sourceName'],'on_main_form_load')
                    startup_line = next(i for i,line in enumerate(source.splitlines()) if 'FILE_STARTUP' in line)
                    self.assertTrue(editor.view.document().findBlockByNumber(startup_line).isVisible())
                    panel.collapse()
                    self.assertFalse(editor.view.document().findBlockByNumber(startup_line).isVisible())
                    self.assertFalse(editor.view.isReadOnly())
                    panel.collapse()
                    self.assertTrue(editor.view.document().findBlockByNumber(startup_line).isVisible())
                    self.assertFalse(editor.view.isReadOnly())
                else:
                    self.until(lambda: 'FILE_STARTUP' in self.javascript(visible))
                    self.javascript("document.querySelectorAll('.routine-toggle[aria-expanded=\"true\"]').forEach(button=>button.click());'ok'")
                    self.until(lambda: self.javascript(visible) == '')
                    self.until(lambda: self.javascript("[...document.querySelectorAll('.routine-zone')].every(n=>n.getBoundingClientRect().height>=30)"))
                    positions = json.loads(self.javascript("JSON.stringify([...document.querySelectorAll('.routine-zone')].map(n=>({top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom})))"))
                    self.assertAlmostEqual(positions[0]['bottom'],positions[1]['top'],delta=2)
                    self.assertEqual(self.javascript("document.querySelectorAll('.routine-name').length"),2)
                    # Folding must not lock the whole source document.
                    self.assertFalse(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['readOnly'])
                    self.assertEqual(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'],source)
                    self.javascript("document.querySelector('.routine-toggle').click();'ok'")
                    self.until(lambda: 'FILE_STARTUP' in self.javascript(visible))
                    self.assertNotIn('CLICK_BODY',self.javascript(visible))
                self.assertEqual(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'],source)
                editor.save()
                self.assertEqual(path.read_text(encoding='utf-8'),source)

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

