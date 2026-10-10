"""Actual frozen builds and execution of standalone/system four-language software."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from pcide.core.build_service import BuildService
from pcide.core.development import create_project
from pcide.core.paths import Paths, atomic_write_json, sha256_file
from pcide.core.processes import run_bounded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path)
    args = parser.parse_args()
    paths = Paths(root).ensure()
    identity = uuid.uuid4().hex[:10]
    workspace = Paths(paths.cache / ('development-delivery-' + identity)).ensure()
    records = []
    for language, extension in [('python','py'), ('zhxb','zhxb'), ('javascript','js'), ('typescript','ts')]:
        project = create_project(workspace, 'Development_' + identity + '_' + language, language + '-script')
        if language in {'javascript', 'typescript'}:
            project.manifest['development']['tools']['node'] = str(root / 'runtime/node/node.exe')
            project.save_manifest()
        if language == 'python':
            helper = 'def add(value):\n    return value + local_value\n'
            source = ('from pcide.runtime_api import tasks\nprint("DELIVERY", add(count))\n'
                      'with tasks.pool(1, 2) as pool:\n    job = pool.submit(lambda cancel:42)\n    print("FROZEN_TASKS", job.result(3))\n')
            helper_line = 1
        elif language == 'zhxb':
            helper = '.版本 2\n.子程序 add(value), 整数型, 公开\n返回(value + local_value)\n'
            source = '.版本 2\n.子程序 主程序\n输出("DELIVERY", add(count))\n'
            helper_line = 2
        else:
            helper = 'function add(value' + (': number' if language=='typescript' else '') + ') { return value + local_value; }\n'
            source = f'console.log("DELIVERY", add(count), require("./helper.{extension}").add(3));\n'
            helper_line = 1
        (project.root / ('src/helper.' + extension)).write_text(helper, encoding='utf-8')
        project.entry_path.write_text(source, encoding='utf-8')
        atomic_write_json(project.ide_dir / 'routines.json', {'helper': {'file': 'src/helper.' + extension,
            'line': helper_line, 'sourceName': 'add', 'name': 'add', 'public': True,
            'locals': [{'name': 'local_value', 'type': '整数型', 'defaultValue': '7'}]}})
        project.save_data({'variables': [{'id': 'count', 'label': '数量', 'scope': 'global', 'type': '整数型', 'default': '2'}]})
        for target in ('script-standalone', 'script-system'):
            name = language + '-' + target
            record = {'language': language, 'target': target, 'ok': False}
            try:
                report = paths.logs / ('development-delivery-build-' + name + '.json')
                run_bounded([str(args.exe.resolve()), '--project', str(project.root), '--build', '--build-target', target,
                    '--report', str(report)], cwd=root, timeout=120, log_path=report.with_suffix('.log'))
                built = json.loads(report.read_text(encoding='utf-8'))
                artifact = Path(built['artifact'])
                env = BuildService.system_environment()
                env['PYTHONPATH'] = ''
                log = paths.logs / ('development-delivery-run-' + name + '.log')
                if target == 'script-standalone':
                    env['PCIDE_PYTHON'] = str(workspace.root / 'missing-python.exe')
                    env['PCIDE_DATA_ROOT'] = str(workspace.cache / name)
                    run_report = log.with_suffix('.json')
                    run_bounded([str(artifact), '--verify', '--report', str(run_report)], cwd=workspace.root,
                                timeout=40, log_path=log, environment=env)
                    result = json.loads(run_report.read_text(encoding='utf-8'))
                    output = result['output']
                    record['frozen_customer'] = result['frozen']
                else:
                    files = list(artifact.parent.rglob('*'))
                    record['no_environments'] = not any(p.suffix.lower() in {'.exe','.dll'} or p.name=='typescript.js' for p in files if p.is_file())
                    if not record['no_environments']:raise RuntimeError('System delivery unexpectedly includes environments/SDK')
                    run_bounded([sys.executable, '-B', str(artifact.parent/'launch.py'), '--verify'], cwd=artifact.parent,
                                timeout=25, log_path=log, environment=env)
                    output = log.read_text(encoding='utf-8')
                expected = 'DELIVERY 9 10' if language in {'javascript','typescript'} else 'DELIVERY 9'
                if expected not in output:raise RuntimeError('Missing actual public/module/local result: ' + output[-2000:])
                if language=='python' and 'FROZEN_TASKS 42' not in output:raise RuntimeError('Task pool did not execute')
                record.update(ok=True, build=built, output=output[-4000:])
            except Exception as exc:record['error'] = str(exc)
            records.append(record)
            print(name, 'PASS' if record['ok'] else 'FAIL', flush=True)
    report = {'ok': all(record['ok'] for record in records), 'exe': str(args.exe.resolve()),
              'exe_sha256': sha256_file(args.exe), 'workspace': str(workspace.root), 'results': records}
    atomic_write_json(paths.logs/'development-delivery-20261010.json', report)
    return 0 if report['ok'] else 1


if __name__ == '__main__':raise SystemExit(main())
