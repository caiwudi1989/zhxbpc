from .core.runtime_api import db, game, network, ocr_mock, screenshot_mock, yolo_mock, ui

from .core.automation import (com_object, describe_window, hid_device, list_hid_devices,
                             list_serial_ports, list_windows, screenshot, serial_port, uia_root)

__all__ = ["ocr_mock", "screenshot_mock", "yolo_mock", "ui", "db", "network", "game", "com_object", "describe_window",
           "hid_device", "list_hid_devices", "list_serial_ports", "list_windows", "screenshot", "serial_port", "uia_root", "ocr", "yolo"]


def ocr(image):
    from .core.vision import VisionWorkbench
    from pathlib import Path
    return VisionWorkbench(Path.cwd()).ocr(image, simulated=False)


def yolo(image, model):
    from .core.vision import VisionWorkbench
    from pathlib import Path
    return VisionWorkbench(Path.cwd()).yolo(image, model=model)
