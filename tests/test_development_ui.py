from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from pcide.core.agent_tools import project_tools
from pcide.core.paths import Paths
from pcide.ui.agent_dialog import AgentDialog
from pcide.ui.development_dialogs import BuildDialog, ExampleDialog, NewProjectDialog, ToolsDialog
import tests.test_ui as ui_tests

class DevelopmentUiTests(ui_tests.UiTests):
    # Keep this suite focused; inherited regression cases are run separately.
    def test_welcome_creates_native_project_and_switches_editor_mode(self):
        window=self.window
        window.paths.projects=self.paths.projects
        window.show_welcome()
        chooser=window.welcome.chooser
        chooser.kind.setCurrentIndex(chooser.kind.findData('native'))
        chooser.template.setCurrentIndex(chooser.template.findData('cpp-console'))
        chooser.name.setText('NativeFromWelcome')
        window.welcome.createRequested.emit(*chooser.selection())
        self.until(lambda:window.project.manifest['language']=='cpp')
        self.assertEqual(window.editor._language(window.editor.path),'cpp')
        self.assertFalse(window.workspace_tabs.isTabVisible(window.workspace_tabs.indexOf(window.designer)))
        self.assertFalse(window.window_menu.isEnabled())
        self.assertTrue(window.project.entry_path.is_file())
        commands = [window.snippet_tree.topLevelItem(group).child(i).text(0)
                    for group in range(window.snippet_tree.topLevelItemCount())
                    for i in range(window.snippet_tree.topLevelItem(group).childCount())]
        self.assertIn('后台线程', commands)
        self.assertFalse(window.chinese_view_action.isEnabled())
        self.assertNotIn('后台线程', [window.support_library.topLevelItem(i).text(0) for i in range(window.support_library.topLevelItemCount())])

    def test_zhxb_project_shows_yi_style_library_categories_and_types(self):
        project = self.project('ChineseCatalog', 'zhxb')
        self.window._switch(project)
        self.until(lambda: self.window.project.manifest['language'] == 'zhxb')
        labels = []
        def visit(item):
            labels.append(item.text(0))
            for index in range(item.childCount()):
                visit(item.child(index))
        for index in range(self.window.support_library.topLevelItemCount()):
            visit(self.window.support_library.topLevelItem(index))
        self.assertIn('流程控制', labels)
        self.assertIn('网络通信', labels)
        self.assertIn('按钮', labels)
        self.assertIn('属性', labels)
        self.assertIn('事件', labels)
        self.assertIn('方法', labels)
        self.assertNotIn('通用对话框', labels)
        self.assertEqual(self.window.snippet_tree.topLevelItemCount(), 0)
        self.assertTrue(self.window.chinese_view_action.isEnabled())

    def test_cpp_view_edits_and_saves_original_language_without_keyword_projection(self):
        import json
        from pcide.core.development import create_project
        project = create_project(self.paths, 'CppRoundtrip', 'cpp-console')
        source = '#include <iostream>\nint main() { const int value = 42; std::cout << value; return 0; }\n'
        project.entry_path.write_text(source, encoding='utf-8')
        self.window._switch(project)
        editor = self.window.editor
        if editor._fallback:
            self.assertEqual(editor.view.toPlainText(), source)
        else:
            self.until(lambda: json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['displayText'] == source)
            self.assertEqual(json.loads(self.javascript('JSON.stringify(pcide.snapshot())'))['text'], source)
        captured = []
        editor.capture(lambda: captured.append(True))
        self.until(lambda: bool(captured))
        self.assertEqual(editor.documents[str(project.entry_path)], source)
        updated = source.replace('42', '43')
        editor.set_value(updated)
        captured.clear()
        editor.capture(lambda: captured.append(True))
        self.until(lambda: bool(captured))
        editor.save()
        self.assertEqual(project.entry_path.read_text(encoding='utf-8'), updated)
        self.assertFalse(self.window.chinese_view_action.isEnabled())
        # The action follows the current file when a native project opens a
        # script file, then returns to native source.
        script = project.root/'src/helper.py'
        script.write_text('print("helper")\n', encoding='utf-8')
        editor.load(script)
        self.assertTrue(self.window.chinese_view_action.isEnabled())
        editor.load(project.entry_path)
        self.assertFalse(self.window.chinese_view_action.isEnabled())

    def test_project_wizard_keeps_only_supported_build_targets(self):
        dialog=NewProjectDialog(self.window)
        chooser=dialog.chooser
        chooser.kind.setCurrentIndex(chooser.kind.findData('desktop'))
        chooser.template.setCurrentIndex(chooser.template.findData('csharp-winforms'))
        self.assertEqual([chooser.target.itemData(i) for i in range(chooser.target.count())],['dotnet-system'])
        chooser.kind.setCurrentIndex(chooser.kind.findData('game'))
        chooser.template.setCurrentIndex(chooser.template.findData('godot-2d'))
        self.assertEqual(chooser.target.currentData(),'godot')
        dialog.close()

    def test_close_project_keeps_welcome_and_can_create_again(self):
        window=self.window
        window.paths.projects=self.paths.projects
        window.close_project()
        self.until(lambda:window._project_closed)
        self.assertTrue(window.welcome.isEnabled())
        self.assertIs(window.workspace_tabs.currentWidget(),window.welcome)
        window.debug_script();self.assertFalse(window.runner.active)
        window.create_software_project('AfterClose','python-script','script-system')
        self.until(lambda:not window._project_closed and window.project.root.name=='AfterClose')
        self.assertTrue(window.editor.isEnabled())
        self.assertIs(window.workspace_tabs.currentWidget(),window.tabs)

    def test_old_unity_entry_now_binds_a_buildable_engine_project(self):
        from unittest.mock import patch
        from pcide.core.development import create_project
        from pcide.core.engines import engine_command
        window=self.window;window.paths.projects=self.paths.projects
        external=create_project(self.paths,'ExternalUnity','unity-3d')
        with patch('pcide.main.QFileDialog.getExistingDirectory',return_value=str(external.root)):
            window.connect_unity_project()
            self.until(lambda:window.project.manifest['development']['template']=='unity-3d')
        self.assertNotEqual(window.project.root,external.root)
        self.assertEqual(window.project.manifest['development']['engine_root'],str(external.root))
        self.assertIn('-buildWindows64Player',engine_command(window.project,'Unity.exe','build',self.temp/'game.exe'))
        commands=[window.snippet_tree.topLevelItem(group).child(i).text(0)
                  for group in range(window.snippet_tree.topLevelItemCount())
                  for i in range(window.snippet_tree.topLevelItem(group).childCount())]
        self.assertIn('协程与取消',commands);self.assertNotIn('窗口线程更新',commands)

    def test_tools_dialog_saves_reusable_defaults_and_limits_engine_binding(self):
        import sys
        from pcide.core.toolchains import load_workspace_tools
        dialog=ToolsDialog(self.window.project,self.window,paths=self.paths)
        self.assertFalse(dialog.engine_root.isEnabled())
        dialog.fields['python'].setText(sys.executable);dialog.save()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(load_workspace_tools(self.paths)['python'],sys.executable)
        dialog.close()

    def test_console_input_widgets_send_to_owned_program_and_show_live_output(self):
        import sys
        window=self.window
        window._launch_tool([sys.executable,'-u','-c','print("READY",flush=True); print("INPUT="+input())'],
                            '控制台测试',cwd=self.temp,interactive=True,timeout=10)
        try:
            self.until(lambda:'READY' in window.output_panel.toPlainText())
            self.assertTrue(window.console_input.isEnabled())
            window.console_input.setText('42');window.console_send.click()
            self.until(lambda:'INPUT=42' in window.output_panel.toPlainText())
            self.until(lambda:not window.console_input.isEnabled())
            self.assertFalse(window.tool_sessions)
        finally:
            window.cancel_tools()
            for session in tuple(window.tool_sessions.values()):session.wait(5)

    def test_examples_search_readme_double_click_and_real_copy(self):
        from pcide.core.examples import instantiate_example
        dialog=ExampleDialog(Paths(),self.window)
        dialog.show();self.app.processEvents()
        self.assertEqual(dialog.tree.topLevelItemCount(),100)
        dialog.search.setText('有界后台任务池')
        self.assertEqual(dialog.tree.topLevelItemCount(),1)
        self.assertIn('预期结果',dialog.details.toPlainText())
        rect=dialog.tree.visualItemRect(dialog.tree.topLevelItem(0))
        dialog.activateWindow();QTest.qWait(30)
        QTest.mouseClick(dialog.tree.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        QTest.mouseDClick(dialog.tree.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        self.until(lambda:dialog.result()==QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_example['id'],'task_pool')
        self.paths.resources=Paths().root
        project=instantiate_example(self.paths,dialog.selected_example)
        self.window._switch(project)
        self.assertIn('tasks.pool',self.window.editor.documents[str(project.entry_path)])

    def test_build_dialog_exposes_incremental_static_and_system_modes(self):
        dialog=BuildDialog(self.window.project,Paths(),self.window)
        dialog.target.setCurrentIndex(dialog.target.findData('script-system'))
        self.assertIn('系统环境',dialog.target.currentText())
        self.assertIn('不下载',dialog.description.text())
        self.assertEqual(dialog.settings()['target'],'script-system')
        dialog.rebuild();self.assertTrue(dialog.force)

    def test_library_drag_carries_real_snippet_and_context_help(self):
        tree=self.window.support_library
        def find(item,text):
            if item.text(0)==text:return item
            for i in range(item.childCount()):
                result=find(item.child(i),text)
                if result:return result
        item=find(tree.topLevelItem(0),'创建任务池')
        self.assertIsNotNone(item)
        self.assertIn('tasks.pool',tree.mimeData([item]).text())
        self.assertIn('64',item.data(0,Qt.ItemDataRole.UserRole+5)['description'])
        before=self.window.editor.documents[str(self.window.project.entry_path)]
        self.window._insert_library_item(item)
        self.window.editor.capture(lambda:None)
        self.until(lambda:self.window.editor.documents[str(self.window.project.entry_path)]!=before)
        self.assertIn('tasks.pool',self.window.editor.documents[str(self.window.project.entry_path)])

    def test_ai_window_write_signal_refreshes_real_designer(self):
        window=self.window
        dialog=AgentDialog(window.project,window)
        tools={t.name:t.handler for t in project_tools(window.project.root,{'ui/main.form.json'},on_ui_written=dialog._ui_written)}
        form=tools['inspect_ui']({})['model']
        form['controls'][1]['properties']['text']='后台生成的UI'
        tools['write_ui']({'path':'ui/main.form.json','model':form})
        self.assertEqual(window.designer.form['controls'][1]['properties']['text'],'后台生成的UI')
        self.assertIn('校验',dialog.output.toPlainText())
        dialog.close()

    def test_editor_evicts_saved_documents_and_preserves_dirty_buffers(self):
        editor=self.window.editor
        paths=[]
        for number in range(66):
            path=self.window.project.root/'src'/f'cache_{number}.txt'
            path.write_text('cached '+str(number),encoding='utf-8');paths.append(path)
            editor.load(path)
        self.assertLessEqual(len(editor.documents),64)
        self.assertNotIn(str(paths[0]),editor.documents)
        protected=str(paths[40]);editor.documents[protected]='unsaved edit'
        for number in range(66,72):
            path=self.window.project.root/'src'/f'cache_{number}.txt';path.write_text('more',encoding='utf-8');editor.load(path)
        self.assertEqual(editor.documents[protected],'unsaved edit')
        self.window.dirty=False

# unittest also discovers inherited cases; remove them from this subclass so
# one explicit command can run just the interaction additions.
for _name in dir(ui_tests.UiTests):
    if _name.startswith('test_') and _name not in DevelopmentUiTests.__dict__:
        setattr(DevelopmentUiTests,_name,None)
