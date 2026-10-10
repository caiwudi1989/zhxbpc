from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from pcide.core.agent import AgentSession, AgentTask
from pcide.core.agent_client import AgentClient
from pcide.core.agent_tools import project_tools
from pcide.core.agent_roles import ROLES
from pcide.core.runner import ScriptRunner

class _AgentSignals(QObject):
    done = Signal(object)
    event = Signal(object)
    ui_written = Signal(str)

class _AgentTask(QRunnable):
    def __init__(self, session, client, signals, role_prompt):
        super().__init__()
        self.session, self.client, self.signals = session, client, signals
        self.role_prompt = role_prompt

    def run(self):
        result = self.session.run_model(self.client, system_prompt=(
            "你是 zhxbpc 中文 Windows IDE 的高级编程 Agent。先理解项目结构，再使用工具检索；"
            "修改已有文件前必须 read，严格使用项目内相对路径。完成后说明改动、风险和验证结果。"
            + self.role_prompt
        ))
        self.signals.done.emit(result)

class AgentDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.session = None
        self._active = False
        self._closing = False
        self._verify_runner = None
        self.setWindowTitle("AI 编程助手")
        self.resize(760, 680)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit("https://api.deepseek.com/v1")
        self.model = QLineEdit("deepseek-chat")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.approved = QLineEdit(project.entry_path.relative_to(project.root).as_posix())
        self.approved.setPlaceholderText('逗号分隔精确路径；例如 src/main.py,ui/main.form.json')
        self.role = QComboBox(self)
        for role in ROLES:
            self.role.addItem(role.label, role.id)
        self.role.setCurrentIndex(1)
        self.allow_writes = QCheckBox("允许模型写入上面列出的路径（仍会先读取并校验语法）")
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("描述要完成的目标，例如：检查入口脚本并修复明显错误")
        form.addRow("兼容 API 地址", self.url)
        form.addRow("模型", self.model)
        form.addRow("助手角色", self.role)
        form.addRow("API Key（仅本次会话）", self.key)
        form.addRow("批准写入路径", self.approved)
        approve_ui=QPushButton('加入当前窗口与入口的批准路径')
        def include_ui():
            values=[value.strip() for value in self.approved.text().split(',') if value.strip()]
            for path in [self.project.entry_path,*self.project.window_paths()]:
                relative=path.relative_to(self.project.root).as_posix()
                if relative not in values:values.append(relative)
            self.approved.setText(','.join(values))
        approve_ui.clicked.connect(include_ui)
        form.addRow(approve_ui)
        form.addRow(self.allow_writes)
        root.addLayout(form)
        root.addWidget(self.prompt, 1)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(2000)
        self.output.setPlaceholderText("Agent 计划、工具调用和验证结果会显示在这里")
        root.addWidget(self.output, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('关闭')
        self.run_button = QPushButton("开始 Agent 任务")
        self.stop_button = QPushButton("取消")
        self.stop_button.setEnabled(False)
        buttons.addButton(self.run_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.stop_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.rejected.connect(self.reject)
        self.run_button.clicked.connect(self.start_task)
        self.stop_button.clicked.connect(self.stop_task)
        root.addWidget(buttons)

    def start_task(self):
        if self._active:
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "AI 助手", "请先输入任务目标")
            return
        paths = frozenset(item.strip().replace("\\", "/") for item in self.approved.text().split(",") if item.strip())
        signals = _AgentSignals(self)
        signals.ui_written.connect(self._ui_written)
        try:
            client = AgentClient(self.url.text().strip(), self.key.text().strip(), self.model.text().strip(), isolated=True)
            task = AgentTask(prompt, str(Path(self.project.root)), paths, allow_writes=self.allow_writes.isChecked())
            def verify_project():
                if self.session._cancel.is_set():
                    return {"ok": False, "error": "任务已取消"}
                runner = ScriptRunner()
                self._verify_runner = runner
                try:
                    from pcide.core.project import Project
                    project=Project.open(self.project.root)
                    from pcide.core.development import SCRIPT_LANGUAGES
                    if project.manifest['language'] not in SCRIPT_LANGUAGES:
                        from pcide.core.build_service import BuildService
                        from pcide.core.paths import Paths
                        return BuildService(Paths(),self.session._cancel).build(project)
                    code, output, state = runner.run_sync(project, timeout=min(60, project.manifest.get("execution", {}).get("timeout_seconds", 60)))
                    return {"ok": code == 0, "exit_code": code, "error": state.error, "output": output[-8000:]}
                finally:
                    runner.stop()
                    runner.wait(5)
                    self._verify_runner = None
            self.session = AgentSession(task, list(project_tools(self.project.root, paths, verify_project,on_ui_written=signals.ui_written.emit)))
        except Exception as exc:
            QMessageBox.critical(self, "AI 助手", str(exc))
            return
        self.output.clear()
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        signals.done.connect(self._finished)
        signals.event.connect(lambda event: self.output.appendPlainText(f"[{event.kind}] {event.message}"))
        self.session.on_event = signals.event.emit
        self._active = True
        selected = next(role for role in ROLES if role.id == self.role.currentData())
        self.pool.start(_AgentTask(self.session, client, signals, selected.system_prompt))

    def _ui_written(self,path):
        parent=self.parent()
        if parent and hasattr(parent,'current_form_path') and (self.project.root/path).resolve()==parent.current_form_path.resolve():
            parent.designer.load(self.project.load_window(self.project.root/path))
            parent.select_control('')
        self.output.appendPlainText('窗口JSON已通过合同校验并写入：'+path+'；关闭助手后重新载入工程，可预览实际UI。')

    def stop_task(self):
        if self.session:
            self.session.cancel()
        if self._verify_runner:
            self._verify_runner.stop()
        self.stop_button.setEnabled(False)

    def _finished(self, result):
        self._active = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        lines = [f"状态：{result.state.value}", result.reply]
        for event in result.events:
            if event.kind in {"tool_start", "tool_end", "approval_required", "failed", "completed"}:
                lines.append(f"[{event.kind}] {event.message}")
        if result.changes:
            lines.append("变更：" + ", ".join(str(item.get("path", "")) for item in result.changes))
        self.output.setPlainText("\n".join(lines))
        if self._closing:
            self.key.clear()
            super().reject()

    def reject(self):
        if self._active:
            self._closing = True
            self.stop_task()
            self.output.appendPlainText("正在停止任务并清理子进程…")
            return
        self.key.clear()
        super().reject()

    def closeEvent(self, event):
        if self._active:
            event.ignore()
            self.reject()
        else:
            self.key.clear()
            event.accept()
