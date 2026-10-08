"""Adapted from the reviewed generic legacy yolo_tool/label_io.py contract."""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import yaml

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def ensure_dataset_dirs(dataset_dir):
    root = Path(dataset_dir)
    images, labels = root / "images", root / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    return images, labels


def list_images(dataset_dir):
    directory = Path(dataset_dir) / "images"
    return sorted((p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES), key=lambda p: p.name.lower()) if directory.exists() else []


def label_path_for(image_path, dataset_dir):
    stem = Path(image_path).stem
    if stem in {"", ".", ".."}:
        raise ValueError("image name required")
    return Path(dataset_dir) / "labels" / f"{stem}.txt"


def read_boxes(label_file):
    path = Path(label_file)
    if not path.exists():
        return []
    boxes = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"invalid YOLO label line {number}")
        box = dict(zip(("class_id", "cx", "cy", "w", "h"), (int(parts[0]), *map(float, parts[1:]))))
        validate_box(box)
        boxes.append(box)
    return boxes


def validate_box(box):
    if type(box.get("class_id")) is not int or box["class_id"] < 0:
        raise ValueError("class_id must be a nonnegative integer")
    for key in ("cx", "cy", "w", "h"):
        value = box.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("YOLO coordinates must be finite normalized values")
    if box["w"] <= 0 or box["h"] <= 0:
        raise ValueError("YOLO box must have positive size")


def write_boxes(label_file, boxes):
    for box in boxes:
        validate_box(box)
    target = Path(label_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(f"{b['class_id']} {b['cx']:.6f} {b['cy']:.6f} {b['w']:.6f} {b['h']:.6f}\n" for b in boxes)
    target.write_text(text, encoding="utf-8")
    return True


def read_class_names(dataset_dir):
    path = Path(dataset_dir) / "data.yaml"
    if not path.exists():
        return ["object"]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dataset YAML must be an object")
    names = data.get("names", ["object"])
    if isinstance(names, dict):
        if set(names) != set(range(len(names))):
            raise ValueError("class IDs must be contiguous integers")
        names = [names[index] for index in range(len(names))]
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("class names must be nonempty text")
    return names


def write_data_yaml(dataset_dir, names=None):
    root = Path(dataset_dir).resolve()
    ensure_dataset_dirs(root)
    target = root / "data.yaml"
    target.write_text(yaml.safe_dump({"path": root.as_posix(), "train": "images", "val": "images",
                                    "names": names or ["object"]}, allow_unicode=True), encoding="utf-8")
    return target


def copy_images_into_dataset(dataset_dir, source_files):
    images, labels = ensure_dataset_dirs(dataset_dir)
    copied = 0
    candidates = []
    stems = {p.stem.casefold(): p.name.casefold() for p in list_images(dataset_dir)}
    for source in source_files:
        source = Path(source)
        if not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"not an image: {source}")
        target = images / source.name
        if target.exists() and source.resolve() != target.resolve():
            raise ValueError(f"duplicate dataset image: {target.name}")
        if not target.exists():
            key = source.stem.casefold()
            if key in stems and stems[key] != source.name.casefold():
                raise ValueError(f"images share one label name: {source.stem}")
            stems[key] = source.name.casefold()
        candidates.append((source, target))
    for source, target in candidates:
        if not target.exists():
            shutil.copy2(source, target)
            copied += 1
        label = labels / (source.stem + ".txt")
        if not label.exists():
            label.write_text("", encoding="utf-8")
    write_data_yaml(dataset_dir, read_class_names(dataset_dir))
    return copied
