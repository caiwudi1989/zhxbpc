"""Bind development delivery to its actual compiled modules and offline assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from pcide.core.builder import RUNTIME_SOURCE_NAMES, runtime_fingerprint
from pcide.core.paths import Paths, atomic_write_json, read_json, sha256_file
from PyInstaller.archive.readers import CArchiveReader


def code_identity(value):
    if isinstance(value, types.CodeType):
        fields = ('co_name', 'co_qualname', 'co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount',
                  'co_nlocals', 'co_stacksize', 'co_flags', 'co_names', 'co_varnames',
                  'co_freevars', 'co_cellvars', 'co_firstlineno', 'co_code', 'co_linetable', 'co_exceptiontable')
        return {**{key: code_identity(getattr(value, key)) for key in fields},
                'co_consts': code_identity(value.co_consts)}
    if isinstance(value, bytes):return {'bytes': value.hex()}
    if isinstance(value, (tuple, list)):return [code_identity(item) for item in value]
    if isinstance(value, frozenset):return {'frozenset': sorted((code_identity(item) for item in value), key=repr)}
    if value is Ellipsis:return {'ellipsis': True}
    if isinstance(value, complex):return {'complex': [value.real, value.imag]}
    return value


def digest_code(value):
    return hashlib.sha256(json.dumps(code_identity(value), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def audit_modules(executable, names):
    archive = CArchiveReader(str(executable)).open_embedded_archive('PYZ.pyz')
    records = {}
    for name in names:
        path = root / 'src' / (name.replace('.', '/') + '.py')
        try:
            embedded = archive.extract(name)
            source = compile(path.read_text(encoding='utf-8'), embedded.co_filename, 'exec', dont_inherit=True, optimize=0)
            actual, expected = digest_code(embedded), digest_code(source)
            records[name] = {'match': actual == expected, 'compiled_sha256': actual, 'source_code_sha256': expected}
        except Exception as exc:records[name] = {'match': False, 'error': str(exc)}
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path)
    parser.add_argument('--report', type=Path, default=root / 'cache/logs/development-artifact-20261010.json')
    args = parser.parse_args()
    exe = args.exe.resolve()
    resources = exe.parent / '_internal'
    names = [p.relative_to(root / 'src').with_suffix('').as_posix().replace('/', '.')
             for p in sorted((root / 'src/pcide').rglob('*.py')) if p.name != '__init__.py' and p.parent.name != 'runtime']
    # Entry code is in the outer archive; the runtime launcher is owned by each prebuilt runtime.
    names.remove('pcide.main')
    names.remove('pcide.core.training_worker')
    modules = audit_modules(exe, names)
    data = [(root / 'src/pcide/ui/editor.html', resources / 'pcide/ui/editor.html'),
            (root / 'examples/catalog.json', resources / 'examples/catalog.json'),
            (root / 'docs/规范/development.md', resources / 'docs/development.md')]
    data.append((root / 'docs/规范/libraries.md', resources / 'docs/libraries.md'))
    data.append((root / 'docs/规范/pages.md', resources / 'docs/pages.md'))
    data += [(root / 'src/pcide/core' / name, resources / 'pcide/core' / name)
             for name in ('worker_js.cjs','compile_js.cjs','source_contract.cjs')]
    data += [(p, resources / p.relative_to(root)) for p in sorted((root / 'examples/projects').rglob('*')) if p.is_file()]
    assets = {str(source.relative_to(root)): destination.is_file() and sha256_file(source) == sha256_file(destination)
              for source, destination in data}
    runtimes = {}
    for profile, folder in [('basic', 'project-runtime'), ('vision', 'project-runtime-vision'), ('node', 'project-runtime-node')]:
        local = root / 'runtime/prebuilt' / folder
        bundled = resources / 'runtime/prebuilt' / folder
        expected = runtime_fingerprint(Paths(root), profile)
        names = ['pcide.core.' + name[:-3] for name in RUNTIME_SOURCE_NAMES]
        names += ['pcide.runtime_api', 'pcide.ui.form_runtime']
        records = audit_modules(bundled / 'PCIDE.Runtime.exe', names)
        import marshal
        launcher = marshal.loads(CArchiveReader(str(bundled / 'PCIDE.Runtime.exe')).extract('launcher'))
        source_launcher = compile((root / 'src/pcide/runtime/launcher.py').read_text(encoding='utf-8'), launcher.co_filename,
                                  'exec', dont_inherit=True, optimize=0)
        runtimes[profile] = {'fingerprint': expected, 'manifest_match':
            read_json(local / 'runtime.json', {}).get('fingerprint') == expected == read_json(bundled / 'runtime.json', {}).get('fingerprint'),
            'launcher_match': digest_code(launcher) == digest_code(source_launcher),
            'exe_match': all(sha256_file(local / name) == sha256_file(bundled / name) for name in ('PCIDE.Runtime.exe','PCIDE.Single.exe')), 'compiled_modules': records}
    entry = CArchiveReader(str(exe)).extract('main')
    import marshal
    actual = marshal.loads(entry)
    expected = compile((root / 'src/pcide/main.py').read_text(encoding='utf-8'), actual.co_filename, 'exec', dont_inherit=True, optimize=0)
    entry_match = digest_code(actual) == digest_code(expected)
    # Training is an explicitly shipped child entry .pyc, not a PYZ module.
    worker = marshal.loads((resources / 'pcide/core/training_worker.pyc').read_bytes()[16:])
    worker_source = compile((root / 'src/pcide/core/training_worker.py').read_text(encoding='utf-8'), worker.co_filename,
                            'exec', dont_inherit=True, optimize=0)
    training_match = digest_code(worker) == digest_code(worker_source)
    ok = entry_match and training_match and all(record['match'] for record in modules.values()) and all(assets.values())
    ok = ok and all(record['manifest_match'] and record['exe_match'] and record['launcher_match'] and all(item['match'] for item in record['compiled_modules'].values()) for record in runtimes.values())
    report = {'ok': ok, 'exe': str(exe), 'exe_sha256': sha256_file(exe), 'entry_match': entry_match, 'training_worker_match': training_match,
              'modules': modules, 'assets': assets, 'runtimes': runtimes}
    atomic_write_json(args.report, report)
    print(json.dumps({'ok': ok, 'modules': len(modules), 'assets': len(assets), 'report': str(args.report)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':raise SystemExit(main())
