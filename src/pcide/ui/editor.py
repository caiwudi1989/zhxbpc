from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineUrlScheme,
                                     QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from pcide.core.paths import Paths
from pcide.core.editor_projection import PYTHON_WORDS, JS_WORDS, transform


def register_editor_scheme():
    if QWebEngineUrlScheme.schemeByName(b"pcide").name():
        return
    scheme = QWebEngineUrlScheme(b"pcide")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.CorsEnabled |
                    QWebEngineUrlScheme.Flag.LocalAccessAllowed | QWebEngineUrlScheme.Flag.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)


class EditorAssets(QWebEngineUrlSchemeHandler):
    def __init__(self, paths, parent):
        super().__init__(parent)
        self.base = paths.resources / "third_party" / "monaco" / "vs"

    def requestStarted(self, job):
        url = job.requestUrl()
        if url.host() != "editor" or job.requestMethod() != b"GET":
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        relative = url.path().lstrip("/")
        try:
            if relative == "index.html":
                data = Path(__file__).with_name("editor.html").read_bytes()
                mime = b"text/html"
            elif relative == "worker.js":
                data = (b"self.MonacoEnvironment={baseUrl:'pcide://editor/'};"
                        b"importScripts('pcide://editor/vs/base/worker/workerMain.js');")
                mime = b"text/javascript"
            elif relative.startswith("vs/"):
                target = (self.base / relative[3:]).resolve()
                if not target.is_relative_to(self.base.resolve()) or not target.is_file():
                    raise FileNotFoundError(relative)
                data = target.read_bytes()
                mime = {".js": b"text/javascript", ".css": b"text/css", ".ttf": b"font/ttf",
                        ".json": b"application/json"}.get(target.suffix, b"application/octet-stream")
            else:
                raise FileNotFoundError(relative)
            buffer = QBuffer(job)
            buffer.setData(QByteArray(data))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(mime, buffer)
        except OSError:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)


class Bridge(QObject):
    ready = Signal()
    changed = Signal(str, str)
    cursor = Signal(str, int)
    breakpoint = Signal(str, int)
    error = Signal(str)

    @Slot()
    def editorReady(self):
        self.ready.emit()

    @Slot(str, str)
    def textChanged(self, uri, text):
        self.changed.emit(uri, text)

    @Slot(str, int)
    def cursorChanged(self, uri, line):
        self.cursor.emit(uri, line)

    @Slot(str, int)
    def toggleBreakpoint(self, uri, line):
        self.breakpoint.emit(uri, line)

    @Slot(str)
    def reportError(self, message):
        self.error.emit(message)


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.scheme() in {"pcide", "qrc", "about", "data"}

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.parent().bridge.error.emit(f"Monaco {line}: {message}")


class CodeEditor(QWidget):
    ready = Signal()
    changed = Signal(str)
    cursor = Signal(str, int)
    breakpoint = Signal(str, int)
    error = Signal(str)

    def __init__(self, paths: Paths, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.documents: dict[str, str] = {}
        self.saved: dict[str, str] = {}
        self.path: str | None = None
        self.loaded = False
        self.completion_items: list[dict] = []
        self.chinese_view = True
        self.bridge = Bridge(self)
        self.bridge.ready.connect(self._ready)
        self.bridge.changed.connect(self._changed)
        self.bridge.cursor.connect(self.cursor)
        self.bridge.breakpoint.connect(self.breakpoint)
        self.bridge.error.connect(self.error)
        self.profile = QWebEngineProfile(self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.profile.setPersistentStoragePath(str(paths.cache / "webengine"))
        self.assets = EditorAssets(paths, self.profile)
        self.profile.installUrlSchemeHandler(b"pcide", self.assets)
        self.view = QWebEngineView(self)
        self.page = LocalPage(self.profile, self)
        self.view.setPage(self.page)
        channel = QWebChannel(self.page)
        channel.registerObject("bridge", self.bridge)
        self.page.setWebChannel(channel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.setUrl(QUrl("pcide://editor/index.html"))

    def _ready(self):
        self.loaded = True
        if self.path:
            self._show_model(self.path)
        self.ready.emit()

    def _changed(self, path, text):
        if path not in self.documents:
            return
        language = self._language(path)
        self.documents[path] = transform(text, language, reverse=True) if self.chinese_view else text
        self.changed.emit(path)

    def load(self, path: str | Path):
        self.path = str(Path(path).resolve())
        if self.path not in self.documents:
            text = Path(self.path).read_text(encoding="utf-8")
            if len(text) > 5 * 1024 * 1024:
                raise ValueError("editor file exceeds 5 MiB")
            self.documents[self.path] = text
            self.saved[self.path] = text
        if self.loaded:
            self._show_model(self.path)

    def _show_model(self, path):
        language = self._language(path)
        args = json.dumps({"path": path, "language": language, "text": self.documents[path],
                           "completions": self.completion_items, "chinese": self.chinese_view,
                           "words": PYTHON_WORDS if language == "python" else JS_WORDS}, ensure_ascii=False)
        self.page.runJavaScript(f"pcide.open({args})")

    @staticmethod
    def _language(path):
        return {".py": "python", ".ts": "typescript", ".js": "javascript", ".json": "json", ".cs": "csharp", ".c": "cpp"}.get(Path(path).suffix.lower(), "plaintext")

    def set_completion_items(self, items):
        """Update project symbols used by Monaco's Yi-style completion popup."""
        normalized = []
        seen = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            normalized.append({
                "label": label,
                "insertText": str(item.get("insertText", label)),
                "kind": str(item.get("kind", "variable")),
                "detail": str(item.get("detail", "")),
                "documentation": str(item.get("documentation", "")),
                "parameters": item.get("parameters", []),
            })
        self.completion_items = normalized[:2000]
        if self.loaded and self.path:
            self.page.runJavaScript(f"pcide.setCompletions({json.dumps(self.completion_items, ensure_ascii=False)})")

    def set_chinese_view(self, enabled):
        self.chinese_view = bool(enabled)
        if self.loaded and self.path:
            self._show_model(self.path)

    def toggle_chinese_view(self):
        self.set_chinese_view(not self.chinese_view)

    def capture(self, callback):
        if not self.loaded:
            self.error.emit("代码编辑器尚未就绪")
            return
        def done(result):
            try:
                snapshot = json.loads(result)
                self._changed(snapshot["path"], snapshot["text"])
                callback()
            except (ValueError, TypeError, KeyError) as exc:
                self.error.emit(f"Monaco snapshot failed: {exc}")
        self.page.runJavaScript("JSON.stringify(pcide.snapshot())", done)

    def save(self, all_documents=True):
        selected = self.documents if all_documents else {self.path: self.documents[self.path]}
        for path, text in selected.items():
            if self.saved.get(path) != text:
                Path(path).write_text(text, encoding="utf-8", newline="\n")
                self.saved[path] = text

    def goto(self, line: int):
        if self.loaded:
            self.page.runJavaScript(f"pcide.goto({int(line)})")

    def set_breakpoints(self, lines):
        if self.loaded:
            self.page.runJavaScript(f"pcide.breakpoints({json.dumps(sorted(lines))})")

    def set_value(self, text):
        if self.path:
            self.documents[self.path] = text
            if self.loaded:
                self.page.runJavaScript(f"pcide.setValue({json.dumps(text)})")

    def insert_text(self, text):
        if self.loaded:
            self.page.runJavaScript(f"pcide.insertText({json.dumps(str(text), ensure_ascii=False)})")

    def close_project(self):
        self.path = None
        self.documents.clear()
        self.saved.clear()
        if self.loaded:
            self.page.runJavaScript("pcide.dispose()")

    def shutdown(self):
        self.page.setWebChannel(None)
        self.page.deleteLater()
        self.profile.deleteLater()
