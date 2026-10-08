"""Small versioned Chinese source compiler contract.

It provides a deterministic lexer/parser/IR boundary that future native backends
can consume. The current emitter targets the existing Python runtime.
"""
from __future__ import annotations

import hashlib
import ast
import re
from dataclasses import dataclass, field
from typing import Any

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

@dataclass
class ProgramIR:
    version: str = "2"
    assembly: str = ""
    procedures: list[Procedure] = field(default_factory=list)

_TOKEN = re.compile(r"(?P<header>^\s*\.版本\s+(?P<version>\d+)\s*$)|(?P<assembly>^\s*\.程序集\s*(?P<assembly_name>.*)$)|(?P<procedure>^\s*\.子程序\s+(?P<procedure_name>[\w\u4e00-\u9fff]+)\s*$)|(?P<comment>^\s*//.*$)|(?P<text>.*)$")

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
            tokens.append(Token("procedure", match.group("procedure_name"), line_no))
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
            if not token.value.isidentifier() or token.value == "__zhxb_entrypoint__":
                raise CompilerError(f"第 {token.line} 行子程序名非法")
            if any(item.name == token.value for item in program.procedures):
                raise CompilerError(f"子程序重复: {token.value}")
            current = Procedure(token.value, line=token.line)
            program.procedures.append(current)
        elif token.kind == "statement":
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
        for index, statement in enumerate(procedure.body):
            _statement(statement, procedure.statement_lines[index])
    return program


def _statement(statement: str, line: int) -> str:
    output = re.fullmatch(r"(?:输出|信息框)\s*\((.*)\)", statement)
    generated = f"print({output.group(1)})" if output else statement
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
    entry_name = None
    main_name = None
    for index, procedure in enumerate(ir.procedures):
        function_name = procedure.name if procedure.name.isidentifier() else "zhxb_" + hashlib.sha256(procedure.name.encode("utf-8")).hexdigest()[:12]
        if index == 0:
            entry_name = function_name
        if procedure.name == "主程序":
            main_name = function_name
        if len(lines) < procedure.line - 1:
            lines.extend([""] * (procedure.line - 1 - len(lines)))
        lines.append(f"def {function_name}(event=None):")
        if procedure.body:
            for statement_index, statement in enumerate(procedure.body):
                line = procedure.statement_lines[statement_index] if procedure.statement_lines else len(lines) + 1
                if len(lines) < line - 1:
                    lines.extend([""] * (line - 1 - len(lines)))
                lines.append("    " + _statement(statement, line))
        else:
            lines.append("    pass")
    if entry_name:
        entry_name = main_name or entry_name
        lines.append("")
        lines.extend(["def __zhxb_entrypoint__(event=None):", f"    return {entry_name}(event)", ""])
    result = "\n".join(lines)
    try:
        compile(result, "<zhxb>", "exec")
    except SyntaxError as exc:
        raise CompilerError(f"中文源码生成失败: {exc}") from exc
    return result
