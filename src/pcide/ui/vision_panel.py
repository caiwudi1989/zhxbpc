from __future__ import annotations

import json

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QPlainTextEdit, QSplitter, QSpinBox, QVBoxLayout, QWidget)

from pcide.core.label_io import copy_images_into_dataset, list_images, read_boxes, label_path_for
from pcide.core.vision import VisionWorkbench


class Annotator(QGraphicsView):
    box_added = Signal(dict)

    def __init__(self):
        super().__init__()
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.origin = None
        self.rect_item = None
        self.image_size = None

    def load_image(self, path, boxes):
        self.origin = None
        self.rect_item = None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("cannot decode dataset image")
        self.canvas.clear()
        self.canvas.addPixmap(pixmap)
        self.canvas.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.image_size = (pixmap.width(), pixmap.height())
        for box in boxes:
            w, h = self.image_size
            self.canvas.addRect((box["cx"] - box["w"] / 2) * w, (box["cy"] - box["h"] / 2) * h,
                                box["w"] * w, box["h"] * h, QColor("#e44a3f"))
        self.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event):
        if self.image_size and event.button() == Qt.MouseButton.LeftButton:
            self.origin = self.mapToScene(event.position().toPoint())
            self.rect_item = self.canvas.addRect(QRectF(self.origin, self.origin), QColor("#e44a3f"))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.rect_item.setRect(QRectF(self.origin, self.mapToScene(event.position().toPoint())).normalized())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            rect = self.rect_item.rect().intersected(self.canvas.sceneRect())
            self.rect_item.setRect(rect)
            self.origin = None
            if rect.width() > 2 and rect.height() > 2:
                w, h = self.image_size
                self.box_added.emit({"class_id": 0, "cx": rect.center().x() / w, "cy": rect.center().y() / h,
                                     "w": rect.width() / w, "h": rect.height() / h})
            else:
                self.canvas.removeItem(self.rect_item)
        else:
            super().mouseReleaseEvent(event)


class VisionPanel(QWidget):
    message = Signal(str)
    execute_requested = Signal(object, object)

    def __init__(self, project, paths, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.image = None
        self.boxes = []
        self.trainer = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        from PySide6.QtWidgets import QGridLayout
        bar = QGridLayout()
        bar.setSpacing(3)
        for index, (title, callback) in enumerate((("导入图片", self.import_images), ("清除标注", self.clear_boxes),
                                ("模拟 OCR/YOLO", self.simulate), ("导入模型", self.import_model),
                                ("OCR", self.real_ocr), ("模型测试", self.test_model), ("训练", self.train), ("停止训练", self.stop_training),
                                ("导出 ONNX", self.export_model))):
            button = QPushButton(title)
            button.clicked.connect(callback)
            bar.addWidget(button, index // 5, index % 5)
        layout.addLayout(bar)
        parameters = QHBoxLayout()
        parameters.addWidget(QLabel("训练轮数"))
        self.epochs = QSpinBox()
        self.epochs.setRange(1, 10000)
        self.epochs.setValue(1)
        parameters.addWidget(self.epochs)
        parameters.addWidget(QLabel("处理器"))
        parameters.addStretch()
        layout.addLayout(parameters)
        split = QSplitter()
        self.images = QListWidget()
        self.images.currentTextChanged.connect(self.select_image)
        self.canvas = Annotator()
        self.canvas.box_added.connect(self.add_box)
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.document().setMaximumBlockCount(1000)
        split.addWidget(self.images)
        split.addWidget(self.canvas)
        split.addWidget(self.info)
        split.setSizes([130, 600, 240])
        layout.addWidget(split)
        self.set_project(project)

    def set_project(self, project):
        self.stop_training()
        if self.trainer:
            self.trainer.deleteLater()
            self.trainer = None
        self.image, self.boxes = None, []
        self.canvas.origin = None
        self.canvas.rect_item = None
        self.canvas.image_size = None
        self.canvas.canvas.clear()
        self.project = project
        self.vision = VisionWorkbench(project.root, self.paths)
        self.images.clear()
        self.images.addItems([p.name for p in list_images(self.vision.dataset)])
        self.info.setPlainText(json.dumps(self.vision.model_manifest(), ensure_ascii=False, indent=2))

    def import_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "数据集", "", "图片 (*.png *.jpg *.bmp *.webp)")
        if files:
            try:
                copy_images_into_dataset(self.vision.dataset, files)
                self.set_project(self.project)
            except ValueError as exc:
                self.message.emit(str(exc))

    def select_image(self, name):
        if name:
            try:
                self.image = self.vision.dataset / "images" / name
                self.boxes = read_boxes(label_path_for(self.image, self.vision.dataset))
                self.canvas.load_image(self.image, self.boxes)
            except ValueError as exc:
                self.message.emit(str(exc))

    def add_box(self, box):
        if self.image:
            self.boxes.append(box)
            self.vision.add_annotation(self.image.name, self.boxes)

    def clear_boxes(self):
        if self.image:
            self.boxes = []
            self.vision.add_annotation(self.image.name, [])
            self.canvas.load_image(self.image, [])

    def simulate(self):
        result = {"ocr": self.vision.ocr("screen"), "yolo": self.vision.yolo("screen"), "simulated": True}
        self.info.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))

    def real_ocr(self):
        if self.image:
            vision, image = self.vision, self.image
            self.execute_requested.emit(lambda: vision.ocr(image, simulated=False), self._result)

    def _result(self, result):
        self.info.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))

    def import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "模型", "", "YOLO 模型 (*.pt *.onnx)")
        if path:
            try:
                self.vision.import_model(path)
                self.info.setPlainText(json.dumps(self.vision.model_manifest(), ensure_ascii=False, indent=2))
            except ValueError as exc:
                self.message.emit(str(exc))

    def test_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "ONNX 模型", str(self.vision.models), "ONNX (*.onnx)")
        if path and self.image:
            vision, image = self.vision, self.image
            self.execute_requested.emit(lambda: vision.yolo(image, model=path), self._result)

    def _training_task(self, operation):
        path, _ = QFileDialog.getOpenFileName(self, "YOLO 模型", str(self.vision.models), "YOLO (*.pt)")
        if path:
            from pcide.core.training import TrainingTask
            if self.trainer and self.trainer.active:
                self.message.emit("训练任务已经运行")
                return
            if self.trainer:
                self.trainer.deleteLater()
            self.trainer = TrainingTask(self.paths, self.vision, self)
            self.trainer.message.connect(self.message)
            self.trainer.start(operation, path, epochs=self.epochs.value())

    def train(self):
        self._training_task("train")

    def export_model(self):
        self._training_task("export")

    def stop_training(self):
        if self.trainer:
            self.trainer.stop()

    def shutdown(self):
        self.stop_training()
