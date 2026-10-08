"""Explicit Windows automation operations; no background monitoring."""
from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from ctypes import wintypes

MAX_WINDOWS = 4096
MAX_TEXT = 32768


def _user32():
    if os.name != "nt":
        raise RuntimeError("Win32 automation requires Windows")
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.IsWindow.argtypes = [wintypes.HWND]
    api.IsWindow.restype = wintypes.BOOL
    api.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.IsWindowVisible.argtypes = [wintypes.HWND]
    return api


def describe_window(handle):
    api = _user32()
    if type(handle) is not int or not api.IsWindow(handle):
        raise ValueError("invalid window handle")
    title = ctypes.create_unicode_buffer(min(MAX_TEXT, api.GetWindowTextLengthW(handle) + 1))
    api.GetWindowTextW(handle, title, len(title))
    rect, pid = wintypes.RECT(), wintypes.DWORD()
    if not api.GetWindowRect(handle, ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    return {"handle": handle, "title": title.value, "pid": pid.value,
            "visible": bool(api.IsWindowVisible(handle)), "rect": [rect.left, rect.top, rect.right, rect.bottom]}


def list_windows(title=None):
    api = _user32()
    result, errors = [], []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle, _):
        try:
            item = describe_window(int(handle))
            if title is None or title in item["title"]:
                result.append(item)
            return len(result) < MAX_WINDOWS
        except Exception as exc:
            errors.append(exc)
            return False
    callback = callback_type(visit)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    api.EnumWindows(callback, 0)
    if errors:
        raise errors[0]
    return result


def screenshot(path, handle=None):
    from pathlib import Path
    from PIL import ImageGrab
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rect = describe_window(handle)["rect"] if handle is not None else None
    with ImageGrab.grab(bbox=tuple(rect) if rect else None, all_screens=True) as image:
        image.save(target)
        size = list(image.size)
    return {"kind": "screenshot", "file": str(target.resolve()), "size": size, "simulated": False}


@contextmanager
def com_object(progid):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    instance = None
    try:
        instance = win32com.client.Dispatch(progid)
        yield instance
    finally:
        if instance is not None:
            instance._oleobj_ = None
        instance = None
        pythoncom.CoUninitialize()


def uia_root():
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    automation = element = None
    try:
        from .paths import Paths
        generated = Paths().cache / "comtypes"
        generated.mkdir(parents=True, exist_ok=True)
        comtypes.client.gen_dir = str(generated)
        interfaces = comtypes.client.GetModule("UIAutomationCore.dll")
        automation = comtypes.client.CreateObject(interfaces.CUIAutomation, interface=interfaces.IUIAutomation)
        element = automation.GetRootElement()
        bounds = element.CurrentBoundingRectangle
        return {"name": element.CurrentName, "class": element.CurrentClassName,
                "rect": [bounds.left, bounds.top, bounds.right, bounds.bottom]}
    finally:
        element = automation = None
        comtypes.CoUninitialize()


def list_serial_ports():
    from serial.tools.list_ports import comports
    return [{"device": p.device, "description": p.description, "hwid": p.hwid} for p in comports()]


@contextmanager
def serial_port(port, baudrate=9600, timeout=1.0):
    import serial
    if timeout is None or timeout <= 0:
        raise ValueError("serial operations require a positive timeout")
    connection = serial.serial_for_url(port, baudrate=baudrate, timeout=timeout, write_timeout=timeout)
    try:
        yield connection
    finally:
        connection.close()


def list_hid_devices():
    import hid
    return hid.enumerate()


@contextmanager
def hid_device(path, timeout_ms=1000):
    import hid
    if not isinstance(path, bytes) or timeout_ms <= 0:
        raise ValueError("HID device path/timeout invalid")
    device = hid.device()
    try:
        device.open_path(path)
        yield HidConnection(device, timeout_ms)
    finally:
        device.close()


class HidConnection:
    def __init__(self, device, timeout_ms):
        self.device, self.timeout_ms = device, timeout_ms

    def read(self, size, timeout_ms=None):
        timeout = self.timeout_ms if timeout_ms is None else timeout_ms
        if type(size) is not int or not 1 <= size <= 65536 or timeout <= 0:
            raise ValueError("HID read size/timeout invalid")
        return self.device.read(size, timeout)

    def write(self, data):
        if not 1 <= len(data) <= 65536:
            raise ValueError("HID report size invalid")
        return self.device.write(data)
