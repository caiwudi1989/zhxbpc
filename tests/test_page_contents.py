from __future__ import annotations

import ast
import copy
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem

import tests.test_ui as ui_tests
from pcide.core.api_center import ApiError, generate_client_module
from pcide.core.database import create_schema
from pcide.core.development import create_project
from pcide.core.flow import FlowRunner
from pcide.core.project import ControlModel, Project
from pcide.ui.configuration_dialogs import EnvironmentDialog, PlatformCapabilitiesDialog
from pcide.ui.flow_canvas import FlowNodeDialog
from pcide.ui.platform_dialogs import ApiCenterDialog, DatabaseDesignerDialog


class PageContentsUiTests(ui_tests.UiTests):
    def test_closed_pages_reopen_from_view_menu_and_share_one_output_document(self):
        window = self.window
        for key in ('code', 'flow', 'debug', 'data', 'resources', 'vision'):
            widget, tabs, _, _ = window.pages[key]
            window._close_code_tab(tabs.indexOf(widget))
            self.assertFalse(tabs.isTabVisible(tabs.indexOf(widget)))
            window.page_actions[key].trigger()
            self.assertTrue(tabs.isTabVisible(tabs.indexOf(widget)))
            self.assertIs(tabs.currentWidget(), widget)
        window.log('ONE_LOG_RECORD')
        self.assertIs(window.output.document(), window.output_panel.document())
        self.assertEqual(window.output_panel.toPlainText().count('ONE_LOG_RECORD'), 1)

    def test_native_project_hides_script_and_window_pages_and_actions(self):
        project = create_project(self.paths, 'NativePageModes', 'cpp-console')
        self.window._switch(project)
        window = self.window
        for key in ('design', 'properties', 'debug', 'flow', 'data', 'vision'):
            widget, tabs, _, _ = window.pages[key]
            self.assertFalse(tabs.isTabVisible(tabs.indexOf(widget)), key)
            self.assertFalse(window.page_actions[key].isEnabled(), key)
            self.assertFalse(window.show_page(key))
        self.assertFalse(window.debug_action.isEnabled())
        self.assertFalse(window.preview_action.isEnabled())
        self.assertFalse(window.design_menu.isEnabled())
        self.assertTrue(window.right_tabs.isHidden())
        self.assertTrue(window.page_actions['resources'].isEnabled())
        self.assertTrue(window.page_actions['snippets'].isEnabled())
        self.assertIs(window.left_catalog.currentWidget(), window.snippet_host)
        roots = [window.project_tree.topLevelItem(i).text(0) for i in range(window.project_tree.topLevelItemCount())]
        self.assertNotIn('变量 / 常量', roots)
        self.assertNotIn('子程序', roots)

    def test_window_geometry_changes_save_at_form_level(self):
        window = self.window
        window.select_control('')
        window.properties.widgets['width'].setValue(930)
        window.properties.widgets['width'].editingFinished.emit()
        window.select_control('')
        window.properties.widgets['height'].setValue(530)
        window.properties.widgets['height'].editingFinished.emit()
        window.save_all()
        self.until(lambda: window.project.load_form()['form']['height'] == 530)
        form = window.project.load_form()['form']
        self.assertEqual(form['width'], 930)
        self.assertNotIn('width', form['window'])
        self.assertNotIn('height', form['window'])

    def test_control_events_match_runtime_and_selector_tracks_selection(self):
        window = self.window
        label = window.designer.add('Label')
        progress = window.designer.add('ProgressBar')
        window.select_control(label)
        self.assertNotIn('change', window.properties.event_widgets)
        self.assertNotIn('close', window.properties.event_widgets)
        self.assertIn('resize', window.properties.event_widgets)
        selector = window.properties.control_selector
        selector.setCurrentIndex(selector.findData(progress))
        selector.activated.emit(selector.currentIndex())
        self.assertEqual(window.current_control, progress)
        self.assertIn('change', window.properties.event_widgets)
        from pcide.ui.form_runtime import RuntimeForm
        form = copy.deepcopy(window.designer.form)
        next(item for item in form['controls'] if item['id'] == progress)['events']['change'] = 'progress_changed'
        runtime = RuntimeForm(form)
        events = []
        runtime.event.connect(lambda name, data: events.append((name, data)))
        runtime.widgets[progress].setValue(60)
        self.assertEqual(events[-1][0], 'progress_changed')
        runtime.close()

    def test_chinese_handlers_appear_and_dropdown_selection_persists(self):
        project = create_project(self.paths, 'ChineseHandlers', 'zhxb-form')
        project.entry_path.write_text(project.entry_path.read_text(encoding='utf-8') + '\n.子程序 中文处理\n输出("事件")\n', encoding='utf-8')
        self.window._switch(project)
        window = self.window
        self.until(lambda: window.editor.path == str(project.entry_path.resolve()))
        window.select_control('')
        combo = window.properties.event_widgets['load']
        self.assertGreaterEqual(combo.findText('中文处理'), 0)
        combo.setCurrentText('中文处理')
        combo.activated.emit(combo.currentIndex())
        window.save_all()
        self.until(lambda: project.load_form()['form']['events'].get('load') == '中文处理')

    def test_imported_resource_is_listed_and_previewed_without_opening_binary_in_editor(self):
        window = self.window
        source = self.temp / 'asset.bin'
        source.write_bytes(b'\0binary-resource')
        original = window.editor.path
        with patch('pcide.main.QFileDialog.getOpenFileName', return_value=(str(source), '')):
            window.resources_panel.import_requested.emit()
            self.until(lambda: (window.project.root / 'resources/asset.bin').is_file())
        panel = window.resources_panel
        self.assertEqual(window.editor.path, original)
        self.assertIs(window.tabs.currentWidget(), panel)
        row = next(row for row in range(panel.table.rowCount()) if panel.table.item(row, 0).text() == 'resources/asset.bin')
        panel.table.setCurrentCell(row, 0)
        panel.copy_path()
        self.assertEqual(QApplication.clipboard().text(), 'resources/asset.bin')
        self.assertIn('大小：', panel.preview.toPlainText())
        panel.search.setText('not-present')
        self.assertTrue(panel.table.isRowHidden(row))

    def test_source_routine_navigation_opens_own_file_and_restores_editor(self):
        window = self.window
        source = window.project.root / 'src/helper.py'
        source.write_text('def other_file_routine():\n    return 42\n', encoding='utf-8')
        window._load_project()
        queue = [window.project_tree.invisibleRootItem()]
        target = None
        while queue:
            item = queue.pop()
            if item.text(0).startswith('子程序 other_file_routine'):
                target = item
                break
            queue.extend(item.child(i) for i in range(item.childCount()))
        self.assertIsNotNone(target)
        window._close_code_tab(window.tabs.indexOf(window.editor))
        window._open_program_item(target)
        self.until(lambda: window.editor.path == str(source.resolve()))
        self.assertTrue(window.tabs.isTabVisible(window.tabs.indexOf(window.editor)))
        self.assertIs(window.tabs.currentWidget(), window.editor)

    def test_breakpoint_page_navigates_and_clears(self):
        window = self.window
        window.toggle_breakpoint(str(window.project.entry_path), 4)
        self.assertEqual(window.breakpoint_tree.topLevelItemCount(), 1)
        window._close_code_tab(window.tabs.indexOf(window.editor))
        window.goto_breakpoint(window.breakpoint_tree.topLevelItem(0))
        self.assertTrue(window.tabs.isTabVisible(window.tabs.indexOf(window.editor)))
        if window.editor._fallback:
            self.assertEqual(len(window.editor._fallback_edit.extraSelections()), 1)
            helper = window.project.root / 'src/no_breakpoints.py'
            helper.write_text('value = 1\n', encoding='utf-8')
            window.editor.load(helper)
            self.assertEqual(len(window.editor._fallback_edit.extraSelections()), 0)
            window.goto_breakpoint(window.breakpoint_tree.topLevelItem(0))
            self.assertEqual(len(window.editor._fallback_edit.extraSelections()), 1)
        window.clear_breakpoints()
        self.assertEqual(window.breakpoints, {})
        self.assertEqual(window.breakpoint_tree.topLevelItemCount(), 0)

    def test_entry_routine_navigation_returns_from_other_file_without_duplicate_file_nodes(self):
        window = self.window
        helper = window.project.root / 'src/other.py'
        helper.write_text('def helper():\n    return 1\n', encoding='utf-8')
        window._load_project()
        window.editor.load(helper)
        routine_section = next(window.project_tree.topLevelItem(i) for i in range(window.project_tree.topLevelItemCount())
                               if window.project_tree.topLevelItem(i).text(0) == '子程序')
        self.assertGreater(routine_section.childCount(), 0)
        window._open_routine(routine_section.child(0))
        self.assertEqual(window.editor.path, str(window.project.entry_path.resolve()))
        queue = [window.project_tree.invisibleRootItem()]
        while queue:
            item = queue.pop()
            if item.text(0) == window.project.entry_path.name:
                self.assertEqual(item.childCount(), 0)
            queue.extend(item.child(i) for i in range(item.childCount()))

    def _assert_async_routine_navigation(self, project, source, headers, helper_source, helper_header):
        project.entry_path.write_text(source, encoding='utf-8')
        helper = project.root / ('src/helper' + project.entry_path.suffix)
        helper.write_text(helper_source, encoding='utf-8')
        window = self.window
        window._switch(project)
        entry = str(project.entry_path.resolve())
        self.until(lambda: window.editor.path == entry)
        section = next(window.project_tree.topLevelItem(i) for i in range(window.project_tree.topLevelItemCount())
                       if window.project_tree.topLevelItem(i).text(0) == '子程序')
        expected_lines = [source.splitlines().index(header) + 1 for header in headers]
        self.assertEqual(section.childCount(), len(headers))
        self.assertEqual(window.routine_list.topLevelItemCount(), len(headers))
        self.assertEqual([section.child(i).data(0, Qt.ItemDataRole.UserRole + 1) for i in range(section.childCount())], expected_lines)
        queue = [window.project_tree.invisibleRootItem()]
        helper_item = None
        while queue:
            item = queue.pop()
            if item.data(0, Qt.ItemDataRole.UserRole) == str(helper) and item.text(0) == helper.name:
                helper_item = item
            if item.text(0) == project.entry_path.name:
                self.assertEqual(item.childCount(), 0, '入口子程序只应出现在独立列表')
            queue.extend(item.child(i) for i in range(item.childCount()))
        self.assertIsNotNone(helper_item)
        self.assertEqual(helper_item.childCount(), 1, '字符串和注释中的声明不能成为子程序')
        helper_line = helper_source.splitlines().index(helper_header) + 1
        self.assertEqual(helper_item.child(0).data(0, Qt.ItemDataRole.UserRole + 1), helper_line)
        window._close_code_tab(window.tabs.indexOf(window.editor))
        window._open_program_item(helper_item.child(0))
        self.until(lambda: window.editor.path == str(helper.resolve()))
        self.assertTrue(window.tabs.isTabVisible(window.tabs.indexOf(window.editor)))
        self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['position']['lineNumber'] == helper_line + 1)
        for index, line in enumerate(expected_lines):
            window._open_routine(section.child(index))
            self.until(lambda: window.editor.path == entry)
            self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['position']['lineNumber'] == line + 1)
        window._open_routine(window.routine_list.topLevelItem(len(headers) - 1))
        self.assertEqual(window.editor.path, entry)
        self.assertEqual(project.entry_path.read_text(encoding='utf-8'), source)
        self.assertEqual(helper.read_text(encoding='utf-8'), helper_source)

    def test_python_async_routines_are_complete_and_exclude_nested_or_literal_declarations(self):
        source = ('note = """\ndef literal():\n    return 0\n"""\n\n'
                  'def plain(value):\n    return value\n\n'
                  'async def fetch_data(value):\n    return value\n\n'
                  'class Container:\n    async def nested(self):\n        return 0\n')
        helper = 'note = "async def fake():"\n\nasync def helper(value):\n    return value\n'
        self._assert_async_routine_navigation(create_project(self.paths, 'PythonAsyncNavigation', 'python-script'),
                                             source, ['def plain(value):', 'async def fetch_data(value):'],
                                             helper, 'async def helper(value):')

    def test_node_exported_and_async_routines_are_complete_in_entry_and_other_files(self):
        for language in ('javascript', 'typescript'):
            with self.subTest(language=language):
                source = ('const note = `\nexport function literal() {}\n`;\n/*\nexport async function comment() {}\n*/\n\n'
                          'function plain(value) {\n    return value;\n}\n\n'
                          'async function local_async(value) {\n    return value;\n}\n\n'
                          'export function exported(value) {\n    return value;\n}\n\n'
                          'export async function exported_async(value) {\n    return value;\n}\n')
                helper = '/*\nasync function fake() {}\n*/\nexport async function helper(value) {\n    return value;\n}\n'
                headers = ['function plain(value) {', 'async function local_async(value) {',
                           'export function exported(value) {', 'export async function exported_async(value) {']
                self._assert_async_routine_navigation(create_project(self.paths, language.title() + 'AsyncNavigation', language + '-script'),
                                                     source, headers, helper, 'export async function helper(value) {')

    def test_flow_structured_edit_direction_deletion_and_persisted_run(self):
        canvas = self.window.flow
        flow = {'version': 1, 'nodes': [
            {'id': 'a', 'kind': 'log', 'position': [100, 100], 'config': {'message': 'A'}},
            {'id': 'b', 'kind': 'log', 'position': [300, 100], 'config': {'message': 'B'}}], 'edges': []}
        canvas.load(flow)
        canvas.source.setCurrentIndex(canvas.source.findData('b'))
        canvas.target.setCurrentIndex(canvas.target.findData('a'))
        canvas.connect_selected()
        self.assertEqual(canvas.flow['edges'], [['b', 'a']])
        dialog = FlowNodeDialog(canvas.flow['nodes'][1], canvas.flow, self.window)
        dialog.identity.setText('日志一')
        dialog.fields['message'].setText('新的日志')
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        canvas.load(dialog.result_flow)
        self.window.save_all()
        self.until(lambda: self.window.project.load_flow()['edges'] == [['日志一', 'a']])
        result = FlowRunner().run(self.window.project.load_flow())
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.outputs[0]['result']['message'], '新的日志')
        canvas.edges[0].setSelected(True)
        canvas.delete_selected()
        self.assertEqual(canvas.flow['edges'], [])

    def test_database_fields_index_default_and_generated_crud_are_real(self):
        dialog = DatabaseDesignerDialog(self.window.project, self.window)
        dialog.table_name.setText('people')
        dialog.columns.setItem(1, 0, QTableWidgetItem('display_name'))
        dialog.columns.setItem(1, 4, QTableWidgetItem('"默认名"'))
        dialog.columns.cellWidget(1, 2).setChecked(False)
        dialog.columns.cellWidget(1, 5).setChecked(True)
        dialog.tabs.setCurrentIndex(2)
        self.assertIn('INSERT INTO people', dialog.preview.toPlainText())
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted, dialog.error.text())
        schema = json.loads((self.window.project.root / 'database/schema.json').read_text(encoding='utf-8'))
        self.assertEqual(schema['tables'][0]['indexes'], ['display_name'])
        namespace = {}
        exec((self.window.project.root / 'src/generated_database.py').read_text(encoding='utf-8'), namespace)
        with sqlite3.connect(':memory:') as connection:
            create_schema(connection, schema)
            connection.execute('INSERT INTO people (id) VALUES (1)')
            self.assertEqual(connection.execute(namespace['CRUD']['people']['read'], (1,)).fetchone(), (1, '默认名'))

    def test_database_invalid_json_cannot_overwrite_saved_definition(self):
        dialog = DatabaseDesignerDialog(self.window.project, self.window)
        dialog.save()
        path = self.window.project.root / 'database/schema.json'
        before = path.read_bytes()
        invalid = DatabaseDesignerDialog(self.window.project, self.window)
        invalid.tabs.setCurrentIndex(1)
        invalid.editor.setPlainText('{invalid json')
        invalid.save()
        self.assertNotEqual(invalid.result(), QDialog.DialogCode.Accepted)
        self.assertTrue(invalid.error.text())
        self.assertEqual(path.read_bytes(), before)
        invalid.reject()

    def test_api_table_saves_timeout_and_quoted_path_with_executable_python_client(self):
        dialog = ApiCenterDialog(self.window.project, self.window)
        dialog.table.item(0, 4).setText("/v1/users?name='x'")
        dialog.table.cellWidget(0, 3).setCurrentText('POST')
        dialog.table.cellWidget(0, 5).setValue(12.5)
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted, dialog.error.text())
        source = (self.window.project.root / 'src/generated_api.py').read_text(encoding='utf-8')
        ast.parse(source)
        namespace = {}
        exec(source, namespace)
        with patch.object(namespace['network'], 'request', return_value={'status': 200}) as request:
            self.assertEqual(namespace['users_list']('https://example.test', {'value': 1}), {'status': 200})
            self.assertEqual(request.call_args.args[0], "https://example.test/v1/users?name='x'")
            self.assertEqual(request.call_args.kwargs['timeout'], 12.5)
        endpoints = json.loads((self.window.project.root / 'api/endpoints.json').read_text(encoding='utf-8'))
        self.assertEqual(endpoints[0]['timeout_seconds'], 12.5)
        with self.assertRaises(ApiError):
            generate_client_module([{'id': 'a.b', 'name': 'A', 'method': 'GET', 'path': '/'},
                                    {'id': 'a-b', 'name': 'B', 'method': 'GET', 'path': '/'}])

    def test_api_protects_existing_user_code_and_native_projects_only_save_definitions(self):
        project = self.window.project
        target = project.root / 'src/generated_api.py'
        target.write_text('USER_CODE = 1\n', encoding='utf-8')
        dialog = ApiCenterDialog(project, self.window)
        dialog.save()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(target.read_text(encoding='utf-8'), 'USER_CODE = 1\n')
        self.assertIn('不是 IDE 生成文件', dialog.error.text())
        dialog.overwrite.setChecked(True)
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        native = create_project(self.paths, 'NativeDefinitions', 'cpp-console')
        for cls in (ApiCenterDialog, DatabaseDesignerDialog):
            page = cls(native, self.window)
            self.assertFalse(page.generate.isEnabled())
            self.assertFalse(page.generate.isChecked())
            page.save()
            self.assertEqual(page.result(), QDialog.DialogCode.Accepted, page.error.text())
        self.assertFalse((native.root / 'src/generated_api.py').exists())
        self.assertFalse((native.root / 'src/generated_database.py').exists())

    def test_environment_dialog_persists_real_execution_limits(self):
        window = self.window
        old_language = window.project.manifest['language']
        def edit_dialog():
            dialog = QApplication.activeModalWidget()
            self.assertIsInstance(dialog, EnvironmentDialog)
            self.assertTrue(dialog.engine.isReadOnly())
            dialog.timeout.setValue(15.25)
            dialog.output_limit.setValue(200)
            dialog.accept()
        QTimer.singleShot(50, edit_dialog)
        window.show_environment()
        self.until(lambda: Project.open(window.project.root).manifest['execution']['max_output_lines'] == 200)
        stored = Project.open(window.project.root).manifest
        self.assertEqual(stored['language'], old_language)
        self.assertEqual(stored['execution']['timeout_seconds'], 15.25)

    def test_platform_lists_provider_declarations_and_saves_capability_options(self):
        project = self.window.project
        file = project.root / 'providers/test/provider.json'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({'id': 'example.ai', 'kind': 'ai', 'version': '1.0.0', 'entry': 'missing-provider-code.py'}), encoding='utf-8')
        dialog = PlatformCapabilitiesDialog(project, self.window)
        self.assertEqual(dialog.providers.rowCount(), 1)
        self.assertEqual(dialog.providers.item(0, 3).text(), '文件发现')
        dialog.checks['ai'].setChecked(True)
        dialog.fields[('ai', 'backends')].setText('onnx,opencv')
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted, dialog.error.text())
        self.assertTrue(dialog.result_platform['capabilities']['ai']['enabled'])
        self.assertEqual(dialog.result_platform['capabilities']['ai']['backends'], ['onnx', 'opencv'])
        self.assertEqual(dialog.result_platform['providers'], [])

    def test_annotation_rows_delete_actual_saved_boxes_and_reset_on_project_change(self):
        from pcide.core.label_io import read_boxes, label_path_for
        panel = self.window.vision
        image = panel.vision.dataset / 'images/labels.png'
        image.parent.mkdir(parents=True, exist_ok=True)
        bitmap = QImage(100, 80, QImage.Format.Format_RGB32)
        bitmap.fill(Qt.GlobalColor.white)
        self.assertTrue(bitmap.save(str(image)))
        panel.set_project(self.window.project)
        panel.select_image(image.name)
        panel.add_box({'class_id': 0, 'cx': .5, 'cy': .5, 'w': .2, 'h': .4})
        panel.add_box({'class_id': 0, 'cx': .3, 'cy': .3, 'w': .1, 'h': .1})
        self.assertEqual(panel.annotations.rowCount(), 2)
        panel.annotations.selectRow(0)
        panel.delete_boxes()
        saved = read_boxes(label_path_for(image, panel.vision.dataset))
        self.assertEqual(len(saved), 1)
        self.assertAlmostEqual(saved[0]['cx'], .3)
        self.assertEqual(panel.annotations.rowCount(), 1)
        panel.set_project(self.window.project)
        self.assertEqual(panel.annotations.rowCount(), 0)

    def test_empty_vision_operations_show_feedback_and_reserved_api_names_are_rejected(self):
        messages = []
        self.window.vision.message.connect(messages.append)
        self.window.vision.real_ocr()
        self.window.vision.clear_boxes()
        with patch('pcide.ui.vision_panel.QFileDialog.getOpenFileName') as picker:
            self.window.vision.test_model()
            picker.assert_not_called()
        self.assertEqual(len(messages), 3)
        for identity in ('true', 'null', 'arguments', 'network', 'apiRequest'):
            with self.assertRaises(ApiError, msg=identity):
                generate_client_module([{'id': identity, 'name': '保留名称', 'path': '/'}])


for _name in dir(ui_tests.UiTests):
    if _name.startswith('test_') and _name not in PageContentsUiTests.__dict__:
        setattr(PageContentsUiTests, _name, None)
