from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit, QTabWidget, QVBoxLayout

from pcide.core.api_center import generate_client_module, validate_endpoint
from pcide.core.database import generate_python_module, validate_schema

class DatabaseDesignerDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("数据库设计器")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入 version 1 数据库 schema；保存后可由 SQLite/其他 provider 读取。"))
        self.editor = QPlainTextEdit(self)
        default = {"version": 1, "tables": [{"name": "users", "columns": [{"name": "id", "type": "INTEGER", "primary_key": True}, {"name": "name", "type": "TEXT"}], "indexes": ["name"]}]}
        schema_file = project.root / "database" / "schema.json"
        self.editor.setPlainText(schema_file.read_text(encoding="utf-8") if schema_file.is_file() else json.dumps(default, ensure_ascii=False, indent=2))
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            raw = json.loads(self.editor.toPlainText())
            normalized = validate_schema(raw)
            path = self.project.root / "database" / "schema.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            generated = generate_python_module(normalized)
            (self.project.root / "src" / "generated_database.py").write_text(generated, encoding="utf-8")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "数据库 schema 无效", str(exc))

class ApiCenterDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("API 中心")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入接口数组；支持 HTTP/HTTPS/WebSocket/TCP/UDP/MQTT 合同。"))
        self.editor = QPlainTextEdit(self)
        default = [{"id": "users.list", "name": "用户列表", "method": "GET", "path": "/v1/users", "protocol": "https"}]
        endpoint_file = project.root / "api" / "endpoints.json"
        self.editor.setPlainText(endpoint_file.read_text(encoding="utf-8") if endpoint_file.is_file() else json.dumps(default, ensure_ascii=False, indent=2))
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            raw = json.loads(self.editor.toPlainText())
            if not isinstance(raw, list) or len(raw) > 500:
                raise ValueError("接口必须是最多 500 项的数组")
            endpoints = [validate_endpoint(item) for item in raw]
            if len({item.id for item in endpoints}) != len(endpoints):
                raise ValueError("接口 ID 不能重复")
            normalized = [item.__dict__ for item in endpoints]
            endpoint_file = self.project.root / "api" / "endpoints.json"
            endpoint_file.parent.mkdir(parents=True, exist_ok=True)
            endpoint_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            language = self.project.manifest.get("language", "python")
            target_language = language if language in {"python", "javascript", "typescript"} else "python"
            source = generate_client_module(endpoints, target_language)
            extension = ".py" if target_language == "python" else ".ts" if target_language == "typescript" else ".js"
            (self.project.root / "src" / ("generated_api" + extension)).write_text(source, encoding="utf-8")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "API 配置无效", str(exc))
