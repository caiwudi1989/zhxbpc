"""Fresh/incremental/unchanged customer builds and portable EXE execution."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from pcide.core.builder import BuildManager
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.processes import run_bounded, child_environment
from pcide.core.project import Project


def main():
    paths = Paths(root).ensure()
    workspace = paths.cache/'release-probes'/('closeout-'+uuid.uuid4().hex)
    workspace.mkdir(parents=True)
    test_paths = Paths(workspace).ensure()
    manager_paths = Paths(root).ensure()
    manager_paths.artifacts = paths.build/'closeout-projects'
    manager_paths.artifacts.mkdir(parents=True,exist_ok=True)
    manager = BuildManager(manager_paths)
    report = {'date':'2026-10-10', 'workspace':str(workspace), 'projects':[], 'ok':False}
    for language, extension in [('python','py'),('zhxb','zhxb'),('javascript','js'),('typescript','ts')]:
        project = Project.create(test_paths,'closeout-'+language,language)
        original = project.entry_path.read_text(encoding='utf-8')
        project.entry_path.write_text(original + ('\n输出(add(count))\n' if language=='zhxb' else '\nprint(add(count))\n' if language=='python' else '\nconsole.log(add(count));\n'),encoding='utf-8')
        (project.root/f'src/library.{extension}').write_text('.版本 2\n.子程序 add(value), 整数型, 公开\n返回(value + local_value)\n' if language=='zhxb' else
            'def add(value):\n    return value + local_value\n' if language=='python' else 'function add(value) { return value + local_value; }\n',encoding='utf-8')
        atomic_write_json(project.ide_dir/'routines.json',{'public':{'file':f'src/library.{extension}','sourceName':'add','name':'add','line':2 if language=='zhxb' else 1,
                         'public':True,'locals':[{'name':'local_value','type':'整数型','defaultValue':'7'}]}})
        project.save_data({'variables':[{'id':'count','label':'数量','type':'整数型','default':'2','scope':'global'}]})
        results = {}
        for kind in ('first','incremental','unchanged'):
            if kind=='incremental':
                project.entry_path.write_text(project.entry_path.read_text(encoding='utf-8')+('\n输出("incremental")\n' if language=='zhxb' else '\nprint("incremental")\n' if language=='python' else '\nconsole.log("incremental");\n'),encoding='utf-8')
            started=time.monotonic()
            built=manager.build(project,'standalone')
            results[kind]={'seconds':round(time.monotonic()-started,3),'cache_hit':built['cache_hit'],'changed_files':built['changed_files']}
        execution_report=workspace/(language+'-exe.json')
        environment=child_environment()
        environment.update(PCIDE_DATA_ROOT=str(workspace/'customer-cache'), PCIDE_PYTHON=str(workspace/'missing-python.exe'),PYTHONPATH='')
        run_bounded([built['artifact'],'--verify','--report',str(execution_report)],cwd=workspace,environment=environment,timeout=60,log_path=paths.logs/('closeout-exe-'+language+'.log'))
        execution=json.loads(execution_report.read_text(encoding='utf-8'))
        if execution['exit_code'] or '9' not in execution['output']:
            raise RuntimeError('customer EXE did not execute metadata public call: '+language)
        report['projects'].append({'language':language,'timings':results,'artifact':built['artifact'],'execution':execution})
        atomic_write_json(paths.logs/'closeout-build-timings-20261010.json',report)
    report['ok']=True
    atomic_write_json(paths.logs/'closeout-build-timings-20261010.json',report)
    print(json.dumps({item['language']:item['timings'] for item in report['projects']},ensure_ascii=False))


if __name__=='__main__':
    main()
