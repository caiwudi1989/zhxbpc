from __future__ import annotations

import copy
import json

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from pcide.core.flow import NODE_KINDS, validate_flow
from pcide.ui.development_dialogs import dialog_buttons

NODE_LABELS = {'log': '输出日志', 'sleep': '等待', 'screenshot.mock': '模拟截图',
               'ocr.mock': '模拟 OCR', 'yolo.mock': '模拟 YOLO', 'fail': '报告失败', 'plugin.call': '插件调用'}
NODE_FIELDS = {
    'log': (('message', '日志内容', 'hello'),),
    'sleep': (('seconds', '等待秒数', 1),),
    'screenshot.mock': (('name', '模拟图片名称', 'screen'),),
    'ocr.mock': (('image', '模拟图片', 'screen'), ('text', '模拟识别结果', 'OK')),
    'yolo.mock': (('image', '模拟图片', 'screen'), ('label', '模拟目标类别', 'object')),
    'fail': (('message', '失败说明', '流程报告失败'),),
    'plugin.call': (('plugin', '已安装插件 ID', 'example.native_math'),
                    ('capability', '插件能力', 'math.answer'), ('params', '参数（JSON 对象）', {})),
}


class FlowNodeDialog(QDialog):
    def __init__(self, node, flow, parent=None):
        super().__init__(parent)
        self.node, self.flow = copy.deepcopy(node), copy.deepcopy(flow)
        self.setWindowTitle('流程节点：' + NODE_LABELS[node['kind']])
        self.resize(540, 350)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.identity = QLineEdit(node['id'])
        self.label = QLineEdit(node.get('label', node['id']))
        form.addRow('节点编号', self.identity)
        form.addRow('显示名称', self.label)
        form.addRow('节点类型', QLabel(NODE_LABELS[node['kind']] + ' (' + node['kind'] + ')'))
        self.fields = {}
        for key, label, default in NODE_FIELDS[node['kind']]:
            value = node.get('config', {}).get(key, default)
            if key == 'seconds':
                field = QDoubleSpinBox()
                field.setDecimals(3)
                field.setRange(0, 3600)
                field.setValue(float(value))
            elif key == 'params':
                field = QPlainTextEdit(json.dumps(value, ensure_ascii=False, indent=2))
                field.setMaximumHeight(140)
            else:
                field = QLineEdit(str(value))
            self.fields[key] = field
            form.addRow(label, field)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = dialog_buttons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            identity = self.identity.text().strip()
            if not identity or len(identity) > 128:
                raise ValueError('节点编号必须为 1..128 个字符')
            config = copy.deepcopy(self.node.get('config', {}))
            for key, field in self.fields.items():
                if isinstance(field, QDoubleSpinBox):
                    config[key] = field.value()
                elif isinstance(field, QPlainTextEdit):
                    config[key] = json.loads(field.toPlainText())
                    if not isinstance(config[key], dict):
                        raise ValueError('插件参数必须为 JSON 对象')
                else:
                    config[key] = field.text()
            old_id = self.node['id']
            self.result_node = {**self.node, 'id': identity, 'label': self.label.text(), 'config': config}
            candidate = copy.deepcopy(self.flow)
            next_index = next(index for index, item in enumerate(candidate['nodes']) if item['id'] == old_id)
            candidate['nodes'][next_index] = self.result_node
            candidate['edges'] = [[identity if value == old_id else value for value in edge] for edge in candidate['edges']]
            self.result_flow = copy.deepcopy(validate_flow(candidate))
            self.accept()
        except (ValueError, TypeError) as exc:
            self.error.setText(str(exc))


class NodeItem(QGraphicsObject):
    def __init__(self, node, canvas):
        super().__init__()
        self.node, self.canvas = node, canvas
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(*node.get('position', [20, 20]))

    def boundingRect(self):
        return QRectF(0, 0, 160, 72)

    def paint(self, painter, option, widget=None):
        painter.setBrush(QColor('#ffffff'))
        painter.setPen(QPen(QColor('#176ac6' if self.isSelected() else '#aab7c4'), 2 if self.isSelected() else 1))
        painter.drawRoundedRect(self.boundingRect(), 4, 4)
        painter.fillRect(QRectF(1, 1, 158, 5), QColor('#26856d' if '.mock' in self.node['kind'] else '#176ac6'))
        painter.setPen(QColor('#24313e'))
        painter.drawText(QRectF(10, 14, 140, 24), Qt.AlignmentFlag.AlignLeft, self.node.get('label', self.node['id']))
        painter.setPen(QColor('#667888'))
        painter.drawText(QRectF(10, 40, 140, 22), Qt.AlignmentFlag.AlignLeft, NODE_LABELS[self.node['kind']])

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.node['position'] = [round(self.pos().x()), round(self.pos().y())]
        self.canvas.draw_edges()
        self.canvas.changed.emit()

    def mouseDoubleClickEvent(self, event):
        self.canvas.edit_node(self)
        event.accept()


class FlowCanvas(QWidget):
    changed = Signal()
    run_requested = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.kind = QComboBox()
        for kind in NODE_KINDS:
            self.kind.addItem(NODE_LABELS[kind] + ' (' + kind + ')', kind)
        bar.addWidget(self.kind)
        for label, callback in (('添加节点', self.add_node), ('编辑节点', self.edit_selected), ('删除所选', self.delete_selected),
                                ('适应画布', self.fit_canvas), ('运行流程', self.run_requested.emit)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        connections = QHBoxLayout()
        self.source = QComboBox()
        self.target = QComboBox()
        connections.addWidget(QLabel('连接方向'))
        connections.addWidget(self.source, 1)
        connections.addWidget(QLabel('→'))
        connections.addWidget(self.target, 1)
        connect = QPushButton('连接')
        connect.clicked.connect(self.connect_selected)
        connections.addWidget(connect)
        layout.addLayout(connections)
        note = QLabel('双击编辑节点；选择连线后可删除。模拟截图/OCR/YOLO 只产生模拟数据；真实图像处理使用视觉工作台。流程运行最长 30 秒。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setBackgroundBrush(QColor('#f0f3f6'))
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.view)
        self.flow = {'version': 1, 'nodes': [], 'edges': []}
        self.nodes, self.edges = {}, []

    def snapshot(self):
        return copy.deepcopy(self.flow)

    def load(self, flow):
        self.flow = copy.deepcopy(validate_flow(flow))
        self.scene.clear()
        self.nodes, self.edges = {}, []
        for node in self.flow['nodes']:
            item = NodeItem(node, self)
            self.scene.addItem(item)
            self.nodes[node['id']] = item
        previous_source, previous_target = self.source.currentData(), self.target.currentData()
        self.source.clear()
        self.target.clear()
        for node in self.flow['nodes']:
            for combo in (self.source, self.target):
                combo.addItem(node.get('label', node['id']) + ' · ' + node['id'], node['id'])
        self.source.setCurrentIndex(max(0, self.source.findData(previous_source)))
        self.target.setCurrentIndex(max(0, self.target.findData(previous_target)) if previous_target else min(1, self.target.count() - 1))
        self.scene.setSceneRect(0, 0, 1500, 900)
        self.draw_edges()

    def draw_edges(self):
        for item in self.edges:
            self.scene.removeItem(item)
        self.edges = []
        for source, target in self.flow['edges']:
            a, b = self.nodes[source].pos(), self.nodes[target].pos()
            line = self.scene.addLine(a.x() + 160, a.y() + 36, b.x(), b.y() + 36, QPen(QColor('#7d92a6'), 2))
            line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            line.setData(0, [source, target])
            line.setToolTip(source + ' → ' + target)
            line.setZValue(-1)
            self.edges.append(line)
            vector = QPointF(b.x() - a.x() - 160, b.y() - a.y())
            length = max(1, (vector.x() ** 2 + vector.y() ** 2) ** 0.5)
            unit = QPointF(vector.x() / length, vector.y() / length)
            end = QPointF(b.x(), b.y() + 36)
            base = end - unit * 10
            side = QPointF(-unit.y() * 5, unit.x() * 5)
            arrow = self.scene.addPolygon(QPolygonF([end, base + side, base - side]), QPen(QColor('#7d92a6')), QColor('#7d92a6'))
            arrow.setZValue(-1)
            arrow.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            arrow.setData(0, [source, target])
            arrow.setToolTip(source + ' → ' + target)
            self.edges.append(arrow)

    def add_node(self):
        index = 1
        while f'node{index}' in self.nodes:
            index += 1
        kind = self.kind.currentData()
        config = {key: copy.deepcopy(default) for key, _, default in NODE_FIELDS[kind]}
        candidate = self.snapshot()
        candidate['nodes'].append({'id': f'node{index}', 'kind': kind, 'label': NODE_LABELS[kind],
                                   'position': [30 + index * 25, 120], 'config': config})
        try:
            self.load(candidate)
            self.changed.emit()
        except ValueError as exc:
            self.error.emit(str(exc))

    def edit_node(self, item):
        dialog = FlowNodeDialog(item.node, self.flow, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load(dialog.result_flow)
            self.changed.emit()

    def edit_selected(self):
        item = next((item for item in self.scene.selectedItems() if isinstance(item, NodeItem)), None)
        if item:
            self.edit_node(item)

    def connect_selected(self):
        source, target = self.source.currentData(), self.target.currentData()
        if source is None or target is None or source == target:
            self.error.emit('请选择不同的起点和终点')
            return
        edge = [source, target]
        if edge not in self.flow['edges']:
            candidate = self.snapshot()
            candidate['edges'].append(edge)
            try:
                self.load(candidate)
                self.changed.emit()
            except ValueError as exc:
                self.error.emit(str(exc))

    def delete_selected(self):
        selected = self.scene.selectedItems()
        removed = {item.node['id'] for item in selected if isinstance(item, NodeItem)}
        removed_edges = [item.data(0) for item in selected if not isinstance(item, NodeItem) and item.data(0)]
        candidate = self.snapshot()
        candidate['nodes'] = [node for node in candidate['nodes'] if node['id'] not in removed]
        candidate['edges'] = [edge for edge in candidate['edges'] if edge not in removed_edges and not any(node in removed for node in edge)]
        self.load(candidate)
        self.changed.emit()

    def fit_canvas(self):
        if self.nodes:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30), Qt.AspectRatioMode.KeepAspectRatio)
