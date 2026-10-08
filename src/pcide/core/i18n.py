"""Chinese display labels to stable internal IDs and back."""
from __future__ import annotations

import re

_SAFE = re.compile(r"[^A-Za-z0-9_]")


def make_id(label: str, prefix="item", used=()):
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label is required")
    stem = _SAFE.sub("_", label.strip()).strip("_") or prefix
    if stem[0].isdigit():
        stem = f"{prefix}_{stem}"
    stem = stem[:60]
    occupied = set(used)
    candidate = stem
    index = 2
    while candidate in occupied:
        candidate = f"{stem}_{index}"
        index += 1
    return candidate


class IdentifierMap:
    def __init__(self, items=()):
        self._label_to_id = {}
        self._id_to_label = {}
        for item in items:
            self.add(item["id"], item.get("label", item["id"]))

    def add(self, internal_id: str, label: str):
        if not isinstance(internal_id, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", internal_id):
            raise ValueError("invalid internal ID")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("invalid display label")
        if internal_id in self._id_to_label and self._id_to_label[internal_id] != label:
            raise ValueError("duplicate internal ID")
        if label in self._label_to_id and self._label_to_id[label] != internal_id:
            raise ValueError("duplicate display label")
        self._id_to_label[internal_id] = label
        self._label_to_id[label] = internal_id

    def to_id(self, value: str) -> str:
        return self._label_to_id.get(value, value)

    def to_label(self, value: str) -> str:
        return self._id_to_label.get(value, value)

    def as_dict(self):
        return {key: self._id_to_label[key] for key in sorted(self._id_to_label)}


EVENT_LABELS = {"click": "点击", "double_click": "双击", "change": "变更", "load": "加载",
                "mouse_down": "按下鼠标", "key_down": "按下按键"}
EVENT_IDS = {label: key for key, label in EVENT_LABELS.items()}


def to_event_id(value: str) -> str:
    return EVENT_IDS.get(value, value)


def to_event_label(value: str) -> str:
    return EVENT_LABELS.get(value, value)


event_to_id = to_event_id
event_to_label = to_event_label
