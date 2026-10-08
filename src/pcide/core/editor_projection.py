"""Reversible Chinese keyword view; strings/comments are never rewritten."""
import re

PYTHON_WORDS = {"def": "子程序", "return": "返回", "if": "如果", "elif": "否则如果", "else": "否则",
    "for": "计次循环", "while": "判断循环", "in": "在", "break": "跳出循环", "continue": "继续循环",
    "True": "真", "False": "假", "None": "空", "and": "且", "or": "或", "not": "非",
    "import": "导入", "from": "从", "as": "作为", "class": "数据类型", "pass": "空语句",
    "try": "尝试", "except": "捕获", "finally": "最终", "raise": "抛出", "with": "使用",
    "global": "全局", "nonlocal": "外层", "print": "调试输出", "str": "文本型", "int": "整数型",
    "float": "小数型", "bool": "逻辑型", "len": "取长度", "range": "范围", "event": "事件"}
JS_WORDS = {"function": "子程序", "return": "返回", "if": "如果", "else": "否则", "for": "循环",
    "while": "判断循环", "break": "跳出循环", "continue": "继续循环", "true": "真", "false": "假",
    "null": "空", "const": "常量", "let": "变量", "var": "变量声明", "class": "数据类型",
    "new": "新建", "try": "尝试", "catch": "捕获", "finally": "最终", "throw": "抛出", "event": "事件"}


def transform(text, language, reverse=False):
    mapping = PYTHON_WORDS if language == "python" else JS_WORDS if language in {"javascript", "typescript"} else {}
    if reverse:
        mapping = {value: key for key, value in mapping.items()}
    pattern = (r"\#.*?$|'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\w+"
               if language == "python" else r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`|\w+")
    return re.sub(pattern, lambda match: mapping.get(match.group(0), match.group(0)), text, flags=re.MULTILINE)
