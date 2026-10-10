from __future__ import annotations

import json
import zipfile
from unittest.mock import patch

from pcide.core.libraries import (SYSTEM_LIBRARIES, import_library, load_libraries, save_libraries,
                                   calling_example, validate_dex_config)
from pcide.core.compiler import emit_python
from pcide.core.paths import atomic_write_json
from pcide.core.runner import ScriptRunner
from tests.test_core import WorkspaceCase


class LibraryTests(WorkspaceCase):
    def run_project(self, project):
        runner=ScriptRunner()
        self.owned.append(runner)
        runner.start(project,timeout=10)
        runner.wait(15)
        self.assertFalse(runner.active)
        self.assertEqual(runner.state.exit_code,0,(runner.lines,runner.state.error))
        return ''.join(runner.lines)

    def test_yi_style_catalog_has_core_categories_window_types_and_valid_zhxb_snippets(self):
        core = next(item for item in SYSTEM_LIBRARIES if item['id'] == 'system.core')
        window = next(item for item in SYSTEM_LIBRARIES if item['id'] == 'system.window')
        categories = {item['category'] for item in core['commands']}
        for category in {'流程控制', '算术运算', '逻辑比较', '位运算', '变量操作', '数组操作',
                         '环境存取', '文本操作', '字节集操作', '数值转换', '时间操作',
                         '磁盘操作', '文件读写', '程序调试', '数据库', '网络通信', '控制台操作'}:
            self.assertIn(category, categories)
        for type_name in ('窗口', '编辑框', '标签', '按钮', '列表框', '表格', '时钟'):
            self.assertIn(type_name, window['types'])
        self.assertNotIn('通用对话框', window['types'])
        for library in SYSTEM_LIBRARIES:
            labels = [item['label'] for item in library['commands']]
            self.assertEqual(len(labels), len(set(labels)))
            for item in library['commands']:
                code = item['code'].get('zhxb')
                if code:
                    emit_python('.版本 2\n.子程序 主程序\n' + code + '\n')

    def test_system_commands_have_unique_bilingual_completion_aliases(self):
        commands = [command for library in SYSTEM_LIBRARIES for command in library['commands']]
        aliases = [alias for command in commands for alias in command.get('aliases', [])]
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertEqual(len(aliases), len(commands))
        self.assertEqual(next(command for command in commands if command['label'] == '取绝对值')['aliases'], ['abs'])
        self.assertEqual(next(command for command in commands if command['label'] == '解析JSON')['aliases'], ['parse_json'])

    def test_inserted_zhxb_catalog_commands_execute_math_files_database_tasks_and_ui_proxy(self):
        project = self.project('ChineseCommands', 'zhxb')
        commands = {item['label']: item['code']['zhxb'] for library in SYSTEM_LIBRARIES for item in library['commands']}
        body = ['输出('+commands['求平方根']+')', commands['位与'], '输出(value)',
                commands['写到文件'], '输出('+commands['读入文件']+')',
                'connection = '+commands['数据库连接'], commands['数据库执行'], 'connection.close()',
                commands['创建任务池'], commands['提交后台任务'], commands['等待任务结果'], '输出(result)',
                commands['关闭任务池'], commands['设置控件属性'], '输出("CATALOG_OK")']
        project.entry_path.write_text('.版本 2\n.子程序 主程序\n'+'\n'.join(body)+'\n', encoding='utf-8')
        output = self.run_project(project)
        for expected in ('3.0', '1', '内容', '4950', 'CATALOG_OK'):
            self.assertIn(expected, output)

    def test_import_source_selected_exports_edit_and_real_call(self):
        for language,extension,source in [('python','py','def answer():\n    return 42\ndef private():\n    return -1\n'),
            ('zhxb','zhxb','.版本 2\n.子程序 answer, 整数型, 公开\n返回(42)\n.子程序 private\n返回(-1)\n')]:
            with self.subTest(language=language):
                project=self.project(name=language,language=language)
                file=self.temp/('source.'+extension)
                file.write_text(source,encoding='utf-8')
                record=import_library(project,file,'数学模块',exports=['answer'])
                self.assertEqual(record['exports'],['answer'])
                project.entry_path.write_text('print(数学模块.answer())\n' if language=='python' else '.版本 2\n.子程序 主程序\n输出(数学模块.answer())\n',encoding='utf-8')
                self.assertIn('42',self.run_project(project))
                admitted=project.root/record['file']
                admitted.write_text(source.replace('42','43'),encoding='utf-8')
                self.assertEqual(load_libraries(project)['imports'][0]['id'],'数学模块')
                self.assertIn('43',self.run_project(project))

    def test_node_modules_admit_syntax_and_actual_call(self):
        for language,extension in [('javascript','js'),('typescript','ts')]:
            with self.subTest(language=language):
                project=self.project(name=language,language=language)
                source=self.temp/('source.'+extension)
                source.write_text('function answer()'+(': number' if extension=='ts' else '')+' { return 42; }',encoding='utf-8')
                record=import_library(project,source,'math')
                project.entry_path.write_text('console.log('+calling_example(record,language)+');',encoding='utf-8')
                self.assertIn('42',self.run_project(project))
                source.write_text('function broken( {',encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    import_library(project,source,'broken')
                self.assertFalse((project.root/('src/broken.'+extension)).exists())

    def plugin_package(self, identity='sample.math', permissions=()):
        file=self.temp/(identity+'.pcplugin')
        manifest={'id':identity,'name':'算术封装库','version':'1.0.0','kind':'python','entry':'entry.py',
            'capabilities':['add'],'permissions':list(permissions)}
        with zipfile.ZipFile(file,'w') as archive:
            archive.writestr('plugin.json',json.dumps(manifest))
            archive.writestr('entry.py','def plugin_entry(request):\n    return request["params"].get("value",0)+1\n')
        return file

    def test_packaged_plugin_real_worker_call_and_permission_grant(self):
        project=self.project()
        file=self.plugin_package(permissions=['custom.math'])
        import_library(project,file,'math',grant=True)
        project.entry_path.write_text('print(plugins.call("sample.math","add",{"value":41}))\n',encoding='utf-8')
        self.assertIn('42',self.run_project(project))
        self.assertIn('custom.math',project.manifest['permissions'])
        with self.assertRaisesRegex(ValueError,'ID已经存在'):
            import_library(project,file,'again')

    def test_opaque_e_language_files_are_registered_without_execution(self):
        project=self.project()
        for extension in ['ec','fne']:
            source=self.temp/('supplier.'+extension)
            source.write_bytes(b'opaque-supplier-format')
            record=import_library(project,source,'supplier_'+extension)
            self.assertEqual(record['status'],'待桥接封装')
            self.assertEqual(calling_example(record,'python'),'')
        self.assertEqual(project.load_data()['apis'],[])

    def test_bad_manifest_paths_versions_duplicate_ids_and_rollback(self):
        project=self.project()
        file=self.temp/'source.py'
        file.write_text('def answer():\n    return 1\n',encoding='utf-8')
        with self.assertRaises(ValueError):
            import_library(project,file,'bad',version='latest')
        with patch('pcide.core.libraries.save_libraries',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                import_library(project,file,'rollback')
        self.assertEqual(load_libraries(project)['imports'],[])
        self.assertFalse((project.ide_dir/'modules.json').exists())
        for raw in [{'system':[{}]},{'imports':[{'id':'x','file':3}]},{'system':['system.core','system.core']}]:
            atomic_write_json(project.ide_dir/'libraries.json',raw)
            with self.assertRaises(ValueError):
                load_libraries(project)

    def test_dex_connection_configuration_rejects_escapes(self):
        validate_dex_config('ws://127.0.0.1:8765','examples/demo.dex','pcide.android.ExampleDex')
        for url,path,name in [('http://localhost','demo.dex','pcide.Example'),('ws://localhost','../demo.dex','pcide.Example'),
            ('ws://localhost','folder\\demo.dex','pcide.Example'),('ws://localhost','demo.dex','invalid')]:
            with self.assertRaises(ValueError):
                validate_dex_config(url,path,name)

    def test_library_configuration_persists(self):
        project=self.project()
        save_libraries(project,{'version':1,'system':['system.core'],'imports':[]})
        self.assertEqual(load_libraries(project)['system'],['system.core'])

    def test_dll_admission_creates_callable_declaration_in_isolated_host(self):
        from pcide.core.paths import Paths
        project=self.project()
        source=Paths().root/'runtime/modules/native_math/native_math.dll'
        record=import_library(project,source,'初始化库',dll_entry='pcide_init',dll_return='int32')
        self.assertEqual(project.load_data()['apis'][0]['entry'],'pcide_init')
        project.entry_path.write_text('print('+calling_example(record,'python')+')\n',encoding='utf-8')
        self.assertIn('0',self.run_project(project))

    def test_package_path_traversal_is_rejected_before_registration(self):
        project=self.project()
        file=self.plugin_package()
        with zipfile.ZipFile(file,'a') as archive:
            archive.writestr('../outside.py','raise RuntimeError("do not run")')
        with self.assertRaises(ValueError):
            import_library(project,file,'math')
        self.assertFalse((project.root/'plugins/sample.math').exists())
