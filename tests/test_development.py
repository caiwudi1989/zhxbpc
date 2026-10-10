from __future__ import annotations

import copy
import os
import threading
import time
from pathlib import Path

from pcide.core.agent import AgentError
from pcide.core.agent_tools import project_tools
from pcide.core.build_service import BuildService
from pcide.core.development import TEMPLATES, create_project, validate_development
from pcide.core.engines import bind_engine_project, engine_command
from pcide.core.examples import instantiate_example, load_catalog
from pcide.core.paths import Paths
from pcide.core.processes import run_bounded
from pcide.core.project import Project
from pcide.core.runner import ScriptRunner
from pcide.core.tasks import pool
from tests.test_core import WorkspaceCase

ROOT=Path(__file__).resolve().parents[1]

class DevelopmentTests(WorkspaceCase):
    def test_factory_creates_every_explicit_template(self):
        for template in TEMPLATES:
            with self.subTest(template=template.id):
                project=create_project(self.paths,template.id,template.id)
                self.assertEqual(Project.open(project.root).manifest['development']['template'],template.id)
                self.assertTrue(project.entry_path.is_file())
                self.assertTrue((project.root/'README.md').is_file())
                self.assertEqual(project.manifest['development']['target'],template.targets[0])

    def test_rejects_invalid_modes_paths_and_language_mismatch(self):
        for raw,language in [({'template':'cpp-console','target':'dotnet-aot'},'cpp'),
                             ({'template':'python-script','jobs':64},'python'),
                             ({'template':'python-script','tools':{'python':'relative.exe'}},'python'),
                             ({'template':'cpp-console'},'python'),
                             ({'template':'godot-2d','engine_root':'../outside'},'gdscript'),
                             ({'template':'csharp-winforms','target':'dotnet-aot'},'csharp')]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate_development(raw,language)
        with self.assertRaises(ValueError):create_project(self.paths,'../escape','cpp-console')

    def test_legacy_projects_migrate_and_native_rejects_script_runner(self):
        project=self.project()
        manifest=copy.deepcopy(project.manifest);manifest.pop('development')
        self.assertEqual(Project(project.root,manifest).manifest['development']['template'],'python-form')
        native=create_project(self.paths,'native','cpp-console')
        with self.assertRaises(ValueError):ScriptRunner().start(native)

    def test_tasks_bound_capacity_cancel_propagate_errors_and_reap_threads(self):
        started=threading.Event()
        def work(cancel):started.set();cancel.wait(3);return 42
        with pool(1,1) as tasks:
            job=tasks.submit(work);self.assertTrue(started.wait(1))
            with self.assertRaises(RuntimeError):tasks.submit(work)
            job.cancel();self.assertEqual(job.result(2),42)
            deadline=time.monotonic()+1
            while tasks.handles and time.monotonic()<deadline:time.sleep(0.01)
            def fail(cancel):raise ValueError('failure')
            bad=tasks.submit(fail)
            with self.assertRaises(ValueError):bad.result(2)
        self.assertTrue(all(not thread.is_alive() for thread in tasks.threads))
        self.assertFalse(tasks.handles)
        with self.assertRaises(RuntimeError):tasks.submit(work)

    def test_worker_reaps_unclosed_task_pool(self):
        project=self.project(source='from pcide.runtime_api import tasks\np=tasks.pool(1,2)\nj=p.submit(lambda cancel:42)\nprint(j.result(2))\n')
        runner=ScriptRunner();self.owned.append(runner)
        code,output,state=runner.run_sync(project,timeout=5)
        self.assertEqual(code,0,state.error);self.assertIn('42',output)

    def test_external_console_streams_prompt_accepts_input_and_reaps(self):
        import sys
        from pcide.core.tool_session import ToolSession
        output=[];done=threading.Event();result=[]
        def finish(value):result.append(value);done.set()
        session=ToolSession([sys.executable,'-u','-c','print("PROMPT>",end="",flush=True); print("VALUE="+input())'],
            cwd=self.temp,log_path=self.paths.logs/'console.log',environment=BuildService.system_environment(),
            on_done=finish,on_output=output.append,interactive=True,timeout=10)
        try:
            deadline=time.monotonic()+3
            while 'PROMPT>' not in ''.join(output) and time.monotonic()<deadline:time.sleep(0.01)
            self.assertIn('PROMPT>',''.join(output));self.assertTrue(session.active)
            with self.assertRaises(ValueError):session.send('bad\ninput')
            session.send('42');self.assertTrue(done.wait(3))
            self.assertTrue(session.wait(2));self.assertTrue(result[0]['ok'],result)
            self.assertIn('VALUE=42',''.join(output));self.assertTrue(session.input.empty())
        finally:session.stop();session.wait(5)

    def test_ai_ui_write_validates_approval_and_refreshes(self):
        project=self.project();written=[]
        tools={item.name:item.handler for item in project_tools(project.root,{'ui/main.form.json'},on_ui_written=written.append)}
        model=tools['inspect_ui']({'path':'ui/main.form.json'})['model']
        model['controls'][1]['properties']['text']='AI设计'
        result=tools['write_ui']({'path':'ui/main.form.json','model':model})
        self.assertTrue(result['validated']);self.assertEqual(written,['ui/main.form.json'])
        self.assertEqual(project.load_form()['controls'][1]['properties']['text'],'AI设计')
        duplicate=copy.deepcopy(model);duplicate['controls'].append(copy.deepcopy(duplicate['controls'][0]))
        with self.assertRaises(ValueError):tools['write_ui']({'path':'ui/main.form.json','model':duplicate})
        with self.assertRaises(AgentError):tools['write_ui']({'path':'ui/new.form.json','model':model,'create':True})

    def test_engine_vectors_are_explicit_and_do_not_execute(self):
        unity=create_project(self.paths,'unity','unity-3d')
        command=engine_command(unity,'C:/Installed/Unity.exe','build',self.temp/'build/game.exe')
        self.assertIn('-batchmode',command);self.assertIn('PCIDEBuild.BuildWindows',command)
        godot=create_project(self.paths,'godot','godot-2d')
        command=engine_command(godot,'C:/Installed/Godot.exe','build',self.temp/'build/game.exe')
        self.assertIn('--headless',command);self.assertIn('--export-release',command)
        self.assertEqual(command[-2],'Windows Desktop')
        with self.assertRaises(ValueError):engine_command(unity,'Unity.exe','unsupported')

    def test_bind_existing_engines_is_runnable_without_overwriting_assets(self):
        from pcide.core.paths import sha256_file
        for template in ('unity-2d','godot-3d'):
            external=create_project(self.paths,'external-'+template,template)
            before={p.relative_to(external.root).as_posix():sha256_file(p) for p in external.root.rglob('*') if p.is_file()}
            project=bind_engine_project(self.paths,'linked-'+template,template,external.root)
            self.assertEqual(project.manifest['development']['engine_root'],str(external.root))
            command=engine_command(project,'engine.exe','build',self.temp/'output/game.exe')
            self.assertIn(str(external.root),command)
            if template.startswith('unity'):self.assertIn('-buildWindows64Player',command)
            after={p.relative_to(external.root).as_posix():sha256_file(p) for p in external.root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
        with self.assertRaises(ValueError):bind_engine_project(self.paths,'invalid','godot-2d',self.temp)
        self.assertFalse(self.paths.project('invalid').exists())

    def test_workspace_tool_defaults_are_reused_and_project_paths_take_priority(self):
        import sys
        from pcide.core.toolchains import discover_tools, save_workspace_tools
        save_workspace_tools(self.paths,{'python':sys.executable})
        project=create_project(self.paths,'new','python-script')
        records=discover_tools(project,self.paths)
        self.assertTrue(records['python']['available'])
        self.assertEqual(records['python']['origin'],'工作区配置')
        project.manifest['development']['tools']['python']=str(self.temp/'missing.exe')
        record=discover_tools(project,self.paths)['python']
        self.assertFalse(record['available']);self.assertEqual(record['origin'],'项目配置')

    def test_all_100_examples_have_valid_projects_and_copy_without_overwrite(self):
        root,catalog=load_catalog(Paths(ROOT))
        self.assertEqual(len(catalog),100)
        for record in catalog:
            with self.subTest(record=record['id']):
                Project.open(root/record['path'])
                self.assertGreater((root/record['path']/'README.md').stat().st_size,400)
        self.paths.resources=ROOT
        first=instantiate_example(self.paths,catalog[0]);second=instantiate_example(self.paths,catalog[0])
        self.assertNotEqual(first.root,second.root)
        self.assertEqual(first.entry_path.read_text(encoding='utf-8'),second.entry_path.read_text(encoding='utf-8'))

    def test_native_real_static_build_incremental_headers_and_rollback(self):
        compiler=ROOT/'sdk/mingw64/bin/g++.exe'
        if not compiler.is_file():self.skipTest('No already-installed C++ compiler')
        project=create_project(self.paths,'small','cpp-console')
        project.manifest['development']['tools']={'cxx':str(compiler)};project.save_manifest()
        project.entry_path.write_text('#include <stdio.h>\n#include "value.h"\nint main(){printf("%d\\n",value());}\n',encoding='utf-8')
        header=project.root/'src/value.h';header.write_text('int value();\n',encoding='utf-8')
        source=project.root/'src/value.cpp';source.write_text('#include "value.h"\nint value(){return 42;}\n',encoding='utf-8')
        first=BuildService(self.paths).build(project)
        unchanged=BuildService(self.paths).build(project)
        self.assertEqual(first['compiled_files'],2);self.assertTrue(unchanged['cache_hit'])
        unrelated=project.root/'src/unused.h';unrelated.write_text('int unrelated();\n',encoding='utf-8')
        untouched=BuildService(self.paths).build(project)
        self.assertEqual(untouched['compiled_files'],0)
        log=self.paths.logs/'native-run.log'
        run_bounded([first['artifact']],cwd=Path(first['artifact']).parent,timeout=10,log_path=log)
        self.assertEqual(log.read_text().strip(),'42')
        source.write_text('#include "value.h"\nint value(){return 43;}\n',encoding='utf-8')
        changed=BuildService(self.paths).build(project);self.assertEqual(changed['compiled_files'],1)
        header.write_text('int value();\n// new API version\n',encoding='utf-8')
        changed=BuildService(self.paths).build(project);self.assertEqual(changed['compiled_files'],2)
        source.write_text('this is invalid C++',encoding='utf-8')
        with self.assertRaises(RuntimeError):BuildService(self.paths).build(project)
        run_bounded([changed['artifact']],cwd=Path(changed['artifact']).parent,timeout=10,log_path=log)
        self.assertEqual(log.read_text().strip(),'43')
        self.assertFalse(list(Path(changed['artifact']).parents[1].glob('_staging-*')))

    def test_web_release_is_cached_and_rebuilds_after_edit(self):
        project=create_project(self.paths,'web','web-app')
        first=BuildService(self.paths).build(project)
        self.assertTrue(Path(first['artifact']).is_file())
        self.assertTrue(BuildService(self.paths).build(project)['cache_hit'])
        project.entry_path.write_text('<h1>new</h1>',encoding='utf-8')
        self.assertFalse(BuildService(self.paths).build(project)['cache_hit'])

    def test_mixed_c_cpp_real_compile_and_link(self):
        compiler=ROOT/'sdk/mingw64/bin/g++.exe'
        if not compiler.is_file():self.skipTest('No already-installed C++ compiler')
        project=create_project(self.paths,'mixed','cpp-console')
        project.manifest['development']['tools']={'cxx':str(compiler)};project.save_manifest()
        project.entry_path.write_text('#include <stdio.h>\nextern "C" int answer(void);\nint main(){printf("%d\\n",answer());}\n',encoding='utf-8')
        (project.root/'src/value.c').write_text('int answer(void){return 42;}\n',encoding='utf-8')
        result=BuildService(self.paths).build(project)
        log=self.paths.logs/'mixed-run.log'
        run_bounded([result['artifact']],cwd=Path(result['artifact']).parent,timeout=10,log_path=log)
        self.assertEqual(log.read_text().strip(),'42');self.assertEqual(result['compiled_files'],2)

    def test_input_added_during_build_rolls_back_delivery(self):
        from unittest.mock import patch
        from pcide.core.build_service import WebAdapter
        project=create_project(self.paths,'changed-during-build','web-app')
        original=BuildService(self.paths).build(project)
        original_text=Path(original['artifact']).read_text(encoding='utf-8')
        build=WebAdapter.build
        def change(adapter,files):
            result=build(adapter,files)
            (project.root/'src/added.js').write_text('alert(42)',encoding='utf-8')
            return result
        with patch.object(WebAdapter,'build',change),self.assertRaises(RuntimeError):
            BuildService(self.paths).build(project,force=True)
        self.assertEqual(Path(original['artifact']).read_text(encoding='utf-8'),original_text)
        self.assertFalse(list(Path(original['artifact']).parents[2].glob('_staging-*')))

    def test_system_script_delivery_copies_no_interpreter_or_qt_and_runs(self):
        import sys
        project=create_project(self.paths,'system','python-script')
        project.entry_path.write_text('print("SYSTEM_ENV_OK")\n',encoding='utf-8')
        result=BuildService(self.paths).build(project,'script-system')
        delivery=Path(result['artifact']).parent
        self.assertFalse(list(delivery.rglob('*.dll')));self.assertFalse(list(delivery.rglob('*.exe')))
        log=self.paths.logs/'system-run.log'
        run_bounded([sys.executable,'-B',str(delivery/'launch.py'),'--verify'],cwd=delivery,timeout=10,log_path=log,
                    environment=BuildService.system_environment())
        self.assertIn('SYSTEM_ENV_OK',log.read_text())

    def test_system_node_delivery_runs_modules_metadata_without_typescript_sdk(self):
        import sys
        from pcide.core.paths import atomic_write_json
        node=ROOT/'runtime/node/node.exe'
        if not node.is_file():self.skipTest('No already-installed Node')
        for language,extension in [('javascript','js'),('typescript','ts')]:
            with self.subTest(language=language):
                project=create_project(self.paths,'system-'+language,language+'-script')
                project.manifest['development']['tools']['node']=str(node);project.save_manifest()
                helper=project.root/f'src/helper.{extension}'
                helper.write_text('function add(value'+(': number' if extension=='ts' else '')+') { return value + local_value; }\n',encoding='utf-8')
                atomic_write_json(project.ide_dir/'routines.json',{'helper':{'file':f'src/helper.{extension}','line':1,
                    'sourceName':'add','name':'add','public':True,'locals':[{'name':'local_value','type':'整数型','defaultValue':'7'}]}})
                project.save_data({'variables':[{'id':'count','label':'数量','type':'整数型','scope':'global','default':'2'}]})
                project.entry_path.write_text(f'console.log(add(count), require("./helper.{extension}").add(3));\n',encoding='utf-8')
                result=BuildService(self.paths).build(project,'script-system')
                delivery=Path(result['artifact']).parent
                self.assertFalse(list(delivery.rglob('typescript.js')))
                self.assertFalse(list(delivery.rglob('*.exe')))
                self.assertFalse(list(delivery.rglob('*.dll')))
                env=BuildService.system_environment();env['PATH']=str(node.parent)+os.pathsep+env.get('PATH','')
                log=self.paths.logs/(language+'-system-run.log')
                run_bounded([sys.executable,'-B',str(delivery/'launch.py'),'--verify'],cwd=delivery,timeout=15,log_path=log,environment=env)
                self.assertIn('9 10',log.read_text(encoding='utf-8'))

    def test_cancelled_build_preserves_existing_artifact(self):
        project=create_project(self.paths,'web','web-app')
        result=BuildService(self.paths).build(project)
        cancel=threading.Event();cancel.set()
        with self.assertRaises(RuntimeError):BuildService(self.paths,cancel).build(project,force=True)
        self.assertTrue(Path(result['artifact']).is_file())
