from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .paths import atomic_write_json


class TrainingTask(QObject):
    message = Signal(str)
    finished = Signal(int)

    def __init__(self, paths, vision, parent=None):
        super().__init__(parent)
        self.paths, self.vision = paths, vision
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(lambda _: self.message.emit(self.process.errorString()))
        self.process.started.connect(self._started)
        self.job = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.stop)

    @property
    def active(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    def start(self, operation, model, epochs=1, timeout=3600):
        if self.active:
            raise RuntimeError("training/export task is already active")
        if operation not in {"train", "export"} or type(epochs) is not int or not 1 <= epochs <= 10000 or not 0 < timeout <= 86400:
            raise ValueError("invalid training/export settings")
        python = self.paths.runtime / "training" / "Scripts" / "python.exe"
        if not python.is_file():
            self.message.emit("训练环境缺失: tools/provision_training.py")
            return
        session = uuid.uuid4().hex
        folder = self.vision.logs / session
        folder.mkdir(parents=True, exist_ok=True)
        config = folder / "request.json"
        atomic_write_json(config, {"operation": operation, "model": str(model), "epochs": epochs,
                                  "dataset": str(self.vision.dataset / "data.yaml"), "output": str(folder),
                                  "models": str(self.vision.models)})
        from PySide6.QtCore import QProcessEnvironment
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
            "YOLO_CONFIG_DIR": str(self.paths.cache / "ultralytics"), "MPLCONFIGDIR": str(self.paths.cache / "matplotlib"),
            "HF_HOME": str(self.paths.cache / "huggingface"), "YOLO_AUTOINSTALL": "false"}.items():
            environment.insert(key, value)
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(folder))
        worker = Path(__file__).with_name("training_worker.py")
        if not worker.is_file():
            worker = worker.with_suffix(".pyc")
        if not worker.is_file():
            raise RuntimeError("training worker is not packaged")
        self.process.start(str(python), ["-B", str(worker), str(config)])
        self.timer.start(int(timeout * 1000))
        self.message.emit("训练/导出任务已启动")

    def _started(self):
        from .processes import ProcessJob
        try:
            self.job = ProcessJob(self.process, pid=self.process.processId())
        except OSError as exc:
            self.message.emit(str(exc))
            self.stop()

    def _read(self):
        self.message.emit(bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")[-16000:])

    def _finished(self, code, status):
        self.timer.stop()
        if self.job:
            self.job.close()
            self.job = None
        self.message.emit(f"训练/导出退出 {code}")
        self.finished.emit(code)

    def stop(self):
        self.timer.stop()
        if self.active:
            if self.job:
                self.job.close()
            else:
                self.process.kill()
            self.process.waitForFinished(3000)
