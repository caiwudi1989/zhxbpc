from __future__ import annotations

import copy

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from pcide.core.development import SCRIPT_LANGUAGES, template_for
from pcide.core.paths import node_runtime
from pcide.core.platform import discover_providers, validate_platform
from pcide.core.processes import host_command
from pcide.core.product import subsystem_catalog
from pcide.ui.development_dialogs import dialog_buttons


class EnvironmentDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle('项目环境 / 运行限制')
        self.resize(760, 370)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow('工程语言', QLabel(project.manifest['language']))
        form.addRow('开发模式', QLabel(template_for(project).label))
        scripted = project.manifest['language'] in SCRIPT_LANGUAGES
        if project.manifest['language'] in {'python', 'zhxb'}:
            profile = 'vision' if 'vision' in project.manifest.get('modules', []) else 'basic'
            command = host_command('worker', profile)
            engine = ' '.join(command)
        elif project.manifest['language'] in {'javascript', 'typescript'}:
            engine = node_runtime() or '未配置 Node.js'
        else:
            engine = '当前工程使用系统工具 / 浏览器 / 引擎；在“系统工具与游戏引擎”中配置。'
        self.engine = QLineEdit(engine)
        self.engine.setReadOnly(True)
        form.addRow('当前执行入口', self.engine)
        settings = project.manifest.get('execution', {})
        self.timeout = QDoubleSpinBox()
        self.timeout.setDecimals(3)
        self.timeout.setRange(0.001, 86400)
        self.timeout.setValue(settings.get('timeout_seconds', 60))
        self.output_limit = QSpinBox()
        self.output_limit.setRange(1, 50000)
        self.output_limit.setValue(settings.get('max_output_lines', 5000))
        for field in (self.timeout, self.output_limit):
            field.setEnabled(scripted)
        form.addRow('脚本最长运行时间（秒）', self.timeout)
        form.addRow('脚本输出行数上限', self.output_limit)
        layout.addLayout(form)
        note = QLabel('运行限制在下一次脚本启动时生效。工程语言由新建模板确定；本页不转换源码。系统发布与编译使用系统工具页中的路径。')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = dialog_buttons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def execution(self):
        if self.project.manifest['language'] not in SCRIPT_LANGUAGES:
            return copy.deepcopy(self.project.manifest.get('execution', {}))
        return {'timeout_seconds': self.timeout.value(), 'max_output_lines': self.output_limit.value()}


class PlatformCapabilitiesDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle('平台能力与提供者')
        self.resize(950, 720)
        self.platform = validate_platform(project.manifest.get('platform'))
        layout = QVBoxLayout(self)
        note = QLabel('此页登记能力开关和配置声明；开启开关不会安装、下载或实现提供者。实际执行入口与依赖请查看各功能页。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['能力', '启用', '配置项', '配置内容（逗号分隔）', '合同版本'])
        self.checks, self.fields = {}, {}
        for subsystem in subsystem_catalog():
            kind = subsystem['kind']
            config = self.platform['capabilities'][kind]
            values = [(key, value) for key, value in config.items() if key != 'enabled'] or [('', [])]
            for index, (key, values) in enumerate(values):
                row = self.table.rowCount()
                self.table.insertRow(row)
                for column, text in ((0, subsystem['label']), (2, key), (4, subsystem['contract'])):
                    item = QTableWidgetItem(text)
                    from PySide6.QtCore import Qt
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
                if index == 0:
                    check = QCheckBox()
                    check.setChecked(config['enabled'])
                    check.toggled.connect(self.update_summary)
                    self.checks[kind] = check
                    self.table.setCellWidget(row, 1, check)
                if key:
                    field = QLineEdit(','.join(values))
                    self.fields[(kind, key)] = field
                    self.table.setCellWidget(row, 3, field)
        self.table.setColumnWidth(0, 190)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 330)
        self.table.setColumnWidth(4, 140)
        layout.addWidget(self.table, 1)
        layout.addWidget(QLabel('工程提供者声明（只读取清单，不加载提供者代码）'))
        self.providers = QTableWidget(0, 5)
        self.providers.setHorizontalHeaderLabels(['提供者 ID', '能力', '版本', '来源', '清单位置'])
        self.providers.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        registered = self.platform['providers']
        records = [(item, '工程登记') for item in registered]
        seen = {item['id'] for item in registered}
        provider_root = project.root / 'providers'
        if provider_root.resolve().is_relative_to(project.root.resolve()):
            records.extend((item, '文件发现') for item in discover_providers(project.root) if item['id'] not in seen)
        for item, origin in records:
            row = self.providers.rowCount()
            self.providers.insertRow(row)
            for column, value in enumerate((item['id'], item['kind'], item.get('version', '1.0.0'), origin, item.get('manifest', '.pcide/project.json'))):
                self.providers.setItem(row, column, QTableWidgetItem(value))
        self.providers.setColumnWidth(0, 180)
        self.providers.setColumnWidth(4, 330)
        layout.addWidget(self.providers, 1)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = dialog_buttons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_summary()

    def update_summary(self, _checked=False):
        if hasattr(self, 'summary'):
            self.summary.setText(f'启用 {sum(check.isChecked() for check in self.checks.values())} / {len(self.checks)} 项能力；工程登记 {len(self.platform["providers"])} 个提供者，表中显示 {self.providers.rowCount()} 个声明。')

    def save(self):
        try:
            platform = copy.deepcopy(self.platform)
            for kind, check in self.checks.items():
                platform['capabilities'][kind]['enabled'] = check.isChecked()
            for (kind, key), field in self.fields.items():
                platform['capabilities'][kind][key] = [value.strip() for value in field.text().split(',') if value.strip()]
            self.result_platform = validate_platform(platform)
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))
