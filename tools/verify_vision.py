from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.vision import VisionWorkbench
from pcide.core.label_io import write_boxes


def main():
    paths = Paths(root).ensure()
    folder = paths.cache / "vision-verification"
    folder.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont
    image_path = folder / "ocr.png"
    with Image.new("RGB", (640, 130), "white") as image:
        ImageDraw.Draw(image).text((25, 25), "PCIDE 2026 TEST", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 44))
        image.save(image_path)
    vision = VisionWorkbench(folder / "project", paths)
    ocr = vision.ocr(image_path, simulated=False)
    if not any("2026" in item["text"] for item in ocr["items"]):
        raise RuntimeError(f"OCR did not recognize test text: {ocr}")
    for index in range(6):
        with Image.new("RGB", (64, 64), "white") as image:
            ImageDraw.Draw(image).rectangle((20, 20, 44, 44), fill=(index*30, 40, 80))
            image.save(vision.dataset / "images" / f"sample{index}.png")
        write_boxes(vision.dataset / "labels" / f"sample{index}.txt", [{"class_id": 0, "cx": .5, "cy": .5, "w": .375, "h": .375}])
    import yaml
    for split, indices in (("train", range(4)), ("val", range(4,6))):
        (vision.dataset / f"{split}.txt").write_text("".join(f"./images/sample{i}.png\n" for i in indices), encoding="utf-8")
    (vision.dataset / "data.yaml").write_text(yaml.safe_dump({"path": vision.dataset.as_posix(), "train": "train.txt", "val": "val.txt", "names": ["square"]}), encoding="utf-8")
    python = paths.runtime / "training/Scripts/python.exe"
    model_path = folder / "tiny.pt"
    env = os.environ.copy()
    for directory in (paths.cache / "ultralytics", paths.cache / "matplotlib"):
        directory.mkdir(parents=True, exist_ok=True)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", YOLO_CONFIG_DIR=str(paths.cache / "ultralytics"),
               MPLCONFIGDIR=str(paths.cache / "matplotlib"), YOLO_AUTOINSTALL="false")
    code = "from ultralytics import YOLO; import sys; YOLO('yolov8n.yaml').save(sys.argv[1])"
    subprocess.run([str(python), "-B", "-c", code, str(model_path)], env=env, check=True, timeout=60, cwd=folder)
    request = folder / "train-request.json"
    atomic_write_json(request, {"operation": "train", "model": str(model_path), "dataset": str(vision.dataset / "data.yaml"),
                               "epochs": 1, "output": str(folder / "training"), "models": str(vision.models)})
    worker = paths.src / "pcide/core/training_worker.py"
    with (folder / "train.log").open("w", encoding="utf-8") as log:
        subprocess.run([str(python), "-B", str(worker), str(request)], env=env, check=True, timeout=180, cwd=folder, stdout=log, stderr=subprocess.STDOUT)
    models = list(vision.models.glob("*.pt"))
    if not models:
        raise RuntimeError("training did not produce weights")
    export_request = folder / "export-request.json"
    (folder / "export").mkdir(exist_ok=True)
    atomic_write_json(export_request, {"operation": "export", "model": str(models[0]), "output": str(folder / "export"), "models": str(vision.models)})
    with (folder / "export.log").open("w", encoding="utf-8") as log:
        subprocess.run([str(python), "-B", str(worker), str(export_request)], env=env, check=True, timeout=120, cwd=folder, stdout=log, stderr=subprocess.STDOUT)
    onnx = next(vision.models.glob("*.onnx"))
    inference = vision.yolo(image_path, model=onnx)
    report = {"ocr": ocr, "train_weights": str(models[0]), "onnx": str(onnx), "inference": inference,
              "boundary": "CPU synthetic dataset: validates execution/export, not recognition accuracy"}
    atomic_write_json(paths.logs / "vision-verification.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
