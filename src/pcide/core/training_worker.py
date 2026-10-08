from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    import torch
    torch.set_num_threads(4)
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    disabled = ("sync", "wandb", "clearml", "comet", "mlflow", "neptune", "raytune", "tensorboard")
    SETTINGS.update({key: False for key in disabled if key in SETTINGS})
    model_path = Path(config["model"])
    if not model_path.is_file():
        raise ValueError("explicit model file is required")
    model = YOLO(str(model_path))
    if config["operation"] == "train":
        results = model.train(data=config["dataset"], epochs=int(config["epochs"]), imgsz=64, batch=2,
                              device="cpu", workers=0, project=config["output"], name="run",
                              exist_ok=True, plots=False, amp=False, cache=False, pretrained=False,
                              mosaic=0, close_mosaic=0, optimizer="SGD")
        weights = Path(config["output"]) / "run" / "weights" / "best.pt"
        if weights.is_file():
            target = Path(config["models"]) / (Path(config["output"]).name + ".pt")
            shutil.copy2(weights, target)
        print(json.dumps({"ok": True, "operation": "train", "output": config["output"]}))
    elif config["operation"] == "export":
        export_model = Path(config["output"]) / model_path.name
        shutil.copy2(model_path, export_model)
        model = YOLO(str(export_model))
        result = model.export(format="onnx", imgsz=640, simplify=False, opset=12)
        shutil.copy2(result, Path(config["models"]) / Path(result).name)
        print(json.dumps({"ok": True, "operation": "export", "file": str(result)}))
    else:
        raise ValueError("unsupported training operation")


if __name__ == "__main__":
    main()
