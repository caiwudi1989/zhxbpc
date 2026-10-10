"""One Python/Chinese source contract shared by run, imports and build."""
from __future__ import annotations

import ast
from pathlib import Path

from .data import _initializer
from .data import TYPES
from .routines import find_metadata

SOURCE_CONTRACT_VERSION = 1


def check_value(value, type_name):
    expected = TYPES.get(type_name)
    valid = {'str': lambda: isinstance(value, str), 'int': lambda: type(value) is int,
             'float': lambda: type(value) in {int, float}, 'bool': lambda: type(value) is bool,
             'dict': lambda: isinstance(value, dict), 'list': lambda: isinstance(value, list),
             'bytes': lambda: isinstance(value, (bytes, bytearray))}
    if expected in valid and not valid[expected]():
        raise TypeError('返回/参数值与声明类型不符: ' + type_name)
    if expected is None and value.__class__.__name__ != type_name:
        raise TypeError('自定义返回/参数类型不符: ' + type_name)
    bounds = {'字节型': (0,255), '整数型': (-2**31,2**31-1), '长整数型': (-2**63,2**63-1)}
    if type_name in bounds and not bounds[type_name][0] <= value <= bounds[type_name][1]:
        raise ValueError('返回/参数值超出声明范围: ' + type_name)
    return value


def compile_source(source, filename, *, metadata=None, data=None, file=None):
    suffix = Path(filename).suffix
    original_chinese = source
    if suffix == ".zhxb":
        from .compiler import emit_python
        source = emit_python(source)
    tree = ast.parse(source, filename=filename)
    file = file or Path(filename).as_posix()
    metadata = metadata or {}
    data = data or {"variables": [], "constants": [], "types": []}
    custom_types = {item["id"] for item in data.get("types", [])}
    global_ids = {item["id"] for item in data.get("variables", []) + data.get("constants", []) if item["scope"] == "global"}
    constants = {item["id"] for item in data.get("constants", []) if item["scope"] == "global"}
    chinese_locals = {}
    chinese_procedures = {}
    if suffix == ".zhxb":
        from .compiler import parse
        chinese_procedures = {procedure.name: procedure for procedure in parse(original_chinese).procedures}
        chinese_locals = {name: {item['name'] for item in procedure.locals} for name, procedure in chinese_procedures.items()}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stored = find_metadata(metadata, file, node.name, node.lineno)
        names = {arg.arg for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs + ([node.args.vararg] if node.args.vararg else []) + ([node.args.kwarg] if node.args.kwarg else [])}
        locals_data = [{"id": item["name"], "type": item["type"], "default": item.get("defaultValue", ""),
                        "description": item.get("remark", "")} for item in stored.get("locals", [])]
        locals_data += [item for item in data.get("variables", []) + data.get("constants", [])
                       if item["scope"] == "local" and item.get("owner") in {node.name, f"{file}:{node.name}"}]
        local_names = [item["id"] for item in locals_data]
        if len(local_names) != len(set(local_names)) or set(local_names) & names:
            raise ValueError(f"{file}:{node.name} 参数和局部变量重复")
        prefix = []
        if node.name in chinese_procedures:
            for parameter in chinese_procedures[node.name].parameters:
                if 'line' not in parameter:
                    continue
                checked = ast.parse(f"{parameter['name']} = __pcide_check_value__({parameter['name']}, {parameter['type']!r})").body[0]
                for child in ast.walk(checked):
                    if hasattr(child, 'lineno'):
                        child.lineno = child.end_lineno = parameter['line']
                prefix.append(checked)
        for item in locals_data:
            expression = (item["type"] + "()" if item["type"] in custom_types and not item.get("default")
                          else _initializer(item, "python", item in data.get("constants", [])))
            if item.get("static"):
                expression = f"__pcide_static__.setdefault({file + ':' + node.name + ':' + item['id']!r}, {expression})"
            assignment = ast.parse(f"{item['id']} = {expression}").body[0]
            # Generated declarations use the declaration's source location;
            # user statement/breakpoint/traceback line numbers stay intact.
            for child in ast.walk(assignment):
                if hasattr(child, "lineno"):
                    child.lineno = child.end_lineno = node.lineno
            prefix.append(assignment)
        node.body = prefix + node.body
        node._pcide_local_names = names | set(local_names)
        return_type = stored.get('returnType', '')
        if suffix == '.zhxb' and not return_type:
            from .compiler import parse
            return_type = next((procedure.return_type for procedure in parse(original_chinese).procedures if procedure.name == node.name), '')
        if return_type:
            if return_type not in TYPES and return_type not in custom_types:
                raise ValueError('返回类型没有具体声明: ' + return_type)
            class ReturnTransformer(ast.NodeTransformer):
                def visit_Return(self, returned):
                    returned.value = ast.copy_location(ast.Call(ast.Name('__pcide_check_value__', ast.Load()),
                                                                [returned.value or ast.Constant(None), ast.Constant(return_type)], []), returned)
                    return returned
                def visit_FunctionDef(self, nested):
                    return nested
                visit_AsyncFunctionDef = visit_FunctionDef
                def visit_Lambda(self, nested):
                    return nested
            node.body = [ReturnTransformer().visit(statement) for statement in node.body]

    class ScopeTransformer(ast.NodeTransformer):
        def __init__(self):
            self.shadow = set()
            self.static_names = {}
        def visit_FunctionDef(self, node):
            previous = self.shadow
            previous_static = self.static_names
            self.static_names = {**previous_static, **{item['id']: file + ':' + node.name + ':' + item['id'] for item in data.get('variables', [])
                                 if item['scope'] == 'local' and item.get('static') and item.get('owner') in {node.name, f'{file}:{node.name}'}}}
            self.shadow = previous | getattr(node, "_pcide_local_names", {arg.arg for arg in node.args.args})
            # Explicit local declarations in zhxb stay local too.
            self.shadow |= chinese_locals.get(node.name, set())
            node = self.generic_visit(node)
            self.shadow = previous
            self.static_names = previous_static
            return node
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_Lambda(self, node):
            previous = self.shadow
            previous_static = self.static_names
            parameters = {arg.arg for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs + ([node.args.vararg] if node.args.vararg else []) + ([node.args.kwarg] if node.args.kwarg else [])}
            self.shadow = previous | parameters
            self.static_names = {name: value for name, value in previous_static.items() if name not in parameters}
            node = self.generic_visit(node)
            self.shadow = previous
            self.static_names = previous_static
            return node
        def visit_Name(self, node):
            if node.id in self.static_names:
                return ast.copy_location(ast.Subscript(ast.Name('__pcide_static__', ast.Load()), ast.Constant(self.static_names[node.id]), node.ctx), node)
            if node.id in global_ids - self.shadow:
                if isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in constants:
                    raise ValueError("常量不能赋值或删除: " + node.id)
                return ast.copy_location(ast.Attribute(ast.Name("__pcide_data__", ast.Load()), node.id, node.ctx), node)
            return node
        def visit_Global(self, node):
            node.names = [name for name in node.names if name not in global_ids]
            return node if node.names else ast.copy_location(ast.Pass(), node)
    tree = ScopeTransformer().visit(tree)
    return compile(ast.fix_missing_locations(tree), filename, "exec")
