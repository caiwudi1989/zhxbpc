from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QSignalBlocker, QStringListModel, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineUrlScheme,
                                     QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QVBoxLayout, QWidget

from pcide.core.paths import Paths
from pcide.core.editor_projection import PYTHON_WORDS, JS_WORDS, transform


def _env_flag(name: str) -> bool:
    """Read a conventional boolean environment flag without treating ``0`` as true."""
    return os.environ.get(name, "").strip().lower() not in {"", "0", "false", "no", "off"}


def _webengine_blocked() -> bool:
    """Return whether the host is known to reject Qt WebEngine's Chromium IPC."""
    if _env_flag("PCIDE_DISABLE_WEBENGINE") or _env_flag("PCIDE_NO_WEBENGINE"):
        return True
    # Codex's restricted Windows token rejects the Mojo named-pipe creation
    # before QWebEnginePage can report an error.  CI/headless Qt platforms have
    # the same failure mode and should use the native editor as well.
    markers = ("CODEX_WINDOWS_SANDBOX_PACKAGE", "CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY",
               "CODEX_WINDOWS_RESTRICTED_TOKEN", "CI", "GITHUB_ACTIONS")
    return any(_env_flag(name) for name in markers) or os.environ.get("QT_QPA_PLATFORM", "").lower() in {"offscreen", "minimal"}


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


class _FallbackPage:
    """Small local page shim used when Chromium IPC is unavailable.

    The Codex Windows sandbox blocks QtWebEngine's named Mojo pipe before the
    first page can be shown.  Falling back to a native editor keeps the IDE
    usable and avoids an OS crash dialog; normal desktop launches continue to
    use Monaco unless ``PCIDE_DISABLE_WEBENGINE`` is set.
    """
    def __init__(self, editor):
        self.editor = editor

    def runJavaScript(self, script, callback=None):
        script = str(script or "")
        value = None
        if "JSON.stringify(pcide.snapshot())" in script:
            value = json.dumps(self.editor._fallback_snapshot(), ensure_ascii=False)
        elif "pcide.setValue(" in script:
            marker = "pcide.setValue("
            try:
                payload = script.split(marker, 1)[1].rsplit(")", 1)[0]
                self.editor._fallback_set_text(json.loads(payload))
            except (IndexError, TypeError, ValueError):
                pass
        elif "pcide.insertText(" in script:
            marker = "pcide.insertText("
            try:
                payload = script.split(marker, 1)[1].rsplit(")", 1)[0]
                self.editor._fallback_edit.insertPlainText(json.loads(payload))
            except (IndexError, TypeError, ValueError):
                pass
        elif "pcide.goto(" in script:
            try:
                line = int(script.split("pcide.goto(", 1)[1].split(")", 1)[0])
                self.editor._fallback_goto(line)
            except (IndexError, ValueError):
                pass
        elif "pcide.undo()" in script:
            self.editor.undo()
        elif "pcide.redo()" in script:
            self.editor.redo()
        elif "pcide.triggerSuggest()" in script:
            self.editor.trigger_completion()
        if callback is not None:
            callback(value)

    def setWebChannel(self, _channel):
        return None

    def deleteLater(self):
        return None


class _NativeHighlighter(QSyntaxHighlighter):
    """Small dependency-free syntax highlighter for the restricted-host editor."""

    def __init__(self, document):
        super().__init__(document)
        self.language = "python"
        self._formats = {
            "keyword": self._format("#0000aa", bold=True),
            "string": self._format("#a31515"),
            "comment": self._format("#6b8e23"),
            "number": self._format("#098658"),
        }

    @staticmethod
    def _format(color, bold=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def set_language(self, language):
        self.language = language
        self.rehighlight()

    def highlightBlock(self, text):
        import re
        comment = r"#.*$" if self.language in {"python", "zhxb"} else r"//.*$"
        for match in re.finditer(comment, text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["comment"])
        for match in re.finditer(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`", text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["string"])
        words = (r"\b(?:and|as|assert|async|await|break|class|continue|def|elif|else|for|from|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b"
                 if self.language in {"python", "zhxb"} else
                 r"\b(?:const|let|var|function|return|if|else|for|while|class|new|async|await|true|false|null|undefined)\b")
        for match in re.finditer(words, text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["keyword"])
        for match in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["number"])


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
        backend = os.environ.get("PCIDE_EDITOR_BACKEND", "auto").strip().lower()
        self._fallback = backend == "native" or (backend != "monaco" and _webengine_blocked())
        self.bridge = Bridge(self)
        self.bridge.ready.connect(self._ready)
        self.bridge.changed.connect(self._changed)
        self.bridge.cursor.connect(self.cursor)
        self.bridge.breakpoint.connect(self.breakpoint)
        self.bridge.error.connect(self.error)
        if self._fallback:
            self.profile = None
            self.view = QPlainTextEdit(self)
            self._fallback_edit = self.view
            self._fallback_edit.textChanged.connect(self._fallback_changed)
            self._fallback_edit.cursorPositionChanged.connect(self._fallback_cursor_changed)
            self._fallback_highlighter = _NativeHighlighter(self._fallback_edit.document())
            self._fallback_breakpoints = set()
            self._fallback_completer = QCompleter(self)
            self._fallback_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._fallback_completer.setWidget(self._fallback_edit)
            self._fallback_completer.activated.connect(self._insert_completion)
            self._fallback_completion_model = QStringListModel([], self._fallback_completer)
            self._fallback_completer.setModel(self._fallback_completion_model)
            self.page = _FallbackPage(self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.view)
            self.loaded = True
            QTimer.singleShot(0, self.ready.emit)
            return
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

    def _fallback_changed(self):
        if self.path and not getattr(self, "_fallback_loading", False):
            self.documents[self.path] = self._fallback_edit.toPlainText()
            self.changed.emit(self.path)

    def _fallback_cursor_changed(self):
        if self.path and not getattr(self, "_fallback_loading", False):
            self.cursor.emit(self.path, self._fallback_edit.textCursor().blockNumber() + 1)

    def _insert_completion(self, text):
        self._fallback_edit.insertPlainText(str(text))

    def trigger_completion(self):
        if not self._fallback or not self.completion_items:
            return
        self._fallback_completer.complete(self._fallback_edit.cursorRect())

    def _fallback_set_text(self, text):
        text = str(text)
        self._fallback_loading = True
        try:
            with QSignalBlocker(self._fallback_edit):
                self._fallback_edit.setPlainText(text)
        finally:
            self._fallback_loading = False
        if self.path:
            # Keep the model authoritative.  Some restricted Qt platforms
            # deliver ``textChanged`` after ``setPlainText`` returns, which
            # can otherwise overwrite a freshly loaded document with an
            # empty intermediate value.
            self.documents[self.path] = text

    def _fallback_goto(self, line):
        line = max(1, int(line))
        cursor = self._fallback_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(line - 1):
            if not cursor.movePosition(cursor.MoveOperation.NextBlock):
                break
        self._fallback_edit.setTextCursor(cursor)

    def _fallback_snapshot(self):
        text = self._fallback_edit.toPlainText() if self.path else ""
        return {"path": self.path or "", "text": text,
                "position": {"lineNumber": self._fallback_edit.textCursor().blockNumber() + 1}}

    def _ready(self):
        self.loaded = True
        if self.path:
            self._show_model(self.path)
        self.ready.emit()

    def _changed(self, path, text):
        if path not in self.documents:
            return
        language = self._language(path)
        # The native editor displays source verbatim, so Chinese identifiers
        # must never be converted back into Python/JavaScript keywords.
        self.documents[path] = transform(text, language, reverse=True) if self.chinese_view and not self._fallback else text
        self.changed.emit(path)

    def load(self, path: str | Path):
        new_path = str(Path(path).resolve())
        new_document = new_path not in self.documents
        if new_document:
            text = Path(new_path).read_text(encoding="utf-8")
            # Keep a local copy before touching the native document; some
            # Qt builds synchronously emit a stale ``textChanged`` callback
            # while switching models.
            if len(text) > 5 * 1024 * 1024:
                raise ValueError("editor file exceeds 5 MiB")
            self.documents[new_path] = text
            self.saved[new_path] = text
        self.path = new_path
        if self.loaded:
            if self._fallback:
                # Do not let a model switch callback observe the new path
                # while the widget is being cleared and refilled.
                source = self.documents[self.path]
                self.path = None
                self._fallback_highlighter.set_language(self._language(new_path))
                self._fallback_set_text(source)
                self.path = new_path
                self.documents[new_path] = source
            else:
                self._show_model(self.path)

    def _show_model(self, path):
        if self._fallback:
            self._fallback_highlighter.set_language(self._language(path))
            self._fallback_set_text(self.documents[path])
            return
        language = self._language(path)
        args = json.dumps({"path": path, "language": language, "text": self.documents[path],
                           "completions": self.completion_items, "chinese": self.chinese_view,
                           "words": PYTHON_WORDS if language == "python" else JS_WORDS}, ensure_ascii=False)
        self.page.runJavaScript(f"pcide.open({args})")

    @staticmethod
    def _language(path):
        return {".py": "python", ".ts": "typescript", ".js": "javascript", ".json": "json", ".cs": "csharp", ".c": "cpp", ".zhxb": "zhxb"}.get(Path(path).suffix.lower(), "plaintext")

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
        if self._fallback:
            self._fallback_completion_model.setStringList([item["label"] for item in self.completion_items])
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

    def undo(self):
        if self._fallback:
            self._fallback_edit.undo()
        elif self.loaded:
            self.page.runJavaScript("pcide.undo()")

    def redo(self):
        if self._fallback:
            self._fallback_edit.redo()
        elif self.loaded:
            self.page.runJavaScript("pcide.redo()")

    def toggle_breakpoint_at_cursor(self):
        if not self.path:
            return
        line = self._fallback_edit.textCursor().blockNumber() + 1 if self._fallback else None
        if line is not None:
            self.breakpoint.emit(self.path, line)

    def show_find(self, replace=False):
        if not self.loaded:
            return
        if self._fallback:
            self._fallback_edit.setFocus()
            self._fallback_edit.find("")
            return
        self.page.runJavaScript(f"pcide.find({str(bool(replace)).lower()})")

    def replace(self, search, replacement, replace_all=False):
        if not self.path or not search:
            return 0
        text = self.documents.get(self.path, "")
        count = text.count(search)
        if count:
            updated = text.replace(search, replacement) if replace_all else text.replace(search, replacement, 1)
            self.set_value(updated)
        return count if replace_all else min(count, 1)

    @staticmethod
    def _format_text(path, text):
        suffix = Path(path).suffix.lower()
        if suffix == ".json":
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2) + "\n"
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
        while len(lines) > 1 and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n"

    def format_document(self):
        if not self.path:
            return
        try:
            formatted = self._format_text(self.path, self.documents.get(self.path, ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.error.emit(f"无法格式化：{exc}")
            return
        self.set_value(formatted)

    def set_breakpoints(self, lines):
        if self.loaded:
            if self._fallback:
                self._fallback_breakpoints = set(int(line) for line in lines)
                selections = []
                for line in sorted(self._fallback_breakpoints):
                    block = self._fallback_edit.document().findBlockByLineNumber(line - 1)
                    if block.isValid():
                        selections.append((block, QColor("#ffe1e1")))
                extra = []
                for block, color in selections:
                    selection = QPlainTextEdit.ExtraSelection()
                    selection.format.setBackground(color)
                    selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
                    selection.cursor = self._fallback_edit.textCursor()
                    selection.cursor.setPosition(block.position())
                    selection.cursor.movePosition(selection.cursor.MoveOperation.EndOfBlock, selection.cursor.MoveMode.KeepAnchor)
                    extra.append(selection)
                self._fallback_edit.setExtraSelections(extra)
            else:
                self.page.runJavaScript(f"pcide.breakpoints({json.dumps(sorted(lines))})")

    def set_value(self, text):
        if self.path:
            self.documents[self.path] = text
            if self.loaded:
                if self._fallback:
                    self._fallback_edit.setPlainText(str(text))
                else:
                    self.page.runJavaScript(f"pcide.setValue({json.dumps(text)})")

    def insert_text(self, text):
        if self.loaded:
            self.page.runJavaScript(f"pcide.insertText({json.dumps(str(text), ensure_ascii=False)})")

    def close_project(self):
        self.path = None
        self.documents.clear()
        self.saved.clear()
        if self.loaded:
            if self._fallback:
                self._fallback_set_text("")
            else:
                self.page.runJavaScript("pcide.dispose()")

    def shutdown(self):
        if self._fallback:
            return
        self.page.setWebChannel(None)
        self.page.deleteLater()
        self.profile.deleteLater()
