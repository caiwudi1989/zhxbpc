"""DLL client. Customer native code is loaded only by PluginSession children."""
from __future__ import annotations

import atexit
import re
import threading
import uuid
from pathlib import Path

from .plugins import PluginManifest, PluginSession

ABI_TYPES = {"空": "void", "无返回值": "void", "整数": "int32", "整数型": "int32",
             "字节型": "uint8", "长整数型": "int64", "数值": "float64", "数值型": "float64",
             "小数型": "float32", "双精度小数型": "float64", "逻辑": "bool32", "逻辑型": "bool32",
             "逻辑型(布尔型)": "bool32", "文本": "utf8", "文本型": "utf8"}
SCALARS = {"int32", "uint8", "int64", "uint32", "uint64", "float32", "float64", "bool32"}


def validate_signature(function, argument_types, return_type):
    if not isinstance(function, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_@$?]{0,127}", function):
        raise ValueError("DLL 导出名称非法")
    if not isinstance(argument_types, (list, tuple)) or len(argument_types) > 32:
        raise ValueError("DLL 必须明确声明 0 到 32 个参数类型")
    args = [ABI_TYPES.get(value, value) for value in argument_types]
    result = ABI_TYPES.get(return_type, return_type)
    if any(value not in SCALARS | {"utf8", "utf16"} for value in args):
        raise ValueError("不支持的 DLL 参数 ABI；裸指针、结构体和输出参数尚未开放")
    if result not in SCALARS | {"void"}:
        raise ValueError("DLL 返回值只开放明确宽度的标量；文本/裸指针返回尚未开放")
    return args, result


class DllProxy:
    def __init__(self):
        self._handles = {}
        self._lock = threading.RLock()

    @staticmethod
    def _safe_path(value):
        if not isinstance(value, str):
            raise ValueError("DLL 路径必须是文本")
        raw = value.replace("\\", "/")
        target = Path(raw)
        if not raw or len(raw) > 260 or target.is_absolute() or ".." in target.parts or ":" in raw or "\x00" in raw or target.suffix.lower() != ".dll":
            raise ValueError("DLL 路径必须是项目内相对 .dll 文件")
        root = Path.cwd().resolve()
        path = root / target
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent.is_relative_to(root)):
            raise ValueError("DLL 路径不能包含符号链接")
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("DLL 文件不存在或越界")
        return path

    def load(self, path, calling_convention="cdecl", timeout=5):
        if calling_convention not in {"cdecl", "stdcall", "winapi"}:
            raise ValueError("DLL 只支持 cdecl/stdcall/winapi")
        target = self._safe_path(path)
        with self._lock:
            if len(self._handles) >= 4:
                raise ValueError("DLL 子进程数量超过 4")
            token = uuid.uuid4().hex
            manifest = PluginManifest("dll." + token, target.name, "1.0.0", "native", target.name,
                                      ["dll.call"], ["native.dll"], abi="dll-v1")
            session = PluginSession(manifest, target.parent, self._timeout(timeout))
            self._handles[token] = (session, calling_convention)
            return token

    @staticmethod
    def _timeout(value):
        if type(value) not in {int, float} or not 0.05 <= value <= 60:
            raise ValueError("DLL 超时必须在 0.05 到 60 秒")
        return float(value)

    def call(self, handle, function, args=(), return_type="整数型", *, argument_types=None, timeout=5):
        types, result = validate_signature(function, [] if argument_types is None and not args else argument_types, return_type)
        if not isinstance(args, (list, tuple)) or len(args) != len(types):
            raise ValueError("DLL 实参与声明数量不符")
        with self._lock:
            if handle not in self._handles:
                raise ValueError("DLL 句柄已失效")
            session, convention = self._handles[handle]
        reply = session.request("call", self._timeout(timeout), capability="dll.call",
                                params={"function": function, "args": list(args), "argument_types": types,
                                        "return_type": result, "calling_convention": convention})
        return reply["result"]

    def unload(self, handle):
        with self._lock:
            item = self._handles.pop(handle, None)
        if item:
            item[0].close(graceful=False)  # Also cancels an active call.
        return item is not None

    def close(self):
        for handle in list(self._handles):
            self.unload(handle)


dll = DllProxy()
atexit.register(dll.close)
