"""Reusable build adapters, transactional delivery and bounded incremental tools."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .development import SCRIPT_LANGUAGES, TARGETS, template_for
from .paths import Paths, atomic_write_json, read_json, sha256_file
from .processes import child_environment, run_bounded
from .toolchains import require_tool

# Increment when native compiler/linker policy or delivery contracts change.
BUILD_POLICY = 2
SKIP = {'.git', '.pcide', 'cache', 'build', 'Library', 'Temp', 'Logs', 'obj', 'bin', 'node_modules', '__pycache__', '.godot'}

def project_identity(project):
    name=''.join(char for char in project.root.name if char.isascii() and (char.isalnum() or char in '-_')) or 'app'
    return name + '-' + hashlib.sha256(str(project.root).casefold().encode()).hexdigest()[:10]

def source_files(root):
    values, size = [], 0
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP)
        for name in files:
            path = Path(current) / name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('工程输入不能包含链接或越界路径')
            size += path.stat().st_size
            values.append(path)
            if len(values) > 10000 or size > 512 * 1024 * 1024:
                raise ValueError('工程输入超过 10000 文件或 512MB；请排除生成目录')
        for name in dirs:
            path = Path(current) / name
            if path.is_symlink() or hasattr(path, 'is_junction') and path.is_junction():
                raise ValueError('工程目录不能包含链接')
    return sorted(values)

def artifact_valid(target, stamp):
    files = stamp.get('files', {})
    return bool(files) and all((target / name).is_file() and sha256_file(target / name) == digest for name, digest in files.items())

def native_compile_command(compiler, source, output, project, static):
    cpp = source.suffix.lower() in {'.cpp', '.cc', '.cxx'}
    debug = project.manifest['development']['configuration'] == 'Debug'
    if Path(compiler).name.lower() == 'cl.exe':
        return [compiler, '/nologo', '/c', '/utf-8', '/EHsc', '/std:c++17' if cpp else '/TC',
                '/MT' if static else '/MD', '/Od' if debug else '/O1', '/Gy', '/I' + str(project.root / 'src'),
                str(source), '/Fo' + str(output)]
    return [compiler, '-x', 'c++' if cpp else 'c', '-c', str(source), '-o', str(output), '-std=c++17' if cpp else '-std=c11',
            '-O0' if debug else '-Os', '-g' if debug else '-ffunction-sections', '-fdata-sections', '-I', str(project.root / 'src')]


_LOCAL_INCLUDE = re.compile(r'^\s*#\s*include\s*["<]([^">]+)[">]', re.MULTILINE)


def local_header_dependencies(source, root, headers):
    """Return the transitive project headers used by one native source.

    The old cache key included every header in the project.  A change to an
    unrelated header therefore rebuilt every translation unit.  We only follow
    quoted includes (and angle includes that resolve inside ``src``), which is
    conservative for project-owned headers while leaving system headers to the
    compiler.  Missing includes remain in the signature so adding a header
    invalidates the previous object.
    """
    root = Path(root).resolve()
    by_path = {Path(name).as_posix(): digest for name, digest in headers.items()}
    by_name = {Path(name).name: name for name in by_path}
    seen, pending = set(), [Path(source).resolve()]
    dependencies = {}
    while pending:
        current = pending.pop()
        try:
            text = current.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for include in _LOCAL_INCLUDE.findall(text):
            candidate = (current.parent / include).resolve()
            if not candidate.is_file() or not candidate.is_relative_to(root):
                relative = by_name.get(Path(include).name, Path(include).as_posix())
                dependencies.setdefault(relative, None)
                continue
            relative = candidate.relative_to(root).as_posix()
            if relative not in by_path:
                dependencies.setdefault(relative, None)
                continue
            dependencies[relative] = by_path[relative]
            if relative not in seen:
                seen.add(relative)
                pending.append(candidate)
    return tuple(sorted(dependencies.items()))

class BuildService:
    def __init__(self, paths, cancel=None):
        self.paths = paths.ensure()
        self.cancel = cancel if cancel is not None else threading.Event()
        self.logs = []

    def execute(self, command, project, timeout=300, cwd=None, env=None):
        self.check_cancel()
        log = self.paths.logs / ('tool-' + uuid.uuid4().hex + '.log')
        self.logs.append(str(log))
        try:
            run_bounded(command, cwd=cwd or project.root, timeout=timeout, log_path=log, cancel=self.cancel,
                        environment=env or self.system_environment())
        except RuntimeError as exc:
            detail=log.read_text(encoding='utf-8',errors='replace')[-3000:] if log.is_file() else ''
            raise RuntimeError(str(exc)+'\n'+detail) from exc

    @staticmethod
    def system_environment():
        env = os.environ.copy()
        for key in ('PYTHONPATH', 'PCIDE_PYTHON', 'PCIDE_NODE', 'PCIDE_DOTNET_HOST', 'PCIDE_TYPESCRIPT'):
            env.pop(key, None)
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
                   DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='true')
        return env

    def check_cancel(self):
        if self.cancel.is_set():
            raise RuntimeError('任务已取消')

    def describe(self, project, target=None):
        template = template_for(project)
        target = target or project.manifest['development']['target']
        if target not in template.targets:
            raise ValueError('工程不支持此构建方式')
        return {'template': template.label, 'target': target, 'label': TARGETS[target][0], 'description': TARGETS[target][1],
                'configuration': project.manifest['development']['configuration'], 'jobs': project.manifest['development']['jobs'],
                'output': str(self.paths.artifacts / project_identity(project) / target)}

    def build(self, project, target=None, force=False):
        started = time.perf_counter()
        info = self.describe(project, target)
        target_id = info['target']
        self.check_cancel()
        if target_id == 'script-standalone':
            from .builder import BuildManager
            result = BuildManager(self.paths).build(project, 'standalone', cancel=self.cancel, force=force)
            result.update(seconds=round(time.perf_counter() - started, 3), target=target_id)
            result['bytes'] = Path(result['artifact']).stat().st_size
            return result
        if target_id in {'unity', 'godot'}:
            from .engines import engine_root
            root = engine_root(project)
        else:
            root = project.root
        files = source_files(root)
        inputs = {path.relative_to(root).as_posix(): sha256_file(path) for path in files}
        inputs['.pcide/project.json'] = sha256_file(project.ide_dir / 'project.json')
        for name in ('data.json', 'routines.json', 'modules.json', 'libraries.json'):
            path = project.ide_dir / name
            if path.is_file():
                inputs['.pcide/' + name] = sha256_file(path)
        tool_names = {'native-static': ['cc' if project.manifest['language'] == 'c' else 'cxx'],
            'native-system': ['cc' if project.manifest['language'] == 'c' else 'cxx'], 'cmake': ['cmake'],
            'dotnet-system': ['dotnet'], 'dotnet-aot': ['dotnet'], 'unity': ['unity'], 'godot': ['godot'],
            'script-system': ['node'] if project.manifest['language'] in {'javascript','typescript'} else []}.get(target_id, [])
        tools = {name: require_tool(project, name) for name in tool_names}
        tool_stamps = {name: (path, Path(path).stat().st_size, Path(path).stat().st_mtime_ns) for name, path in tools.items()}
        import marshal
        support = {}
        for name in ('build_service', 'development', 'engines'):
            module = __import__('pcide.core.' + name, fromlist=['__name__'])
            support[name] = hashlib.sha256(marshal.dumps(module.__spec__.loader.get_code(module.__name__))).hexdigest()
        if target_id == 'script-system':
            from .builder import runtime_fingerprint
            support['runtime'] = runtime_fingerprint(Paths(), 'node' if project.manifest['language'] in {'javascript','typescript'} else 'basic')
        stamp = {'policy': BUILD_POLICY, 'inputs': inputs, 'tools': tool_stamps, 'settings': project.manifest['development'],
                 'target': target_id, 'environment': {key: os.environ.get(key, '') for key in ('INCLUDE', 'LIB', 'PATH')}, 'support': support}
        digest = hashlib.sha256(json.dumps(stamp, sort_keys=True).encode()).hexdigest()
        destination = Path(info['output'])
        previous = read_json(destination / 'build.json', {})
        if not force and previous.get('fingerprint') == digest and artifact_valid(destination, previous):
            return {**previous['result'], 'cache_hit': True, 'compiled_files': 0, 'seconds': round(time.perf_counter() - started, 3)}
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = destination.parent / ('_staging-' + uuid.uuid4().hex)
        backup = destination.parent / ('_previous-' + uuid.uuid4().hex)
        stage.mkdir()
        try:
            builder = BUILDERS[target_id](self, project, stage, tools, force, target_id)
            result = builder.build(files)
            if target_id in {'native-static','native-system','cmake','dotnet-system','dotnet-aot'}:
                resources=project.root/'resources'
                if resources.is_dir():shutil.copytree(resources,stage/'resources',dirs_exist_ok=True)
            self.check_cancel()
            for name,value in inputs.items():
                path=(project.root if name.startswith('.pcide/') else root)/name
                if not path.is_file() or sha256_file(path)!=value:
                    raise RuntimeError('工程在编译期间被修改；保留此前产物，请保存后重新编译')
            if target_id not in {'unity','godot'} and {p.relative_to(root).as_posix() for p in source_files(root)} != {name for name in inputs if not name.startswith('.pcide/')}:
                raise RuntimeError('工程在编译期间增删了输入文件；保留此前产物，请重新编译')
            artifact = stage / result.pop('entry')
            if not artifact.is_file():
                raise RuntimeError('工具成功退出但未生成预期产物')
            result.update(ok=True, target=target_id, artifact=str(destination / artifact.relative_to(stage)), cache_hit=False,
                          logs=list(self.logs), seconds=round(time.perf_counter() - started, 3),
                          bytes=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()))
            hashes = {path.relative_to(stage).as_posix(): sha256_file(path) for path in stage.rglob('*') if path.is_file()}
            atomic_write_json(stage / 'build.json', {'version': 1, 'fingerprint': digest, 'files': hashes, 'inputs': inputs, 'result': result})
            if destination.exists():
                destination.rename(backup)
            stage.rename(destination)
            if backup.exists():
                shutil.rmtree(backup)
            return result
        except Exception:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)

class Adapter:
    def __init__(self, service, project, stage, tools, force, target):
        self.service, self.project, self.stage, self.tools, self.force = service, project, stage, tools, force
        self.target = target

class NativeAdapter(Adapter):
    def build(self, files):
        cache=self.service.paths.build_cache/'native'/project_identity(self.project)
        cache.mkdir(parents=True,exist_ok=True)
        (cache/'temp').mkdir(exist_ok=True)
        (self.stage/'temp').mkdir(exist_ok=True)
        env=self.service.system_environment()
        env.update(TEMP='temp',TMP='temp')
        self.native_env=env
        try:
            return self._build(files)
        finally:
            for temporary in (cache/'temp',self.stage/'temp'):
                if temporary.is_dir() and temporary.resolve().is_relative_to(self.service.paths.root):
                    shutil.rmtree(temporary)

    @staticmethod
    def relative_arguments(command,cwd):
        # MinGW's assembler needs ASCII output/TEMP strings. Relative paths
        # preserve the Unicode working directory supplied by CreateProcessW.
        return [command[0],*[os.path.relpath(value,cwd) if Path(value).is_absolute() else value for value in command[1:]]]

    def _build(self, files):
        project, service = self.project, self.service
        static = self.target == 'native-static'
        compiler = next(iter(self.tools.values()))
        suffixes = {'.c'} if project.manifest['language'] == 'c' else {'.c', '.cpp', '.cc', '.cxx'}
        sources = [path for path in files if path.suffix.lower() in suffixes and path.is_relative_to(project.root / 'src')]
        if not sources or len(sources) > 512:
            raise ValueError('原生工程需要 src 中的 1..512 个源文件')
        headers = {p.relative_to(project.root).as_posix(): sha256_file(p) for p in files if p.suffix.lower() in {'.h', '.hpp', '.hxx', '.inl'}}
        cache = service.paths.build_cache / 'native' / project_identity(project)
        cache.mkdir(parents=True, exist_ok=True)
        driver = [BUILD_POLICY, compiler, Path(compiler).stat().st_mtime_ns, project.manifest['development'], static,
                  os.environ.get('INCLUDE', ''), os.environ.get('LIB', ''), os.environ.get('PATH','')]
        def compile_one(source):
            service.check_cancel()
            dependencies = local_header_dependencies(source, project.root, headers)
            identity = hashlib.sha256(json.dumps([str(source), sha256_file(source), driver, dependencies], sort_keys=True).encode()).hexdigest()
            output = cache / (identity + '.o')
            record = read_json(output.with_suffix('.json'), {})
            if not self.force and output.is_file() and record.get('sha256') == sha256_file(output):
                return output, False
            temporary = cache / (uuid.uuid4().hex + '.o')
            try:
                command=native_compile_command(compiler, source, temporary, project, static)
                service.execute(self.relative_arguments(command,cache), project,cwd=cache,env=self.native_env)
                temporary.replace(output)
                atomic_write_json(output.with_suffix('.json'), {'sha256': sha256_file(output)})
                return output, True
            finally:
                temporary.unlink(missing_ok=True)
        with ThreadPoolExecutor(max_workers=project.manifest['development']['jobs'], thread_name_prefix='pcide-compile') as pool:
            futures = [pool.submit(compile_one, source) for source in sources]
            try:
                objects = [future.result() for future in futures]
            except Exception:
                service.cancel.set()
                raise
        output = self.stage / 'app.exe'
        window = template_for(project).id == 'cpp-win32'
        if Path(compiler).name.lower() == 'cl.exe':
            command = [compiler, '/nologo', *[str(p) for p, _ in objects], '/Fe' + str(output), '/link', '/OPT:REF', '/OPT:ICF']
            if window:
                command += ['/SUBSYSTEM:WINDOWS', 'user32.lib', 'gdi32.lib']
        else:
            command = [compiler, *[str(p) for p, _ in objects], '-o', str(output), '-Wl,--gc-sections']
            installation=Path(compiler).parents[1]
            # Override MinGW's absolute internal link search paths when its
            # installation itself lives under a Unicode directory.
            libraries=sorted((installation/'lib/gcc').glob('*/*'))
            libraries += sorted(installation.glob('*mingw*/lib'))
            libraries += [installation/'lib']
            for library in libraries:
                if library.is_dir():command += ['-B',str(library),'-L',str(library)]
            if project.manifest['development']['configuration'] == 'Release':
                command += ['-s']
            if static:
                command += ['-static', '-static-libgcc'] + ([] if project.manifest['language'] == 'c' else ['-static-libstdc++'])
            if window:
                command += ['-mwindows', '-luser32', '-lgdi32']
        service.execute(self.relative_arguments(command,self.stage), project,cwd=self.stage,env=self.native_env)
        used = {p for p, _ in objects}
        cached = sorted(cache.glob('*.o'), key=lambda p: p.stat().st_mtime)
        size = sum(p.stat().st_size for p in cached)
        for path in cached:
            if size <= 256 * 1024 * 1024:
                break
            if path not in used:
                size -= path.stat().st_size
                path.unlink()
                path.with_suffix('.json').unlink(missing_ok=True)
        return {'entry': 'app.exe', 'compiled_files': sum(changed for _, changed in objects), 'source_files': len(sources)}

class CMakeAdapter(Adapter):
    def build(self, files):
        cache = self.service.paths.build_cache / 'cmake' / project_identity(self.project)
        if not (self.project.root / 'CMakeLists.txt').is_file():
            raise ValueError('CMake 工程缺少 CMakeLists.txt')
        executable = self.tools['cmake']
        settings = self.project.manifest['development']
        # CMake keeps its own configure cache.  Reusing it avoids a full
        # generator pass on every source-only iteration; force rebuild still
        # starts with a clean-first build below.
        if self.force or not (cache / 'CMakeCache.txt').is_file():
            self.service.execute([executable, '-S', str(self.project.root), '-B', str(cache),
                                  '-DCMAKE_BUILD_TYPE=' + settings['configuration'],
                                  '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'], self.project)
        self.service.execute([executable, '--build', str(cache), '--config', settings['configuration'], '--parallel', str(settings['jobs'])] + (['--clean-first'] if self.force else []), self.project)
        candidates = [cache / 'bin' / settings['configuration'] / 'app.exe', cache / 'bin/app.exe']
        executable = next((path for path in candidates if path.is_file()), None)
        if executable is None:
            raise ValueError('CMake 模板约定 bin/app.exe 输出；请保持 app 目标名称')
        shutil.copytree(executable.parent,self.stage,dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('*.pdb') if settings['configuration']=='Release' else None)
        return {'entry': 'app.exe', 'compiled_files': None}

class DotnetAdapter(Adapter):
    def build(self, files):
        project = self.project
        cache = self.service.paths.build_cache / 'dotnet' / project_identity(project)
        aot = self.target == 'dotnet-aot'
        if not (project.root / 'app.csproj').is_file():
            raise ValueError('C# 模板需要 app.csproj')
        command = [self.tools['dotnet'], 'publish', str(project.root / 'app.csproj'), '-c', project.manifest['development']['configuration'],
            '-o', str(self.stage), '--self-contained', 'true' if aot else 'false', '--disable-build-servers',
            '-p:BaseIntermediateOutputPath=' + str(cache/'obj') + os.sep,
            '-p:MSBuildProjectExtensionsPath=' + str(cache/'obj') + os.sep,
            '-p:BaseOutputPath=' + str(cache/'bin') + os.sep,
            '-p:OptimizationPreference=Size', '-p:PublishAot=' + str(aot).lower(), '-p:RestoreIgnoreFailedSources=true']
        if project.manifest['development']['configuration']=='Release':command += ['-p:DebugType=None','-p:DebugSymbols=false']
        # A clear source list prevents implicit environment/package downloads.
        config = cache / 'offline.config'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('<configuration><packageSources><clear /></packageSources></configuration>', encoding='utf-8')
        command += ['-p:RestoreConfigFile=' + str(config)]
        # Restore is needed once for a profile.  Subsequent source-only
        # publishes use the immutable assets file and skip network/package
        # graph work, which keeps the normal iteration path short.
        if not self.force and (cache / 'obj' / 'project.assets.json').is_file():
            command.append('--no-restore')
        if aot:
            command += ['-r', 'win-x64']
        env=self.service.system_environment()
        env.update(DOTNET_CLI_HOME=str(self.service.paths.cache/'dotnet-home'),NUGET_PACKAGES=str(self.service.paths.cache/'nuget'))
        if self.force:
            self.service.execute([self.tools['dotnet'],'clean',str(project.root/'app.csproj'),'-c',project.manifest['development']['configuration'],
                '-p:BaseIntermediateOutputPath='+str(cache/'obj')+os.sep,'-p:BaseOutputPath='+str(cache/'bin')+os.sep],project,env=env)
        self.service.execute(command, project, timeout=600,env=env)
        return {'entry': 'app.exe', 'compiled_files': None}

class EngineAdapter(Adapter):
    def build(self, files):
        from .engines import engine_command
        engine = self.target
        self.service.execute(engine_command(self.project, self.tools[engine], 'build', self.stage / 'game.exe'), self.project, timeout=1800)
        return {'entry': 'game.exe', 'compiled_files': None}

class WebAdapter(Adapter):
    def build(self, files):
        for path in files:
            self.service.check_cancel()
            target = self.stage / path.relative_to(self.project.root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return {'entry': self.project.manifest['entry'], 'compiled_files': 0}

class SystemScriptAdapter(Adapter):
    def build(self, files):
        project = self.project
        payload = self.stage / 'payload'
        for path in project.input_files_for_build():
            self.service.check_cancel()
            target = payload / path.relative_to(project.root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        shutil.copy2(project.ide_dir / 'project.json', payload / '.pcide/project.json')
        from .builder import RUNTIME_SOURCE_NAMES
        modules = (*RUNTIME_SOURCE_NAMES, 'development.py', 'platform.py', 'control_catalog.py', 'tasks.py')
        support = self.stage / '_support/pcide'
        (support / 'core').mkdir(parents=True)
        (support / 'ui').mkdir()
        for folder in (support, support / 'core', support / 'ui'):
            (folder / '__init__.py').write_text('', encoding='utf-8')
        resources = self.service.paths.resources / 'pcide' if getattr(__import__('sys'), 'frozen', False) else Path(__file__).resolve().parents[1]
        import importlib.util
        import marshal
        for name in dict.fromkeys(modules):
            module = __import__('pcide.core.' + name[:-3], fromlist=['__name__'])
            loader = module.__spec__.loader
            code = loader.get_code(module.__name__)
            (support / 'core' / (name[:-3] + '.pyc')).write_bytes(importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code))
        for name in ('runtime_api', 'ui.form_runtime'):
            module = __import__('pcide.' + name, fromlist=['__name__'])
            code = module.__spec__.loader.get_code(module.__name__)
            (support / (name.replace('.', '/') + '.pyc')).write_bytes(importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code))
        for name in ('worker_js.cjs', 'source_contract.cjs'):
            shutil.copy2(resources / 'core' / name, support / 'core' / name)
        if project.manifest['language'] in {'javascript','typescript'}:
            node = self.tools['node']
            distribution = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
            compiler = distribution / 'sdk/typescript/package/lib/typescript.js'
            contract = resources / 'core/source_contract.cjs'
            self.service.execute([node, '-e', PREPARE_NODE, str(compiler), str(contract), str(payload),
                json.dumps([str(p) for p in payload.rglob('*') if p.suffix in {'.js','.ts'}])], project)
        (self.stage / 'launch.py').write_text(SYSTEM_LAUNCHER, encoding='utf-8')
        (self.stage / 'launch.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\npython -B launch.py %*\r\n', encoding='ascii')
        (self.stage / 'REQUIRES.txt').write_text('系统 Python 3.12（辅助字节码 ABI）；Node 项目还需 Node；窗口项目需 PySide6。\n'
            '不包含 Python/Node/Qt DLL 或第三方环境。安装依赖后双击 launch.cmd。\n', encoding='utf-8')
        return {'entry': 'launch.cmd', 'compiled_files': 0, 'requires': ['Python 3.12'] + (['Node'] if project.manifest['language'] in {'javascript', 'typescript'} else []) + (['PySide6'] if template_for(project).mode == 'form' else [])}

SYSTEM_LAUNCHER = '''import os, sys, pathlib
root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(root / '_support'))
os.environ['PCIDE_ROOT'] = str(root)
os.environ['PCIDE_PYTHON'] = sys.executable
os.environ['PYTHONPATH'] = str(root / '_support')
from pcide.core.project import Project
from pcide.core.runner import ScriptRunner
project = Project.open(root / 'payload')
if project.manifest['language'] in {'javascript', 'typescript'}:
    os.environ['PCIDE_PREPARED_NODE'] = '1'
if '--verify' in sys.argv or project.manifest['development']['template'].endswith('-script'):
    runner = ScriptRunner()
    code, output, state = runner.run_sync(project)
    print(output)
    if state.error: print(state.error, file=sys.stderr)
    raise SystemExit(code)
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from pcide.ui.form_runtime import RuntimeWindowManager
class Signals(QObject):
    message = Signal(dict)
app = QApplication(sys.argv)
runner, signals = ScriptRunner(), Signals()
forms = {str(p.resolve()): project.load_window(p) for p in project.window_paths()}
manager = RuntimeWindowManager(forms, lambda name, payload: runner.event(name, payload))
def message(record):
    if record['kind'] == 'ready': manager.load_event()
    elif record['kind'] == 'ui.set': manager.update_control(record['id'], record['properties'], record.get('window'))
    elif record['kind'] == 'ui.window.open':
        manager.open(record['window']); manager.load_event(record['window'])
    elif record['kind'] == 'ui.window.close': manager.close(record['window'])
    elif record['kind'] in {'stdout', 'stderr', 'error'}: print(record.get('text', record.get('message', '')))
signals.message.connect(message)
window = manager.open(str(project.form_path.resolve()))
window.closed.connect(app.quit)
runner.start(project, keep_alive=True, on_message=signals.message.emit)
try: raise SystemExit(app.exec())
finally:
    runner.stop(); runner.wait(5); manager.close()
'''

PREPARE_NODE = r'''
const fs=require('node:fs'),path=require('node:path'),ts=require(process.argv[1]),contract=require(process.argv[2]);
const project=process.argv[3],files=JSON.parse(process.argv[4]);
const result={version:1,exports:{},metadata:contract.contract(project).metadata,dataSource:contract.dataSource(project)};
for(const file of files){
 const prepared=contract.prepare(ts,fs.readFileSync(file,'utf8'),file,project,file.endsWith('.ts')?'typescript':'javascript');
 fs.writeFileSync(file,prepared.source,'utf8');
 result.exports[path.relative(project,file).replaceAll('\\','/')]=prepared.names;
}
fs.writeFileSync(path.join(project,'.pcide/prepared-node.json'),JSON.stringify(result),'utf8');
'''

BUILDERS = {'native-static': NativeAdapter, 'native-system': NativeAdapter, 'cmake': CMakeAdapter,
            'dotnet-system': DotnetAdapter, 'dotnet-aot': DotnetAdapter, 'web': WebAdapter,
            'unity': EngineAdapter, 'godot': EngineAdapter, 'script-system': SystemScriptAdapter}
