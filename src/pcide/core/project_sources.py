"""Worker-owned project modules, explicit public exports and shared data."""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from .data import generate_code
from .paths import read_json
from .source import compile_source
from .source import check_value


class ProjectSources(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, project):
        self.project = project
        self.metadata = read_json(project.ide_dir / "routines.json", {})
        if not isinstance(self.metadata, dict):
            raise ValueError("子程序元数据必须是对象")
        self.data = project.load_data()
        if any(item['scope'] != 'global' and not item.get('owner') for item in self.data['variables'] + self.data['constants']):
            raise ValueError('窗口/模块/局部变量必须声明所属名称')
        generated = {**self.data, "variables": [item for item in self.data["variables"] if item["scope"] != "local"],
                     "constants": [item for item in self.data["constants"] if item["scope"] != "local"]}
        self.namespace = {"__name__": "pcide_program_data"}
        exec(compile(generate_code(generated, "python"), "<program-data>", "exec"), self.namespace)
        self.shared = SimpleNamespace(**{item["id"]: self.namespace[item["id"]]
                                        for item in self.data["variables"] + self.data["constants"] if item["scope"] == "global"})
        self.exports = {}
        from .modules import load_modules
        self.registered = {item["id"]: item for item in load_modules(project)["modules"]}
        self.module_exports = {}
        self.modules = {}
        self.static = {}
        self.loading = set()
        declarations = list(self.metadata.values()) + read_json(project.ide_dir / 'public.json', [])
        from .compiler import parse
        for path in project.scripts():
            if path.suffix == '.zhxb':
                declarations += [{'public': True, 'file': path.relative_to(project.root).as_posix(), 'sourceName': procedure.name}
                                 for procedure in parse(path.read_text(encoding='utf-8')).procedures if procedure.public]
        export_files = {}
        for value in declarations:
            if not isinstance(value, dict) or not value.get("public"):
                continue
            file, name = value.get("file"), value.get("sourceName") or value.get("name")
            if not isinstance(file, str) or not isinstance(name, str) or not name.isidentifier():
                raise ValueError("公开子程序身份无效")
            target = project.root / file
            if not target.resolve().is_relative_to(project.root.resolve()) or not file.startswith("src/"):
                raise ValueError("公开子程序文件越界")
            if name in self.exports:
                if export_files[name] == file:
                    continue
                raise ValueError("公开子程序重复: " + name)
            def invoke(*args, _file=file, _name=name, **kwargs):
                module = self.load_file(_file)
                callback = module.get(_name)
                if not callable(callback):
                    raise ValueError("公开子程序不存在: " + _name)
                return callback(*args, **kwargs)
            invoke.__name__ = name
            self.exports[name] = invoke
            export_files[name] = file
        for identity, descriptor in self.registered.items():
            values = {}
            for name in descriptor["exports"]:
                def invoke(*args, _file=descriptor["file"], _name=name, **kwargs):
                    namespace = self.load_file(_file)
                    if not callable(namespace.get(_name)):
                        raise ValueError("模块接口不存在: " + _name)
                    return namespace[_name](*args, **kwargs)
                values[name] = invoke
            self.module_exports[identity] = SimpleNamespace(**values)

    def prepare(self, namespace):
        from .runtime_api import ui, plugins, tasks
        namespace.update(ui=ui,plugins=plugins,tasks=tasks)
        namespace.update({name: value for name, value in self.namespace.items() if not name.startswith("__")})
        namespace.update(self.exports)
        namespace.update(self.module_exports)
        current = namespace.get('__file__')
        if current:
            for identity, descriptor in self.registered.items():
                if Path(current).with_suffix('') == (self.project.root / descriptor['file']).with_suffix('') and identity in self.namespace:
                    # Internal module variables stay in the module's own
                    # namespace; external users receive only public methods.
                    namespace[identity] = self.namespace[identity]
        namespace["__pcide_data__"] = self.shared
        namespace["__pcide_static__"] = self.static
        namespace['__pcide_check_value__'] = check_value

    def code(self, path):
        if path.suffix == ".pyc":
            return importlib.machinery.SourcelessFileLoader(path.stem, str(path)).get_code(path.stem)
        relative = path.relative_to(self.project.root).as_posix()
        return compile_source(path.read_text(encoding="utf-8"), str(path), metadata=self.metadata, data=self.data, file=relative)

    def load_file(self, file):
        if file in self.modules:
            if file in self.loading:
                raise ValueError("模块初始化循环调用: " + file)
            return self.modules[file]
        path = self.project.root / file
        if not path.is_file() and path.suffix in {".py", ".zhxb"}:
            path = path.with_suffix(".pyc")
        namespace = {"__name__": Path(file).stem, "__file__": str(path)}
        self.prepare(namespace)
        self.modules[file] = namespace
        self.loading.add(file)
        try:
            exec(self.code(path), namespace, namespace)
        except BaseException:
            self.modules.pop(file, None)
            raise
        finally:
            self.loading.discard(file)
        return namespace

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.registered:
            return importlib.util.spec_from_loader(fullname, self, origin="pcide-module:" + fullname)
        relative = Path(*fullname.split("."))
        root = self.project.root / "src"
        for suffix in (".py", ".zhxb", ".pyc"):
            source = (root / relative).with_suffix(suffix)
            if source.is_file() and source.resolve().is_relative_to(root.resolve()):
                return importlib.util.spec_from_file_location(fullname, source, loader=self)
            package = root / relative / ('__init__' + suffix)
            if package.is_file() and package.resolve().is_relative_to(root.resolve()):
                return importlib.util.spec_from_file_location(fullname, package, loader=self, submodule_search_locations=[str(package.parent)])
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if module.__name__ in self.module_exports:
            module.__dict__.update(vars(self.module_exports[module.__name__]))
            return
        self.prepare(module.__dict__)
        relative = Path(module.__spec__.origin).relative_to(self.project.root).as_posix()
        if relative in self.modules:
            module.__dict__.update(self.modules[relative])
            return
        self.modules[relative] = module.__dict__
        exec(self.code(Path(module.__spec__.origin)), module.__dict__, module.__dict__)
