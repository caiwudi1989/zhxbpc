"""Editing ranges only: tolerate unfinished source without swallowing top-level code."""
from __future__ import annotations

import ast
import io
import re
import tokenize

from pcide.core.routines import scan


def scan_editor(source, suffix):
    lines = source.split('\n')
    routines = scan(source, suffix)
    if suffix == '.py':
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        if tree:
            nodes = {node.lineno: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for item in routines:
                node = nodes[item['line']]
                item.update(bodyLine=node.body[0].lineno, bodyColumn=node.body[0].col_offset + 1)
            return routines
        # Token positions distinguish strings/comments from code, including
        # multiline strings. Keep the partial token stream on syntax errors.
        masked = [list(line) for line in lines]
        try:
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type not in {tokenize.STRING, tokenize.COMMENT}:
                    continue
                for row in range(token.start[0], min(token.end[0], len(lines)) + 1):
                    start = token.start[1] if row == token.start[0] else 0
                    end = token.end[1] if row == token.end[0] else len(lines[row-1])
                    masked[row-1][start:end] = ' ' * (end-start)
                if token.type == tokenize.STRING:
                    masked[token.start[0]-1][token.start[1]] = 'x'
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
        masked = [''.join(line) for line in masked]
        routines = [{'sourceName': match.group(1), 'line': row+1, 'parameters': []}
                    for row, line in enumerate(masked)
                    if (match := re.match(r'^(?:async[ \t]+)?def[ \t]+([^\W\d]\w*)[ \t]*\(', line))]
        for item in routines:
            start = item['line'] - 1
            indent = len(lines[start].expandtabs(4)) - len(lines[start].lstrip().expandtabs(4))
            depth, header_end = 0, start
            for row in range(start, len(lines)):
                for char in masked[row]:
                    depth += 1 if char in '([{' else -1 if char in ')]}' else 0
                header_end = row
                if depth <= 0 and ':' in masked[row]:
                    break
            end = len(lines)
            depth = 0
            for row in range(header_end+1, len(lines)):
                text = masked[row]
                current_indent = len(text.expandtabs(4)) - len(text.lstrip().expandtabs(4))
                if text.strip() and depth <= 0 and current_indent <= indent:
                    end = row
                    break
                depth += sum(char in '([{' for char in text) - sum(char in ')]}' for char in text)
            body = next((row for row in range(header_end+1, end) if masked[row].strip()), min(header_end+1, len(lines)-1))
            item.update(endLine=end, bodyLine=body+1, bodyColumn=len(lines[body])-len(lines[body].lstrip())+1)
    elif suffix in {'.js', '.ts'}:
        # Mask literals before brace matching; regex literals and templates may
        # contain braces, as may comments. Preserve offsets and newlines.
        pattern = r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`|/(?=[^/*\n])(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\n\\])+/[a-z]*"
        masked = re.sub(pattern, lambda m: re.sub(r'[^\n]', ' ', m[0]), source)
        offsets = [0]
        for line in source.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        # Build the UI list from masked declarations, including async forms.
        # Runtime metadata scanning remains a separate execution contract.
        from pcide.core.routine_signatures import parameter_details
        declarations = re.finditer(r'(?m)^[ \t]*(?:export[ \t]+)?(?:async[ \t]+)?function[ \t]+([^\W\d]\w*)[ \t]*\(', masked)
        routines = []
        for match in declarations:
            item = {'sourceName': match.group(1), 'line': source.count('\n', 0, match.start()) + 1, 'parameters': []}
            try:
                item['parameters'] = [param['name'] for param in parameter_details(source[match.start():], suffix, item['sourceName'])]
            except ValueError:
                pass
            routines.append(item)
        for item in routines:
            start = offsets[item['line']-1]
            parameters = masked.find('(', start)
            depth = 0
            opening = parameters
            for offset in range(max(0, parameters), len(masked)):
                depth += 1 if masked[offset] == '(' else -1 if masked[offset] == ')' else 0
                if depth == 0:
                    opening = masked.find('{', offset+1)
                    break
            if opening < 0:
                item.update(endLine=item['line'], bodyLine=item['line'], bodyColumn=1)
                continue
            depth, closing = 0, len(source)-1
            for offset in range(opening, len(masked)):
                depth += 1 if masked[offset] == '{' else -1 if masked[offset] == '}' else 0
                if depth == 0:
                    closing = offset
                    break
            body = opening+1
            while body < closing and source[body].isspace():
                body += 1
            body_line = source.count('\n', 0, body)+1
            item.update(endLine=source.count('\n', 0, closing)+1, bodyLine=body_line,
                        bodyColumn=body-source.rfind('\n', 0, body))
    else:
        for item in routines:
            item.update(bodyLine=min(item['line']+1, max(1, len(lines))), bodyColumn=1)
    return routines
