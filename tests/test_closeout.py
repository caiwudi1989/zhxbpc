from __future__ import annotations

import json
import os
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from pcide.core.compiler import CompilerError, emit_python, parse
from pcide.core.dll import DllProxy, validate_signature
from pcide.core.modules import validate_modules
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.plugins import PluginError
from pcide.core.processes import run_bounded
from pcide.core.processes import ProcessJob, write_protocol, child_environment
from pcide.core.project_sources import ProjectSources
from pcide.core.routines import reconcile, rename_identifier
from pcide.core.runner import ScriptRunner
from tests.test_core import WorkspaceCase


class CloseoutTests(WorkspaceCase):
    def test_compiler_strings_parameters_control_flow_and_source_lines(self):
        source = ('.版本 2\n.子程序 加倍(值), 整数型, 公开\n返回(值 * 2)\n'
                  '.子程序 主程序\n.局部变量 计数, 整数型, 0\n'
                  '遍历 次数, range(3)\n赋值(计数, 计数 + 加倍(次数))\n结束循环\n'
                  '如果(真)\n输出("真 假 空", 计数)\n否则\n输出("wrong")\n结束如果\n')
        code = emit_python(source)
        namespace = {}
        exec(compile(code, 'sample.zhxb', 'exec'), namespace)
        self.assertEqual(namespace['加倍'](4), 8)
        self.assertIn('"真 假 空"', code)
        self.assertEqual(namespace['加倍'].__code__.co_firstlineno, 2)
        self.assertEqual(code.splitlines()[9].strip(), 'print("真 假 空", 计数)')
        namespace['__zhxb_entrypoint__']()
        for invalid in ('.版本 2\n.子程序 x(a,a)\n', '.版本 2\n.子程序 x(a)\n.局部变量 a, 整数型\n',
                        '.版本 2\n.子程序 x\n.参数 1a, 整数型\n', '.版本 2\n.子程序 x\n结束如果\n',
                        '.版本 2\n.子程序 x\n.局部变量 a, 整数型, abc\n'):
            with self.subTest(invalid=invalid), self.assertRaises(CompilerError):
                parse(invalid)
        self.assertNotIn('__zhxb_entrypoint__', emit_python('.版本 2\n.子程序 普通函数\n输出("ready")\n'))

    def test_metadata_identity_survives_insertions_and_rename_preserves_strings(self):
        index = {'src/main.py:1': {'file': 'src/main.py', 'line': 1, 'sourceName': 'work', 'name': 'work', 'id': 'stable', 'remark': 'hello'}}
        source = '\n\ndef work():\n    print("work") # work\nwork()\n'
        updated = reconcile(index, 'src/main.py', source, '.py')
        self.assertEqual(updated['src/main.py:3']['id'], 'stable')
        renamed = rename_identifier(source, '.py', 'work', 'changed')
        self.assertIn('def changed()', renamed)
        self.assertIn('changed()', renamed)
        self.assertIn('print("work") # work', renamed)
        self.assertEqual(reconcile(updated, 'src/main.py', 'def another():\n    pass\n', '.py'), {})

    def test_public_python_and_chinese_cross_file_locals_and_data_execute(self):
        for language, extension in [('python', 'py'), ('zhxb', 'zhxb')]:
            with self.subTest(language=language):
                from pcide.core.project import Project
                project = Project.create(self.paths, 'cross-' + language, language)
                library = project.root / f'src/library.{extension}'
                library.write_text('def add(value):\n    return value + local_value\n' if language == 'python' else
                                   '.版本 2\n.子程序 add(value), 整数型, 公开\n返回(value + local_value)\n', encoding='utf-8')
                line = 1 if language == 'python' else 2
                atomic_write_json(project.ide_dir / 'routines.json', {'library': {'file': f'src/library.{extension}', 'line': line,
                    'sourceName': 'add', 'name': 'add', 'public': True, 'locals': [{'name': 'local_value', 'type': '整数型', 'defaultValue': '7'}]}})
                project.save_data({'variables': [{'id': 'count', 'label': '数量', 'scope': 'global', 'type': '整数型', 'default': '2'}]})
                project.entry_path.write_text('print(add(count))\n' if language == 'python' else '.版本 2\n.子程序 主程序\n输出(add(count))\n', encoding='utf-8')
                code, output, state = ScriptRunner().run_sync(project, timeout=10)
                self.assertEqual(code, 0, state.error)
                self.assertIn('9', output)

    def test_shared_globals_local_scope_and_constant_writes(self):
        project = self.project()
        project.save_data({'variables': [{'id': 'count', 'label': '数量', 'type': '整数型', 'default': '1', 'scope': 'global'},
                                       {'id': 'inside', 'label': '局部', 'type': '整数型', 'default': '4', 'scope': 'local', 'owner': 'work'}],
                           'constants': [{'id': 'VERSION', 'label': '版本', 'type': '整数型', 'value': '3', 'scope': 'global'}]})
        project.entry_path.write_text('def work():\n    count = count + inside\nwork()\nprint(count)\n', encoding='utf-8')
        runner = ScriptRunner()
        code, output, state = runner.run_sync(project, timeout=10)
        self.assertEqual(code, 0, state.error)
        self.assertIn('5', output)
        project.entry_path.write_text('VERSION = 9\n', encoding='utf-8')
        code, _, state = runner.run_sync(project, timeout=10)
        self.assertNotEqual(code, 0)
        self.assertIn('VERSION', state.error)

    def test_module_contract_references_versions_private_names_and_reload(self):
        project = self.project()
        library = project.root / 'src/library.py'
        library.write_text('def answer():\n    return 41\ndef private():\n    return 0\n', encoding='utf-8')
        module = {'id': '数学库', 'version': '1.0.0', 'file': 'src/library.py', 'exports': ['answer'], 'dependencies': {}}
        model = validate_modules({'version': 1, 'modules': [module]}, project.root)
        atomic_write_json(project.ide_dir / 'modules.json', model)
        project.entry_path.write_text('print(数学库.answer())\nprint(hasattr(数学库, "private"))\n', encoding='utf-8')
        runner = ScriptRunner()
        code, output, state = runner.run_sync(project, timeout=10)
        self.assertEqual(code, 0, state.error)
        self.assertIn('41\nFalse', output)
        library.write_text('def answer():\n    return 42\n', encoding='utf-8')
        code, output, state = runner.run_sync(project, timeout=10)
        self.assertEqual(code, 0, state.error)
        self.assertIn('42', output)
        for bad in [{**module, 'dependencies': {'missing': '1.0.0'}}, {**module, 'file': 'src/../escape.py'},
                    {**module, 'dependencies': {'数学库': '1.0.0'}}]:
            with self.assertRaises(ValueError):
                validate_modules({'version': 1, 'modules': [bad]}, project.root)

    def test_real_dll_scalar_timeout_crash_unload_and_no_ide_loading(self):
        if os.name != 'nt':
            self.skipTest('Windows DLL test')
        project = self.project()
        original = Path.cwd()
        shutil.copy2(Paths().runtime / 'modules/native_math/native_math.dll', project.root / 'resources/probe.dll')
        proxy = DllProxy()
        try:
            os.chdir(project.root)
            handle = proxy.load('resources/probe.dll')
            session = proxy._handles[handle][0]
            self.assertNotEqual(session.process.pid, os.getpid())
            self.assertEqual(proxy.call(handle, 'pcide_abi_version', return_type='uint32'), 1)
            self.assertEqual(proxy.call(handle, 'pcide_init'), 0)
            with self.assertRaises(ValueError):
                proxy.call(handle, 'pcide_call', ['text'], '文本型', argument_types=['utf8'])
            with self.assertRaises(ValueError):
                proxy.call(handle, 'pcide_call', [1], '指针')
            with self.assertRaisesRegex(PluginError, 'timeout'):
                proxy.call(handle, 'pcide_call', ['sleep'], 'void', argument_types=['utf8'], timeout=.1)
            self.assertIsNotNone(session.process.poll())
            proxy.unload(handle)
            handle = proxy.load('resources/probe.dll')
            session = proxy._handles[handle][0]
            proxy.call(handle, 'pcide_init')
            with self.assertRaises(PluginError):
                proxy.call(handle, 'pcide_call', ['crash'], 'void', argument_types=['utf8'])
            self.assertIsNotNone(session.process.poll())
            proxy.unload(handle)
            handle = proxy.load('resources/probe.dll')
            session = proxy._handles[handle][0]
            self.assertTrue(proxy.unload(handle))
            self.assertIsNotNone(session.process.poll())
            with self.assertRaises(ValueError):
                proxy.load('../outside.dll')
        finally:
            proxy.close()
            os.chdir(original)

    def test_build_inputs_include_data_routines_and_modules(self):
        project = self.project()
        for name in ('data', 'routines', 'modules'):
            atomic_write_json(project.ide_dir / (name+'.json'), {})
        inputs = {path.relative_to(project.root).as_posix() for path in project.input_files_for_build()}
        self.assertTrue({'.pcide/data.json', '.pcide/routines.json', '.pcide/modules.json'} <= inputs)

    def test_node_public_calls_and_metadata_locals_execute_in_both_languages(self):
        for language, extension in [('javascript', 'js'), ('typescript', 'ts')]:
            with self.subTest(language=language):
                project = self.project(language, language)
                project.entry_path.write_text('console.log(add(count));\n', encoding='utf-8')
                (project.root / f'src/library.{extension}').write_text('function add(value) { return value + local_value; }\n', encoding='utf-8')
                atomic_write_json(project.ide_dir/'routines.json', {'public': {'file': f'src/library.{extension}', 'line': 1,
                    'sourceName': 'add', 'name': 'add', 'public': True, 'locals': [{'name': 'local_value', 'type': '整数型', 'defaultValue': '7'}]}})
                project.save_data({'variables': [{'id': 'count', 'label': '数量', 'type': '整数型', 'default': '2', 'scope': 'global'}]})
                code, output, state = ScriptRunner().run_sync(project, timeout=10)
                self.assertEqual(code, 0, state.error)
                self.assertIn('9', output)

    def test_static_locals_custom_types_and_return_validation(self):
        project = self.project()
        project.save_data({'variables': [{'id': 'counter', 'label': '次数', 'type': '整数型', 'default': '0', 'scope': 'local', 'owner': 'work', 'static': True},
                                       {'id': 'record', 'label': '记录', 'type': 'Record', 'default': '', 'scope': 'global'}],
                           'types': [{'id': 'Record', 'label': '记录型', 'members': [{'id': 'text', 'label': '文本', 'type': '文本型', 'default': 'hello'}]}]})
        project.entry_path.write_text('def work():\n    counter += 1\n    return counter\nprint(work(),work(),record.text)\n', encoding='utf-8')
        runner = ScriptRunner()
        code, output, state = runner.run_sync(project, timeout=10)
        self.assertEqual(code, 0, state.error)
        self.assertIn('1 2 hello', output)
        atomic_write_json(project.ide_dir/'routines.json', {'work': {'file':'src/main.py','sourceName':'work','line':1,'returnType':'文本型'}})
        code, _, state = runner.run_sync(project, timeout=10)
        self.assertNotEqual(code, 0)
        self.assertIn('类型', state.error)

    def test_tool_process_timeout_output_bound_and_cleanup(self):
        python = str(Paths().root / 'runtime/dev/Scripts/python.exe')
        with self.assertRaises(TimeoutError):
            run_bounded([python, '-B', '-c', 'import time; time.sleep(10)'], cwd=self.temp, timeout=.1, log_path=self.temp/'timeout.log')
        with self.assertRaises(RuntimeError):
            run_bounded([python, '-B', '-c', 'print("x" * 2000000)'], cwd=self.temp, timeout=5, log_path=self.temp/'output.log')
        self.assertLessEqual((self.temp/'output.log').stat().st_size, 1024*1024)

    def test_stalled_input_pipe_is_bounded_and_child_is_reaped(self):
        import subprocess
        process = subprocess.Popen([str(Paths().root/'runtime/dev/Scripts/python.exe'), '-B','-c','import time; time.sleep(10)'],
                                   cwd=self.temp,env=child_environment(),stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        job = ProcessJob(process)
        try:
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                write_protocol(process,'x'*60000,job.close,.1)
            self.assertLess(time.monotonic()-started,4)
            process.wait(timeout=3)
            self.assertIsNotNone(process.poll())
        finally:
            job.close()
            process.wait(timeout=3)
            process.stdin.close()


if __name__ == '__main__':
    unittest.main()
