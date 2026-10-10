"""Source identities and editor metadata. Line numbers are locations, not IDs."""
from __future__ import annotations

import ast
import io
import keyword
import re
import tokenize
from pathlib import Path


RETURN_TYPES = ["", "文本型", "数值型", "整数型", "长整数型", "小数型", "双精度小数型",
                "逻辑型(布尔型)", "字节型", "日期时间型", "字节集", "对象型", "数组型", "自定义类型"]


def scan(source, suffix):
    if suffix in {".py", ".pyc"}:
        try:
            tree = ast.parse(source)
            return [{"sourceName": node.name, "line": node.lineno, "endLine": node.end_lineno,
                     "parameters": [arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs + ([node.args.vararg] if node.args.vararg else []) + ([node.args.kwarg] if node.args.kwarg else [])]}
                    for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        except SyntaxError:
            pattern = r"(?m)^def[ \t]+([^\W\d]\w*)[ \t]*\("
    elif suffix == ".zhxb":
        try:
            from .compiler import parse
            procedures=parse(source).procedures
            return [{'sourceName':p.name,'line':p.line,'endLine':procedures[index+1].line-1 if index+1<len(procedures) else len(source.splitlines()),
                     'parameters':[item['name'] for item in p.parameters]} for index,p in enumerate(procedures)]
        except ValueError:
            pass
        pattern = r"(?m)^[ \t]*\.子程序[ \t]+([^\W\d]\w*)"
    else:
        pattern = r"(?m)^[ \t]*(?:export[ \t]+)?function[ \t]+([^\W\d]\w*)[ \t]*\("
    matches = list(re.finditer(pattern, source))
    result = [{"sourceName": match.group(1), "line": source.count("\n", 0, match.start()) + 1,
             "endLine": source.count("\n", 0, matches[index+1].start()) if index+1 < len(matches) else len(source.splitlines()),
             "parameters": []} for index, match in enumerate(matches)]
    if suffix in {'.js','.ts'}:
        from .routine_signatures import parameter_details
        for item in result:
            try:
                item['parameters']=[p['name'] for p in parameter_details(source,suffix,item['sourceName'])]
            except ValueError:
                pass
    return result


def find_metadata(index, file, name, line):
    for value in index.values():
        if isinstance(value, dict) and value.get("file") == file and value.get("sourceName") == name:
            return value
    value = index.get(f"{file}:{line}", {})
    # Never assign metadata from another routine merely because its line moved.
    return value if isinstance(value, dict) and value.get("sourceName", name) == name else {}


def reconcile(index, file, source, suffix):
    result = {key: value for key, value in index.items() if isinstance(value, dict) and value.get("file") != file}
    for routine in scan(source, suffix):
        value = find_metadata(index, file, routine["sourceName"], routine["line"])
        if value:
            value = {**value, **routine, "file": file}
            result[f"{file}:{routine['line']}"] = value
    return result


def rename_identifier(source, suffix, old, new):
    if not new.isidentifier() or keyword.iskeyword(new) or len(new) > 128:
        raise ValueError("子程序名必须是有效标识符")
    if old == new:
        return source
    if any(item["sourceName"] == new for item in scan(source, suffix)):
        raise ValueError("子程序名称重复")
    if suffix in {".py", ".zhxb"}:
        # NAME tokens preserve strings and comments. Attribute references are
        # included so module-qualified calls follow an edited public name.
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        return tokenize.untokenize([token._replace(string=new) if token.type == tokenize.NAME and token.string == old else token for token in tokens])
    pattern = re.compile(r"('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`|//[^\n]*|/\*[\s\S]*?\*/)|([^\W\d]\w*)")
    return pattern.sub(lambda match: match.group(1) if match.group(1) is not None else new if match.group(2) == old else match.group(2), source)
