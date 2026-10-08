"""AI Runtime provider contracts for ONNX/OpenCV/OCR and future backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

class AiRuntimeError(RuntimeError):
    pass

@dataclass(frozen=True)
class ModelSpec:
    id: str
    path: str
    task: str = "classification"
    device: str = "CPU"
    labels: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

class InferenceProvider(Protocol):
    def load(self, model: ModelSpec) -> None: ...
    def infer(self, input_data: Any) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...

def validate_model(model: ModelSpec, root: str | Path) -> ModelSpec:
    path = (Path(root).resolve() / model.path).resolve()
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file() or path.is_symlink():
        raise AiRuntimeError("模型必须是项目内的普通文件")
    if model.device.upper() not in {"CPU", "CUDA", "GPU"}:
        raise AiRuntimeError("不支持的推理设备")
    if model.task not in {"classification", "detection", "ocr", "segmentation", "embedding"}:
        raise AiRuntimeError("不支持的模型任务")
    return model

class RuntimeSession:
    def __init__(self, provider: InferenceProvider, model: ModelSpec, root: str | Path):
        self.provider, self.model = provider, validate_model(model, root)
        self.loaded = False

    def start(self) -> None:
        self.provider.load(self.model); self.loaded = True

    def infer(self, input_data: Any) -> list[dict[str, Any]]:
        if not self.loaded: raise AiRuntimeError("模型尚未加载")
        output = self.provider.infer(input_data)
        if not isinstance(output, list) or len(output) > 10000:
            raise AiRuntimeError("推理结果必须是有界列表")
        return output

    def close(self) -> None:
        self.provider.close(); self.loaded = False

class VisionProvider:
    """Adapter over the existing isolated vision workbench."""
    def __init__(self, workbench: Any):
        self.workbench = workbench
        self.model: ModelSpec | None = None
    def load(self, model: ModelSpec) -> None:
        self.model = model
    def infer(self, input_data: Any) -> list[dict[str, Any]]:
        if self.model is None:
            raise AiRuntimeError("模型尚未加载")
        if self.model.task == "ocr":
            result = self.workbench.ocr(input_data, simulated=False)
        elif self.model.task == "detection":
            result = self.workbench.yolo(input_data, model=self.model.path)
        else:
            raise AiRuntimeError("当前 VisionProvider 只支持 OCR 和 detection")
        return result.get("items", result.get("detections", []))
    def close(self) -> None:
        self.model = None
