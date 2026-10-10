"""Explicit scalar DLL ABI, imported exclusively inside plugin_host."""
from __future__ import annotations

import ctypes
import math
import os
import struct
import sys

from .dll import validate_signature


class DllLibrary:
    def __init__(self, entry):
        if os.name != "nt" or not getattr(sys, "_pcide_plugin_host", False):
            raise RuntimeError("DLL 需要独立 Windows 插件宿主")
        with entry.open("rb") as source:
            header = source.read(4096)
        if len(header) < 64 or header[:2] != b"MZ":
            raise ValueError("DLL 不是 Windows PE")
        offset = struct.unpack_from("<I", header, 0x3c)[0]
        if offset + 6 > len(header) or header[offset:offset+4] != b"PE\0\0":
            raise ValueError("DLL PE 头无效")
        machine = struct.unpack_from("<H", header, offset + 4)[0]
        if machine != (0x8664 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x14c):
            raise ValueError("DLL 位数与宿主不匹配")
        self.entry = entry
        self.search = os.add_dll_directory(str(entry.parent))
        self.libraries = {}

    def invoke(self, request):
        raw = request.get("params", {})
        args, result = validate_signature(raw.get("function"), raw.get("argument_types"), raw.get("return_type"))
        values = raw.get("args")
        convention = raw.get("calling_convention")
        if convention not in {"cdecl", "stdcall", "winapi"} or not isinstance(values, list) or len(values) != len(args):
            raise ValueError("DLL 调用合同无效")
        ctypes_map = {"int32": ctypes.c_int32, "uint8": ctypes.c_uint8, "int64": ctypes.c_int64,
                      "uint32": ctypes.c_uint32, "uint64": ctypes.c_uint64, "float32": ctypes.c_float,
                      "float64": ctypes.c_double, "bool32": ctypes.c_int32,
                      "utf8": ctypes.c_char_p, "utf16": ctypes.c_wchar_p, "void": None}
        converted = []
        for kind, value in zip(args, values):
            if kind in {"utf8", "utf16"}:
                if not isinstance(value, str) or "\0" in value or len(value.encode("utf-8")) > 16384:
                    raise ValueError("DLL 文本参数必须无 NUL 且不超过 16KB")
                converted.append(value.encode("utf-8") if kind == "utf8" else value)
            elif kind == "bool32":
                if type(value) is not bool:
                    raise ValueError("DLL 逻辑参数必须是布尔值")
                converted.append(int(value))
            elif kind.startswith("float"):
                if type(value) not in {int, float} or not math.isfinite(value):
                    raise ValueError("DLL 浮点参数必须有限")
                converted.append(value)
            else:
                bits = int(kind.removeprefix("uint").removeprefix("int"))
                minimum, maximum = (0, 2**bits-1) if kind.startswith("uint") else (-2**(bits-1), 2**(bits-1)-1)
                if type(value) is not int or not minimum <= value <= maximum:
                    raise ValueError("DLL 整数参数溢出或类型错误")
                converted.append(value)
        if convention not in self.libraries:
            loader = ctypes.CDLL if convention == "cdecl" else ctypes.WinDLL
            self.libraries[convention] = loader(str(self.entry), winmode=0x1100)
        function = getattr(self.libraries[convention], raw["function"])
        function.argtypes = [ctypes_map[kind] for kind in args]
        function.restype = ctypes_map[result]
        value = function(*converted)
        if result == "bool32":
            return bool(value)
        if result.startswith("float") and not math.isfinite(value):
            raise ValueError("DLL 返回了非有限数值")
        return value

    def close(self):
        self.search.close()
