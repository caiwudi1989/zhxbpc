"""Project data/API table contract and deterministic source generation."""
from __future__ import annotations

import copy
import json
import math
import re
import keyword
from typing import Any

from .i18n import make_id

SCOPES = ("global", "window", "module", "local")
SCOPE_LABELS = {"global": "全局", "window": "窗口", "module": "模块", "local": "局部"}
TYPES = {"文本": "str", "文本型": "str", "字符串": "str", "整数": "int", "整数型": "int", "长整数型": "int", "字节型": "int", "小数": "float", "小数型": "float", "数值型": "float", "双精度小数型": "float", "布尔": "bool", "逻辑型": "bool", "逻辑型(布尔型)": "bool", "对象": "dict", "对象型": "dict", "数组": "list", "数组型": "list", "日期时间型": "str", "字节集": "bytes"}
CALLING_CONVENTIONS = ("cdecl", "stdcall", "winapi")
_ID = re.compile(r"^[^\W\d]\w{0,63}$", re.UNICODE)


class DataError(ValueError):
    pass


def _text(value, field, limit=256, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise DataError(f"invalid {field}")
    return value


def _identity(item, field="id"):
    value = item.get(field, "")
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DataError(f"invalid {field}")
    if keyword.iskeyword(value) or value.startswith('__pcide_') or value in {'__builtins__', 'process', 'require', 'console', 'Buffer', 'globalThis'}:
        raise DataError('reserved data identifier: ' + value)
    return value


def _name(item, fallback):
    label = item.get("label", item.get("name", fallback))
    label = _text(label, "label", 128, True)
    if any(ord(character) < 32 for character in label):
        raise DataError("label cannot contain control characters")
    return label


def _normalize_variables(raw, constants=False, used=()):
    if not isinstance(raw, list) or len(raw) > 1000:
        raise DataError("variables/constants must be an array")
    result = []
    ids = set(used)
    for index, source in enumerate(raw):
        if not isinstance(source, dict):
            raise DataError("data item must be an object")
        item = copy.deepcopy(source)
        if "id" not in item:
            item["id"] = make_id(item.get("label", item.get("name", f"item_{index + 1}")), "value", ids)
        _identity(item)
        if item["id"] in ids:
            raise DataError("duplicate data ID")
        ids.add(item["id"])
        item["label"] = _name(item, item["id"])
        item.setdefault("type", "文本")
        _text(item["type"], "type", 32, True)
        scope = item.get("scope", "global")
        scope = next((key for key, label in SCOPE_LABELS.items() if scope == label), scope)
        if scope not in SCOPES:
            raise DataError("invalid variable scope")
        item["scope"] = scope
        item["owner"] = _text(item.get("owner", ""), "owner", 128)
        item["static"] = item.get("static", False)
        if type(item["static"]) is not bool:
            raise DataError("static must be boolean")
        item["array"] = _text(item.get("array", ""), "array", 64)
        if item["array"] and (not re.fullmatch(r"[1-9]\d*(?:,[1-9]\d*)*", item["array"]) or math.prod(map(int, item["array"].split(","))) > 10000):
            raise DataError("array limit: 10000 elements")
        if constants:
            item["value"] = str(item.get("value", item.get("default", "")))
            item.pop("default", None)
        else:
            item["default"] = str(item.get("default", ""))
            item.pop("value", None)
        item["description"] = _text(item.get("description", ""), "description", 1024)
        result.append(item)
    return result


def _normalize_params(params):
    if not isinstance(params, list) or len(params) > 64:
        raise DataError("API parameters must be an array")
    result = []
    ids = set()
    for index, source in enumerate(params):
        if not isinstance(source, dict):
            raise DataError("API parameter must be an object")
        item = copy.deepcopy(source)
        if "id" not in item:
            item["id"] = make_id(item.get("label", item.get("name", f"arg_{index + 1}")), "arg", ids)
        _identity(item)
        if item["id"] in ids:
            raise DataError("duplicate API parameter ID")
        ids.add(item["id"])
        item["label"] = _name(item, item["id"])
        item["type"] = _text(item.get("type", "整数"), "parameter type", 32, True)
        item["description"] = _text(item.get("description", ""), "parameter description", 512)
        result.append(item)
    return result


def validate_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataError("data table must be an object")
    version = value.get("version", 1)
    if type(version) is not int:
        raise DataError("invalid data schema version")
    variables = _normalize_variables(value.get("variables", []))
    constants = _normalize_variables(value.get("constants", []), True, {item["id"] for item in variables})
    result = {"version": version,
              "variables": variables,
              "constants": constants,
              "apis": [], "types": []}
    if result["version"] != 1:
        raise DataError("unsupported data schema")
    ids = {item["id"] for item in result["variables"] + result["constants"]}
    if len(ids) != len(result["variables"]) + len(result["constants"]):
        raise DataError("duplicate data ID")
    for source in value.get("apis", []):
        if not isinstance(source, dict):
            raise DataError("API item must be an object")
        item = copy.deepcopy(source)
        if "id" not in item:
            item["id"] = make_id(item.get("label", item.get("name", "api")), "api", ids)
        _identity(item)
        if item["id"] in ids:
            raise DataError("duplicate data ID")
        ids.add(item["id"])
        item["label"] = _name(item, item["id"])
        item["library"] = _text(item.get("library", ""), "library", 260)
        item["entry"] = _text(item.get("entry", item["id"]), "API entry", 128, True)
        item["return_type"] = _text(item.get("return_type", item.get("return", "整数")), "return type", 32, True)
        item["calling_convention"] = item.get("calling_convention", item.get("calling", "cdecl"))
        if item["calling_convention"] not in CALLING_CONVENTIONS:
            raise DataError("invalid API calling convention")
        permissions = item.get("permissions", [])
        if not isinstance(permissions, list) or any(not isinstance(p, str) or not p.strip() for p in permissions):
            raise DataError("API permissions must be an array")
        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(p, str) or not p.strip() for p in dependencies):
            raise DataError("API dependencies must be an array")
        item["permissions"] = list(dict.fromkeys(permissions))
        item["dependencies"] = list(dict.fromkeys(dependencies))
        item["parameters"] = _normalize_params(item.get("parameters", item.get("params", [])))
        item["description"] = _text(item.get("description", ""), "API description", 1024)
        result["apis"].append(item)
    if len(result["apis"]) > 1000:
        raise DataError("API limit: 1000")
    raw_types = value.get("types", [])
    if not isinstance(raw_types, list) or len(raw_types) > 1000:
        raise DataError("types must be an array")
    for source in raw_types:
        if not isinstance(source, dict):
            raise DataError("type must be an object")
        item = copy.deepcopy(source)
        _identity(item)
        if item["id"] in ids:
            raise DataError("duplicate data ID")
        ids.add(item["id"])
        item["label"] = _name(item, item["id"])
        item["description"] = _text(item.get("description", ""), "description", 1024)
        item["members"] = _normalize_variables(item.get("members", []))
        result["types"].append(item)
    custom = {item["id"] for item in result["types"]}
    for item in result["variables"] + result["constants"] + [member for typ in result["types"] for member in typ["members"]]:
        if item["type"] not in TYPES and item["type"] not in custom:
            raise DataError("unknown data type: " + item["type"])
        if item["type"] in TYPES:
            _initializer(item, "python", item in result["constants"])
        elif item.get('default') or item.get('value'):
            raise DataError('custom type initial value must be empty')
    graph = {item['id']: {member['type'] for member in item['members'] if member['type'] in custom} for item in result['types']}
    def visit_type(identity, active):
        if identity in active:
            raise DataError('recursive custom type initialization: ' + identity)
        for dependency in graph[identity]:
            visit_type(dependency, active | {identity})
    for identity in graph:
        visit_type(identity, set())
    return result


def scope_label(scope):
    return SCOPE_LABELS.get(scope, scope)


_PY_TYPES = {**TYPES, "string": "str", "str": "str", "integer": "int", "number": "float",
             "boolean": "bool", "object": "dict", "array": "list", "无返回值": "None", "空": "None", "void": "None",
             "指针": "Any", "uint8": "int", "int32": "int", "uint32": "int", "int64": "int", "uint64": "int",
             "float32": "float", "float64": "float", "bool32": "bool", "utf8": "str", "utf16": "str"}
_TS_TYPES = {"文本": "string", "字符串": "string", "str": "string", "string": "string",
             "整数": "number", "整数型": "number", "int": "number", "integer": "number",
             "小数": "number", "float": "number", "number": "number", "布尔": "boolean",
             "bool": "boolean", "boolean": "boolean", "对象": "Record<string, unknown>",
             "dict": "Record<string, unknown>", "object": "Record<string, unknown>",
             "数组": "unknown[]", "list": "unknown[]", "array": "unknown[]"}


def _py_type(value):
    return _PY_TYPES.get(value, value if re.fullmatch(r"[^\W\d]\w*(?:\.\w+)*", value or "") else "Any")


def _ts_type(value):
    return _TS_TYPES.get(value, _TS_TYPES.get(TYPES.get(value), value if re.fullmatch(r"[^\W\d]\w*", value or "") else "unknown"))


def reference_name(item):
    owner = item.get("owner", "")
    return f"{owner}.{item['id']}" if owner and item.get("scope") in {"window", "module"} else item["id"]


def _initializer(item, language, constant=False, custom_types=()):
    result = (item['type'] + '()' if language == 'python' else 'new ' + item['type'] + '()') if item.get('type') in custom_types else _literal(item.get("value" if constant else "default", ""), language, item.get("type"))
    if item.get("array"):
        for dimension in reversed(item["array"].split(",")):
            result = f"[{result} for _ in range({int(dimension)})]" if language == "python" else f"Array.from({{length:{int(dimension)}}}, () => {result})"
    return result


def _literal(value, language, declared_type=None):
    """Return a literal whose value agrees with the declaration type.

    Data-panel values are persisted as text, so inferring only from the text can
    turn a textual ``"1"`` into a number.  Known scalar/container types are
    parsed explicitly; an empty value gets that type's neutral default.
    """
    text = str(value).strip()
    type_name = TYPES.get(declared_type, declared_type)
    if type_name in {"str", "string"}:
        return repr(str(value)) if language == "python" else json.dumps(str(value), ensure_ascii=False)
    if type_name in {"bool", "boolean"}:
        lowered = text.lower()
        if not lowered:
            truth = False
        elif lowered in {"true", "1", "yes", "y", "是", "真"}:
            truth = True
        elif lowered in {"false", "0", "no", "n", "否", "假"}:
            truth = False
        else:
            raise DataError(f"invalid boolean value: {value}")
        return ("True" if truth else "False") if language == "python" else ("true" if truth else "false")
    if type_name in {"int", "integer"}:
        try:
            number = int(text or "0", 10)
        except ValueError as exc:
            raise DataError(f"invalid integer value: {value}") from exc
        bounds = {"字节型": (0, 255), "整数型": (-2**31, 2**31-1), "长整数型": (-2**63, 2**63-1)}
        if declared_type in bounds and not bounds[declared_type][0] <= number <= bounds[declared_type][1]:
            raise DataError("integer value out of declared range")
        return str(number)
    if type_name in {"float", "number"}:
        try:
            number = float(text or "0")
        except ValueError as exc:
            raise DataError(f"invalid number value: {value}") from exc
        if not math.isfinite(number):
            raise DataError(f"invalid number value: {value}")
        return repr(number)
    if type_name in {"dict", "object"} or type_name in {"list", "array"}:
        expected = dict if type_name in {"dict", "object"} else list
        try:
            parsed = json.loads(text) if text else expected()
        except json.JSONDecodeError as exc:
            raise DataError(f"invalid {type_name} value: {value}") from exc
        if not isinstance(parsed, expected):
            raise DataError(f"invalid {type_name} value: {value}")
        return repr(parsed) if language == "python" else json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    if type_name == "bytes":
        return repr(str(value).encode("utf-8")) if language == "python" else f"Buffer.from({json.dumps(str(value), ensure_ascii=False)}, 'utf8')"
    if language == "python":
        if text.lower() in {"true", "false", "none"}:
            return {"true": "True", "false": "False", "none": "None"}[text.lower()]
        try:
            float(text)
            return text
        except ValueError:
            return repr(str(value))
    if text.lower() in {"true", "false", "null"}:
        return text.lower()
    try:
        float(text)
        return text
    except ValueError:
        return json.dumps(str(value), ensure_ascii=False)


def generate_code(data: dict[str, Any], language: str) -> str:
    """Generate declarations and API wrappers for one supported language."""
    model = validate_data(data)
    custom_types = {item['id'] for item in model['types']}
    def initialize(item, language, constant=False):
        return _initializer(item, language, constant, custom_types)
    if language not in {"python", "javascript", "typescript"}:
        raise DataError("unsupported generation language")
    lines = []
    scoped = [item for item in model["variables"] + model["constants"] if item.get("owner") and item["scope"] != "global"]
    constants = [item for item in model["constants"] if item not in scoped]
    variables = [item for item in model["variables"] if item not in scoped]
    if language == "python":
        lines += ["# Generated by PCIDE program data", "from typing import Any", "from pcide.runtime_api import dll", ""]
        for typ in model["types"]:
            lines += [f"class {typ['id']}:", "    def __init__(self):"]
            lines += [f"        self.{member['id']}: {_py_type(member['type'])} = {initialize(member, language)}" for member in typ["members"]] or ["        pass"]
            lines.append("")
        for item in constants:
            lines.append(f"{item['id']} = {initialize(item, language, True)}  # {item['label']}")
        for item in variables:
            lines.append(f"{item['id']}: {_py_type(item['type'])} = {initialize(item, language)}  # {scope_label(item['scope'])}: {item['label']}")
        for api in model["apis"]:
            params = ", ".join(f"{p['id']}: {_py_type(p['type'])}" for p in api["parameters"])
            handle_name = "_dll_" + api["id"]
            arguments = ", ".join(p["id"] for p in api["parameters"])
            lines += ["", f"{handle_name} = None", f"def {api['id']}({params}) -> {_py_type(api['return_type'])}:",
                      f"    {api['label'] + ' (' + api['calling_convention'] + ')'!r}",
                      f"    global {handle_name}",
                      f"    if {handle_name} is None:",
                      f"        {handle_name} = dll.load({api['library']!r}, {api['calling_convention']!r})",
                      f"    return dll.call({handle_name}, {api['entry']!r}, [{arguments}], {api['return_type']!r}, argument_types={[p['type'] for p in api['parameters']]!r})"]
    elif language == "javascript":
        lines += ["// Generated by PCIDE program data", ""]
        for typ in model["types"]:
            lines += [f"class {typ['id']} {{", "  constructor() {"]
            lines += [f"    this.{member['id']} = {initialize(member, language)};" for member in typ["members"]]
            lines += ["  }", "}"]
        lines.extend(f"const {i['id']} = {initialize(i, language, True)}; // {i['label']}" for i in constants)
        lines.extend(f"let {i['id']} = {initialize(i, language)}; // {scope_label(i['scope'])}: {i['label']}" for i in variables)
        for api in model["apis"]:
            params = ", ".join(p["id"] for p in api["parameters"])
            lines += ["", f"// {api['label']}", f"function {api['id']}({params}) {{", "  throw new Error('DLL ABI 仅支持 Python/中文源码独立宿主；Node DLL 尚未开放');", "}"]
    else:
        lines += ["// Generated by PCIDE program data", ""]
        for typ in model["types"]:
            lines += [f"class {typ['id']} {{"]
            lines += [f"  {member['id']}: {_ts_type(member['type'])} = {initialize(member, language)};" for member in typ["members"]]
            lines += ["}"]
        lines.extend(f"const {i['id']}: {_ts_type(i['type'])} = {initialize(i, language, True)}; // {i['label']}" for i in constants)
        lines.extend(f"let {i['id']}: {_ts_type(i['type'])} = {initialize(i, language)}; // {scope_label(i['scope'])}: {i['label']}" for i in variables)
        for api in model["apis"]:
            params = ", ".join(f"{p['id']}: {_ts_type(p['type'])}" for p in api["parameters"])
            lines += ["", f"// {api['label']}", f"function {api['id']}({params}): {_ts_type(api['return_type'])} {{", "  throw new Error('DLL ABI 仅支持 Python/中文源码独立宿主；Node DLL 尚未开放');", "}"]
    groups = {}
    for item in scoped:
        if not item["owner"].isidentifier():
            raise DataError("owner must be a code identifier")
        groups.setdefault((item["scope"], item["owner"]), []).append(item)
    for (scope, owner), members in groups.items():
        if scope == 'local':
            prefix = '# ' if language == 'python' else '// '
            lines += ['', prefix + '局部声明由 IDE 注入子程序 ' + owner]
            lines += [prefix + item['id'] + ' = ' + initialize(item, language, item in model['constants']) for item in members]
            continue
        if language == "python":
            lines += ["", f"class {owner}:" if scope != "local" else f"def {owner}():"]
            for item in members:
                lines.append(f"    {item['id']} = {initialize(item, language, item in model['constants'])}")
        else:
            lines += ["", f"const {owner} = {{" if scope != "local" else f"function {owner}() {{"]
            for item in members:
                expression = initialize(item, language, item in model["constants"])
                lines.append(f"  {item['id']}: {expression}," if scope != "local" else f"  let {item['id']} = {expression};")
            lines.append("};" if scope != "local" else "}")
    return "\n".join(lines).rstrip() + "\n"
