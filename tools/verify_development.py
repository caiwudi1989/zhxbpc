"""Actual example execution, native/.NET build metrics and source evidence. No downloads."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from pcide.core.build_service import BuildService
from pcide.core.development import SCRIPT_LANGUAGES
from pcide.core.examples import load_catalog,instantiate_example
from pcide.core.paths import Paths,atomic_write_json,sha256_file
from pcide.core.processes import run_bounded
from pcide.core.runner import ScriptRunner

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frozen',type=Path)
    args=parser.parse_args()
    paths=Paths(root).ensure()
    probe=paths.cache/('development-probe-'+uuid.uuid4().hex)
    workspace=Paths(probe).ensure()
    workspace.resources=root
    _,catalog=load_catalog(paths)
    records=[]
    def build_project(project,target=None):
        if not args.frozen:return BuildService(workspace).build(project,target)
        report=paths.logs/('development-build-'+uuid.uuid4().hex+'.json')
        command=[str(args.frozen),'--project',str(project.root),'--build','--report',str(report)]
        if target:command += ['--build-target',target]
        run_bounded(command,cwd=root,timeout=150,log_path=report.with_suffix('.log'))
        result=json.loads(report.read_text(encoding='utf-8'))
        if not result.get('ok'):raise RuntimeError(result.get('error','Frozen IDE build failed'))
        return result
    for entry in catalog:
        project=instantiate_example(workspace,entry)
        started=time.perf_counter()
        record={'id':entry['id'],'template':entry['template'],'ok':False}
        try:
            if project.manifest['language'] in SCRIPT_LANGUAGES:
                form=project.load_form()
                events=list(form['form'].get('events',{}).values())+[handler for control in form['controls'] for handler in control.get('events',{}).values()]
                if args.frozen:
                    log=paths.logs/('development-example-'+entry['id']+'.log')
                    report=paths.logs/('development-example-'+entry['id']+'.json')
                    run_bounded([str(args.frozen),'--project',str(project.root),'--smoke','--report',str(report)],
                        cwd=root,timeout=30,log_path=log)
                    data=json.loads(report.read_text(encoding='utf-8'))
                    record.update(ok=data['script_exit']==0,output=data['output'][-4000:],ui_updates=len(data['ui_updates']))
                else:
                    runner=ScriptRunner()
                    try:
                        code,output,state=runner.run_sync(project,timeout=15,events=events)
                        record.update(ok=code==0,exit_code=code,output=output[-4000:],error=state.error,
                                      ui_updates=sum(m.get('kind')=='ui.set' for m in runner.messages))
                    finally:runner.stop();runner.wait(5)
            elif entry['template'].startswith(('unity','godot')):
                record.update(ok=True,executed=False,reason='本机未配置引擎；仅工程文件/命令合同已验证，未声称引擎运行成功')
            elif entry['template']=='cpp-cmake':
                record.update(ok=True,executed=False,reason='未配置系统CMake；未下载')
            elif project.manifest['language'] in {'c','cpp'}:
                key='cc' if project.manifest['language']=='c' else 'cxx'
                project.manifest['development']['tools'][key]=str(root/('sdk/mingw64/bin/gcc.exe' if key=='cc' else 'sdk/mingw64/bin/g++.exe'))
                project.save_manifest()
                first=build_project(project)
                unchanged=build_project(project)
                source=project.entry_path.read_text(encoding='utf-8')
                project.entry_path.write_text(source+'\n// iteration probe\n',encoding='utf-8')
                incremental=build_project(project)
                record.update(ok=True,first=first,unchanged=unchanged,incremental=incremental,executed=False)
                if entry['template']!='cpp-win32':
                    log=paths.logs/('development-native-'+entry['id']+'.log')
                    run_bounded([first['artifact']],cwd=Path(first['artifact']).parent,timeout=10,log_path=log)
                    record.update(executed=True,output=log.read_text(encoding='utf-8'))
                import pefile
                with pefile.PE(first['artifact']) as binary:
                    record['imports']=[i.dll.decode('ascii') for i in binary.DIRECTORY_ENTRY_IMPORT]
            elif project.manifest['language']=='csharp':
                project.manifest['development']['tools']['dotnet']=str(root/'sdk/dotnet/dotnet.exe')
                project.save_manifest()
                result=build_project(project)
                record.update(ok=True,build=result,executed=False)
                if entry['template']=='csharp-console':
                    log=paths.logs/('development-dotnet-'+entry['id']+'.log')
                    env=BuildService.system_environment();env['DOTNET_ROOT']=str(root/'sdk/dotnet')
                    run_bounded([result['artifact']],cwd=Path(result['artifact']).parent,timeout=10,log_path=log,environment=env)
                    record.update(executed=True,output=log.read_text(encoding='utf-8'))
            else:
                result=build_project(project)
                record.update(ok=True,build=result,executed=False,reason='静态网页文件已发布；浏览器交互由Qt UI/人工预览门禁另验')
        except Exception as exc:record['error']=str(exc)
        record['seconds']=round(time.perf_counter()-started,3)
        records.append(record)
        print(entry['id'], 'PASS' if record['ok'] else 'FAIL',flush=True)
    report={'ok':all(r['ok'] for r in records),'examples':len(records),'workspace':str(probe),
        'source':{str(p.relative_to(root)):sha256_file(p) for p in sorted((root/'src/pcide').rglob('*.py'))},
        'frozen':str(args.frozen) if args.frozen else None,'results':records}
    if args.frozen:report['exe_sha256']=sha256_file(args.frozen)
    atomic_write_json(paths.logs/('development-examples-frozen-20261010.json' if args.frozen else 'development-examples-20261010.json'),report)
    raise SystemExit(0 if report['ok'] else 1)

if __name__=='__main__':main()
