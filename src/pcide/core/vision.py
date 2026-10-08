from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .label_io import ensure_dataset_dirs, list_images, read_boxes, write_boxes, label_path_for
from .paths import Paths, atomic_write_json, read_json, sha256_file
from .runtime_api import ocr_mock, yolo_mock


class VisionWorkbench:
    def __init__(self, project_root, paths=None):
        self.paths = (paths or Paths()).ensure()
        self.project_root = Path(project_root).resolve()
        self.project_id = hashlib.sha256(str(self.project_root).encode()).hexdigest()[:16]
        self.dataset = self.project_root / "vision" / "dataset"
        self.annotations = self.dataset / "labels"
        self.models = self.paths.runtime / "models" / self.project_id
        self.logs = self.paths.cache / "training" / self.project_id
        ensure_dataset_dirs(self.dataset)
        self.models.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)

    def ocr(self, image, text="OK", simulated=True):
        if simulated:
            return ocr_mock(image, text)
        from rapidocr_onnxruntime import RapidOCR
        import cv2
        import numpy as np
        frame = cv2.imdecode(np.fromfile(str(image), dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("image could not be decoded")
        engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
        result, timings = engine(frame)
        return {"kind": "ocr", "backend": "rapidocr.onnxruntime", "simulated": False,
                "items": [{"text": item[1], "confidence": float(item[2]), "box": item[0]} for item in result or []],
                "timings": timings}

    def yolo(self, image, label="object", model=None):
        if model is None:
            return yolo_mock(image, label)
        import cv2
        import numpy as np
        # Unicode image paths require decoding bytes instead of imread on Windows.
        frame = cv2.imdecode(np.fromfile(str(image), dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("image could not be decoded")
        network = cv2.dnn.readNetFromONNX(np.fromfile(str(model), dtype=np.uint8))
        blob = cv2.dnn.blobFromImage(frame, 1 / 255, (640, 640), swapRB=True, crop=False)
        network.setInput(blob)
        result = network.forward()
        prediction = np.squeeze(result)
        if prediction.ndim != 2:
            raise ValueError(f"unsupported YOLO output: {result.shape}")
        # Ultralytics detect export is (1, 4 + classes, anchors).
        if prediction.shape[0] < prediction.shape[1]:
            prediction = prediction.T
        if prediction.shape[1] < 5:
            raise ValueError("YOLO model needs coordinates and class scores")
        boxes, scores, classes = [], [], []
        height, width = frame.shape[:2]
        for row in prediction:
            class_id = int(np.argmax(row[4:]))
            confidence = float(row[4 + class_id])
            if confidence < .25:
                continue
            cx, cy, bw, bh = row[:4]
            boxes.append([int((cx-bw/2)*width/640), int((cy-bh/2)*height/640),
                          int(bw*width/640), int(bh*height/640)])
            scores.append(confidence)
            classes.append(class_id)
        selected = cv2.dnn.NMSBoxes(boxes, scores, .25, .45)
        detections = [{"class_id": classes[int(index)], "confidence": scores[int(index)], "box": boxes[int(index)]}
                      for index in np.asarray(selected).reshape(-1)]
        return {"backend": "opencv.dnn", "shape": list(result.shape), "detections": detections,
                "simulated": False}

    def add_annotation(self, image_name, labels):
        target = label_path_for(image_name, self.dataset)
        write_boxes(target, labels)
        return target

    def import_model(self, path):
        source = Path(path)
        if source.suffix.lower() not in {".pt", ".onnx"} or not source.is_file():
            raise ValueError("model must be .pt or .onnx")
        target = self.models / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        atomic_write_json(target.with_suffix(target.suffix + ".json"),
                          {"file": target.name, "sha256": sha256_file(target), "format": target.suffix})
        return target

    def model_manifest(self):
        return {"models": [p.name for p in self.models.iterdir() if p.suffix in {".pt", ".onnx"}],
                "annotations": len(list(self.annotations.glob("*.txt"))),
                "dataset_images": len(list_images(self.dataset)),
                "training_logs": [str(p) for p in self.logs.glob("*/results.csv")]}
