"""Small versioned Chinese source compiler contract.

It provides a deterministic lexer/parser/IR boundary that future native backends
can consume. The current emitter targets the existing Python runtime.
"""
from __future__ import annotations

import hashlib
import ast
import io
import keyword
import re
import tokenize
from dataclasses import dataclass, field
from typing import Any

COMPILER_VERSION = 4

_TYPES = {"", "文本型", "数值型", "整数型", "长整数型", "小数型", "双精度小数型",
          "逻辑型", "逻辑型(布尔型)", "字节型", "日期时间型", "字节集", "对象型", "数组型"}

def _identifier(name):
    return name.isidentifier() and not keyword.iskeyword(name) and name not in {"event", "__zhxb_entrypoint__"} and not name.startswith("__pcide_")

def translate_literals(source):
    """Rewrite NAME tokens only; strings and comments remain byte-for-byte."""
    replacements = {"真": "True", "是": "True", "假": "False", "否": "False", "空": "None"}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        return tokenize.untokenize([token._replace(string=replacements.get(token.string, token.string))
                                   if token.type == tokenize.NAME else token for token in tokens])
    except (tokenize.TokenError, IndentationError) as exc:
        raise CompilerError("表达式 token 无效") from exc

def _default(item):
    from .data import _initializer
    # Declared initial values are literals, never arbitrary evaluated code.
    return _initializer({"type": item["type"], "default": item.get("default", "")}, "python")

class CompilerError(ValueError):
    pass

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int

@dataclass
class Procedure:
    name: str
    body: list[str] = field(default_factory=list)
    line: int = 1
    statement_lines: list[int] = field(default_factory=list)
    parameters: list[dict[str, str]] = field(default_factory=list)
    locals: list[dict[str, str]] = field(default_factory=list)
    return_type: str = ""
    public: bool = False
    remark: str = ""

@dataclass
class ProgramIR:
    version: str = "2"
    assembly: str = ""
    procedures: list[Procedure] = field(default_factory=list)
    imports: list[tuple[str, int]] = field(default_factory=list)

_TOKEN = re.compile(
    r"(?P<header>^[ \t]*\.版本[ \t]+(?P<version>\d+)[ \t]*$)|"
    r"(?P<assembly>^[ \t]*\.程序集[ \t]*(?P<assembly_name>.*)$)|"
    r"(?P<procedure>^[ \t]*\.子程序[ \t]+(?P<procedure_name>[\w\u4e00-\u9fff]+)"
    r"(?:[ \t]*\((?P<procedure_params>[^)]*)\))?(?:[ \t]*,[ \t]*(?P<procedure_meta>.*))?[ \t]*$)|"
    r"(?P<parameter>^[ \t]*\.参数[ \t]+(?P<parameter_value>.*)$)|"
    r"(?P<local>^[ \t]*\.局部变量[ \t]+(?P<local_value>.*)$)|"
    r"(?P<comment>^[ \t]*(?://|').*$)|(?P<text>.*)$")

def lex(source: str) -> list[Token]:
    if not isinstance(source, str) or len(source) > 2 * 1024 * 1024:
        raise CompilerError("中文源码为空或超过 2MB")
    tokens = []
    for line_no, line in enumerate(source.splitlines(), 1):
        match = _TOKEN.match(line)
        if not match:
            raise CompilerError(f"第 {line_no} 行无法识别")
        if match.group("header"):
            tokens.append(Token("version", match.group("version"), line_no))
        elif match.group("assembly"):
            tokens.append(Token("assembly", match.group("assembly_name").strip(), line_no))
        elif match.group("procedure"):
            params = match.group("procedure_params") or ""
            meta = match.group("procedure_meta") or ""
            tokens.append(Token("procedure", "\x1f".join((match.group("procedure_name"), params, meta)), line_no))
        elif match.group("parameter"):
            tokens.append(Token("parameter", match.group("parameter_value").strip(), line_no))
        elif match.group("local"):
            tokens.append(Token("local", match.group("local_value").strip(), line_no))
        elif match.group("comment") or not line.strip():
            continue
        else:
            tokens.append(Token("statement", line.strip(), line_no))
    return tokens

def parse(source: str) -> ProgramIR:
    program = ProgramIR()
    seen_version = False
    current: Procedure | None = None
    for token in lex(source):
        if token.kind == "version":
            if seen_version or token.value != "2":
                raise CompilerError("只支持 .版本 2")
            program.version = token.value
            seen_version = True
        elif token.kind == "assembly":
            if program.assembly:
                raise CompilerError("程序集只能声明一次")
            program.assembly = token.value
        elif token.kind == "procedure":
            name, raw_params, raw_meta = (token.value.split("\x1f", 2) + ["", ""])[:3]
            if not _identifier(name):
                raise CompilerError(f"第 {token.line} 行子程序名非法")
            if any(item.name == name for item in program.procedures):
                raise CompilerError(f"子程序重复: {name}")
            return_type, public, remark = _procedure_meta(raw_meta)
            if return_type not in _TYPES:
                raise CompilerError(f"第 {token.line} 行返回类型不支持: {return_type}")
            current = Procedure(name, line=token.line, return_type=return_type, public=public, remark=remark)
            current.parameters.extend(_parameter_list(raw_params, token.line))
            program.procedures.append(current)
        elif token.kind in {"parameter", "local"}:
            if current is None:
                raise CompilerError(f"第 {token.line} 行声明不在子程序中")
            declarations = _declarations(token.value, token.line, "参数" if token.kind == "parameter" else "局部变量")
            (current.parameters if token.kind == "parameter" else current.locals).extend(declarations)
            names = [item["name"] for item in current.parameters + current.locals]
            if len(names) != len(set(names)):
                raise CompilerError(f"第 {token.line} 行变量重复")
        elif token.kind == "statement":
            imported = re.fullmatch(r"(?:\.导入|导入)\s+([^\W\d]\w*(?:\.[^\W\d]\w*)*)", token.value)
            if imported:
                if current:
                    raise CompilerError(f"第 {token.line} 行导入必须位于子程序前")
                program.imports.append((imported.group(1), token.line))
                continue
            if current is None:
                raise CompilerError(f"第 {token.line} 行语句不在子程序中")
            current.body.append(token.value)
            current.statement_lines.append(token.line)
    if not seen_version:
        raise CompilerError("缺少 .版本 2")
    if not program.procedures:
        raise CompilerError("至少需要一个子程序")
    # Compile all statements while parsing so unsupported syntax cannot be
    # silently discarded, including writes performed by the IDE Agent.
    for procedure in program.procedures:
        optional_seen=False
        for parameter in procedure.parameters:
            if optional_seen and not parameter.get('has_default',False):
                raise CompilerError('必填参数必须放在可省略参数之前')
            optional_seen |= parameter.get('has_default',False)
        names = [item["name"] for item in procedure.parameters + procedure.locals]
        if len(names) != len(set(names)):
            raise CompilerError(f"第 {procedure.line} 行参数/局部变量重复")
        stack = []
        for index, statement in enumerate(procedure.body):
            line = procedure.statement_lines[index]
            generated = _statement(statement, line)
            if generated.startswith(("if ", "while ", "for ")):
                stack.append("if" if generated.startswith("if ") else "loop")
            elif generated == "#end-if" or generated == "#end-loop":
                expected = "if" if generated == "#end-if" else "loop"
                if not stack or stack.pop() != expected:
                    raise CompilerError(f"第 {line} 行结束标记不匹配")
            elif generated.startswith(("else:", "elif ")) and (not stack or stack[-1] != "if"):
                raise CompilerError(f"第 {line} 行否则没有对应如果")
        if stack:
            raise CompilerError(f"第 {procedure.line} 行控制流没有结束标记")
    return program


def _declarations(raw: str, line: int, kind: str) -> list[dict[str, str]]:
    """Parse Yi-style comma-separated parameter/local declarations."""
    if not raw.strip():
        return []
    result = []
    for part in raw.split(";") if ";" in raw else [raw]:
        fields = [value.strip() for value in part.split(",", 3)]
        name = fields[0]
        if not _identifier(name):
            raise CompilerError(f"第 {line} 行{kind}名非法")
        typ = fields[1] if len(fields) > 1 and fields[1] else "文本型"
        if typ not in _TYPES - {""}:
            raise CompilerError(f"第 {line} 行{kind}类型不支持: {typ}")
        result.append({"name": name, "type": typ, "line": line,
                       "has_default": kind=='参数' and len(fields)>2,
                       "default": fields[2] if len(fields) > 2 else "",
                       "remark": fields[3] if len(fields) > 3 else ""})
        try:
            _default(result[-1])
        except ValueError as exc:
            raise CompilerError(f"第 {line} 行初始值与类型不符") from exc
    return result


def _parameter_list(raw: str, line: int) -> list[dict[str, str]]:
    """Parse the compact ``.子程序 Foo(a, b)`` spelling used by the editor."""
    if not raw.strip():
        return []
    if ";" in raw:
        return _declarations(raw, line, "参数")
    result = []
    for name in (value.strip() for value in raw.split(",")):
        if not _identifier(name):
            raise CompilerError(f"第 {line} 行参数名非法")
        result.append({"name": name, "type": "文本型", "default": "", "remark": "", "has_default":False})
    return result


def _procedure_meta(raw: str) -> tuple[str, bool, str]:
    fields = [value.strip() for value in raw.split(",", 2)] if raw.strip() else []
    return_type = fields[0] if fields else ""
    public = len(fields) > 1 and fields[1] in {"公开", "Public", "public", "真", "是"}
    remark = fields[2] if len(fields) > 2 else ""
    return return_type, public, remark


def _statement(statement: str, line: int) -> str:
    statement = statement.strip().rstrip(";")
    if statement in {"结束如果", "结束循环"}:
        return "#end-if" if statement == "结束如果" else "#end-loop"
    if statement == "否则":
        return "else:"
    control = re.fullmatch(r"(如果|否则如果|循环)\s*(?:\((.*)\)|\s+(.+))", statement)
    iteration = re.fullmatch(r"遍历\s+([^,]+),\s*(.+)", statement)
    if control or iteration:
        if control:
            kind = {"如果": "if", "否则如果": "elif", "循环": "while"}[control.group(1)]
            expression = translate_literals(control.group(2) or control.group(3))
            generated = f"{kind} {expression}:"
        else:
            if not _identifier(iteration.group(1).strip()):
                raise CompilerError(f"第 {line} 行迭代变量非法")
            generated = f"for {iteration.group(1).strip()} in {translate_literals(iteration.group(2))}:"
        try:
            ast.parse(generated + "\n    pass")
        except SyntaxError as exc:
            raise CompilerError(f"第 {line} 行条件/迭代表达式非法") from exc
        return generated
    output = re.fullmatch(r"(?:输出|信息框|调试输出)\s*\((.*)\)", statement)
    returned = re.fullmatch(r"返回(?:\s*\((.*)\))?", statement)
    assigned = re.fullmatch(r"赋值\s*\(([^,]+),\s*(.*)\)", statement)
    called = re.fullmatch(r"调用\s+(.+)", statement)
    if output:
        generated = f"print({output.group(1)})"
    elif returned:
        generated = "return" if returned.group(1) is None else f"return {returned.group(1)}"
    elif assigned:
        generated = f"{assigned.group(1).strip()} = {assigned.group(2).strip()}"
    elif called:
        generated = called.group(1).strip()
    else:
        generated = statement
    # Keep common Yi-style boolean/null literals usable in normal Python
    # expressions without rewriting quoted text.
    generated = translate_literals(generated)
    try:
        nodes = ast.parse(generated).body
        if len(nodes) != 1 or not isinstance(nodes[0], (ast.Assign, ast.AugAssign, ast.Expr, ast.Return)):
            raise ValueError("当前支持赋值、表达式、函数调用和返回")
        if isinstance(nodes[0], ast.Expr) and not isinstance(nodes[0].value, ast.Call):
            raise ValueError("表达式语句必须是函数调用")
    except (SyntaxError, ValueError) as exc:
        raise CompilerError(f"第 {line} 行语句不受支持或语法错误: {statement}") from exc
    return generated

def emit_python(program: ProgramIR | str) -> str:
    ir = parse(program) if isinstance(program, str) else program
    lines = []
    for module, line in ir.imports:
        lines.extend([""] * (line-1-len(lines)))
        lines.append("import " + module)
    entry_name = None
    for index, procedure in enumerate(ir.procedures):
        function_name = procedure.name if procedure.name.isidentifier() else "zhxb_" + hashlib.sha256(procedure.name.encode("utf-8")).hexdigest()[:12]
        if procedure.name in {"主程序", "_启动程序"}:
            if entry_name:
                raise CompilerError("软件启动入口重复")
            entry_name = function_name
        if len(lines) < procedure.line - 1:
            lines.extend([""] * (procedure.line - 1 - len(lines)))
        parameters = [f"{item['name']}={_default(item)}" if item.get('has_default',False) else item['name'] for item in procedure.parameters]
        parameters += ["*", "event=None"]
        lines.append(f"def {function_name}({', '.join(parameters)}):")
        for local in procedure.locals:
            default = _default(local)
            local_line = int(local.get("line", len(lines) + 1))
            if len(lines) < local_line - 1:
                lines.extend([""] * (local_line - 1 - len(lines)))
            lines.append(f"    {local['name']} = {default}")
        if procedure.body:
            depth = 1
            for statement_index, statement in enumerate(procedure.body):
                line = procedure.statement_lines[statement_index] if procedure.statement_lines else len(lines) + 1
                if len(lines) < line - 1:
                    lines.extend([""] * (line - 1 - len(lines)))
                generated = _statement(statement, line)
                if generated.startswith("#end-"):
                    depth -= 1
                    lines.append("    " * (depth + 1) + "pass")
                    continue
                if generated.startswith(("else:", "elif ")):
                    depth -= 1
                lines.append("    " * depth + generated)
                if generated.endswith(":"):
                    depth += 1
        else:
            lines.append("    pass")
    if entry_name:
        lines.append("")
        lines.extend(["def __zhxb_entrypoint__(event=None):", f"    return {entry_name}(event=event)", ""])
    result = "\n".join(lines)
    try:
        compile(result, "<zhxb>", "exec")
    except SyntaxError as exc:
        raise CompilerError(f"中文源码生成失败: {exc}") from exc
    return result
