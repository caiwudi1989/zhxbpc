from __future__ import annotations

import copy
import json

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QInputDialog, QPushButton, QVBoxLayout, QWidget)

from pcide.core.flow import NODE_KINDS, validate_flow


class NodeItem(QGraphicsObject):
    def __init__(self, node, canvas):
        super().__init__()
        self.node, self.canvas = node, canvas
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(*node.get("position", [20, 20]))

    def boundingRect(self):
        return QRectF(0, 0, 160, 72)

    def paint(self, painter, option, widget=None):
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#176ac6" if self.isSelected() else "#aab7c4"), 2 if self.isSelected() else 1))
        painter.drawRoundedRect(self.boundingRect(), 4, 4)
        painter.fillRect(QRectF(1, 1, 158, 5), QColor("#26856d" if ".mock" in self.node["kind"] else "#176ac6"))
        painter.setPen(QColor("#24313e"))
        painter.drawText(QRectF(10, 14, 140, 24), Qt.AlignmentFlag.AlignLeft, self.node.get("label", self.node["id"]))
        painter.setPen(QColor("#667888"))
        painter.drawText(QRectF(10, 40, 140, 22), Qt.AlignmentFlag.AlignLeft, self.node["kind"])

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.node["position"] = [round(self.pos().x()), round(self.pos().y())]
        self.canvas.draw_edges()
        self.canvas.changed.emit()

    def mouseDoubleClickEvent(self, event):
        text, ok = QInputDialog.getMultiLineText(self.canvas, "节点参数", "JSON", json.dumps(self.node.get("config", {}), ensure_ascii=False, indent=2))
        if ok:
            try:
                config = json.loads(text)
                if not isinstance(config, dict):
                    raise ValueError("参数必须为 JSON 对象")
                candidate = copy.deepcopy(self.canvas.flow)
                next(n for n in candidate["nodes"] if n["id"] == self.node["id"])["config"] = config
                validate_flow(candidate)
                self.node["config"] = config
                self.canvas.changed.emit()
            except ValueError as exc:
                self.canvas.error.emit(str(exc))


class FlowCanvas(QWidget):
    changed = Signal()
    run_requested = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(NODE_KINDS)
        bar.addWidget(self.kind)
        for label, callback in (("添加节点", self.add_node), ("连接所选", self.connect_selected),
                                ("删除", self.delete_selected), ("运行流程", self.run_requested.emit)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setBackgroundBrush(QColor("#f0f3f6"))
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.view)
        self.flow = {"version": 1, "nodes": [], "edges": []}
        self.nodes = {}
        self.edges = []

    def load(self, flow):
        self.flow = copy.deepcopy(validate_flow(flow))
        self.scene.clear()
        self.nodes, self.edges = {}, []
        for node in self.flow["nodes"]:
            item = NodeItem(node, self)
            self.scene.addItem(item)
            self.nodes[node["id"]] = item
        self.scene.setSceneRect(0, 0, 1500, 900)
        self.draw_edges()

    def draw_edges(self):
        for item in self.edges:
            self.scene.removeItem(item)
        self.edges = []
        for source, target in self.flow["edges"]:
            a, b = self.nodes[source].pos(), self.nodes[target].pos()
            line = self.scene.addLine(a.x() + 160, a.y() + 36, b.x(), b.y() + 36, QPen(QColor("#7d92a6"), 2))
            line.setZValue(-1)
            self.edges.append(line)

    def add_node(self):
        index = 1
        while f"node{index}" in self.nodes:
            index += 1
        kind = self.kind.currentText()
        config = {"sleep": {"seconds": 1}, "log": {"message": "hello"}, "ocr.mock": {"text": "OK"},
                  "yolo.mock": {"label": "object"}, "plugin.call": {"plugin": "example.native_math", "capability": "math.answer"}}.get(kind, {})
        node = {"id": f"node{index}", "kind": kind, "label": kind, "position": [30 + index * 25, 120], "config": config}
        self.flow["nodes"].append(node)
        self.load(self.flow)
        self.changed.emit()

    def connect_selected(self):
        selected = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        if len(selected) == 2:
            selected.sort(key=lambda i: i.pos().x())
            edge = [selected[0].node["id"], selected[1].node["id"]]
            if edge not in self.flow["edges"]:
                candidate = copy.deepcopy(self.flow)
                candidate["edges"].append(edge)
                try:
                    validate_flow(candidate)
                    self.load(candidate)
                    self.changed.emit()
                except ValueError as exc:
                    self.error.emit(str(exc))

    def delete_selected(self):
        removed = {i.node["id"] for i in self.scene.selectedItems() if isinstance(i, NodeItem)}
        self.flow["nodes"] = [n for n in self.flow["nodes"] if n["id"] not in removed]
        self.flow["edges"] = [e for e in self.flow["edges"] if not any(n in removed for n in e)]
        self.load(self.flow)
        self.changed.emit()
