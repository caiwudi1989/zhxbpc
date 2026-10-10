"""Actual Qt input checks, restricted to disposable project copies."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from .routine_ranges import scan_editor


def exercise_editor_input(window):
    if not window.project.root.resolve().is_relative_to(window.paths.cache.resolve()):
        raise ValueError('Input verification requires a disposable project under cache')
    app = QApplication.instance()
    editor = window.editor
    window.show_page('code')
    window.raise_()
    window.activateWindow()
    stage = 'initialization'

    def until(predicate):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        raise AssertionError(f'Editor input verification timed out: {stage}')

    def js(code):
        values = []
        editor.page.runJavaScript(code, values.append)
        until(lambda: bool(values))
        return values[0]

    def snapshot():
        return json.loads(js('JSON.stringify(pcide.snapshot())'))

    def keyboard():
        target = app.focusWidget()
        if target is None or not (target is editor.view or editor.isAncestorOf(target)):
            raise AssertionError(f'Clicking the source did not focus the code editor: focus={type(target).__name__}, state={snapshot()!r}')
        return target

    records = []
    names = [item['sourceName'] for item in scan_editor(snapshot()['text'], Path(editor.path).suffix)]
    for index, name in enumerate(names):
        stage = f'{name}: expand and click body'
        window.activateWindow()
        editor.fold_all(True)
        if editor._fallback:
            panel = editor.routine_panel
            panel.selector.setCurrentIndex(panel.selector.findData(name))
            panel.collapsed.discard(panel.collapse_key(name))
            panel.select(panel.selector.currentIndex())
            QTest.qWait(60)
            routine = next(item for item in scan_editor(snapshot()['text'], Path(editor.path).suffix) if item['sourceName'] == name)
            block = editor.view.document().findBlockByNumber(routine['bodyLine'] - 1)
            rect = editor.view.blockBoundingGeometry(block).translated(editor.view.contentOffset())
            QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(100, round(rect.top() + rect.height() / 2)))
        else:
            until(lambda: all(item['collapsed'] for item in snapshot()['routines']))
            selector = json.dumps(name)
            js(f"document.querySelectorAll('.routine-toggle')[pcide.snapshot().routines.findIndex(item=>item.sourceName==={selector})].click();'ok'")
            until(lambda: not next(item for item in snapshot()['routines'] if item['sourceName'] == name)['collapsed'])
            QTest.qWait(100)
            point = json.loads(js("JSON.stringify((()=>{const r=[...document.querySelectorAll('.view-line')].find(node=>node.textContent.trim()).getBoundingClientRect();return {x:r.x+100,y:r.y+r.height/2};})())"))
            QTest.mouseClick(editor.view.focusProxy() or editor.view, Qt.MouseButton.LeftButton, pos=QPoint(round(point['x']), round(point['y'])))
        QTest.qWait(100)
        assert snapshot()['readOnly'] is False
        stage = f'{name}: letters and numbers'
        QTest.keyClick(keyboard(), Qt.Key.Key_End)
        marker = f' # INPUT_abc123_{index}'
        QTest.keyClicks(keyboard(), marker)
        until(lambda: marker in snapshot()['text'])
        stage = f'{name}: newline and Chinese commit'
        QTest.keyClick(keyboard(), Qt.Key.Key_Return)
        QTest.keyClicks(keyboard(), f'# NEWLINE_456_{index}')
        event = QInputMethodEvent('', [])
        event.setCommitString(' 中文输入789')
        QApplication.sendEvent(keyboard(), event)
        until(lambda: f'NEWLINE_456_{index} 中文输入789' in snapshot()['text'])
        source = snapshot()['text']
        routines = scan_editor(source, Path(editor.path).suffix)
        routine_index = next(i for i, item in enumerate(routines) if item['sourceName'] == name)
        routine = routines[routine_index]
        # AST endLine excludes trailing comment-only input; the next header is
        # the source boundary of the procedure's editable area.
        end = routines[routine_index + 1]['line'] - 1 if routine_index + 1 < len(routines) else len(source.splitlines())
        body = '\n'.join(source.splitlines()[routine['bodyLine'] - 1:end])
        assert marker in body and f'NEWLINE_456_{index} 中文输入789' in body, f'Input went to a different routine: {name}: {source!r}'
        records.append({'routine': name, 'letters_numbers': True, 'newline': True, 'ime_commit': True, 'read_only': False})

    # Reopening a plain file also has to clear every folding/readonly state.
    plain = window.project.root / 'src/keyboard_shortcuts.cpp'
    stage = 'switch to plain C++ file'
    plain.write_text('int keyboard_probe = 123;\n', encoding='utf-8')
    editor.load(plain)
    until(lambda: snapshot()['path'] == str(plain.resolve()))
    window.show_page('code')
    QTest.qWait(80)
    if editor._fallback:
        QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(100, 10))
    else:
        point = json.loads(js("JSON.stringify((()=>{const r=document.querySelector('.view-line').getBoundingClientRect();return {x:r.x+100,y:r.y+r.height/2};})())"))
        QTest.mouseClick(editor.view.focusProxy() or editor.view, Qt.MouseButton.LeftButton, pos=QPoint(round(point['x']), round(point['y'])))
    QTest.qWait(100)
    QTest.keyClick(keyboard(), Qt.Key.Key_End)
    original = snapshot()['text']
    QTest.keyClicks(keyboard(), ' // UNDO_abc123')
    until(lambda: 'UNDO_abc123' in snapshot()['text'])
    typed = snapshot()['text']
    # Monaco creates natural word/space undo groups; exercise each group.
    undo_steps = 0
    stage = 'Ctrl+Z / Ctrl+Y'
    while snapshot()['text'] != original:
        before = snapshot()['text']
        QTest.keyClick(keyboard(), Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        until(lambda: snapshot()['text'] != before)
        undo_steps += 1
        assert undo_steps <= len(' // UNDO_abc123'), 'Ctrl+Z did not restore the original source'
    for _ in range(undo_steps):
        before = snapshot()['text']
        QTest.keyClick(keyboard(), Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        until(lambda: snapshot()['text'] != before)
    assert snapshot()['text'] == typed, 'Ctrl+Y did not restore typed content'

    clipboard = app.clipboard()
    previous = QMimeData()
    current = clipboard.mimeData()
    if current is not None:
        for mime in current.formats():
            previous.setData(mime, current.data(mime))
    try:
        stage = 'Ctrl+A / Ctrl+C'
        QTest.keyClick(keyboard(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(keyboard(), Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        until(lambda: clipboard.text().replace('\r\n', '\n') == typed)
        stage = 'Ctrl+X / Ctrl+V'
        QTest.keyClick(keyboard(), Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        until(lambda: snapshot()['text'] == '')
        QTest.keyClick(keyboard(), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        until(lambda: snapshot()['text'] == typed)
    finally:
        if previous.hasFormat('text/plain') or previous.formats():
            clipboard.setMimeData(previous)
        else:
            clipboard.clear()
    QTest.keyClick(keyboard(), Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    stage = 'Ctrl+S'
    until(lambda: plain.read_text(encoding='utf-8') == typed)
    for key, replace in [(Qt.Key.Key_F, False), (Qt.Key.Key_H, True)]:
        stage = f'Ctrl+{"H" if replace else "F"}: open and search'
        QTest.keyClick(keyboard(), key, Qt.KeyboardModifier.ControlModifier)
        if editor._fallback:
            until(lambda: hasattr(editor, 'find_dialog') and editor.find_dialog.isVisible())
            assert editor.find_dialog.replacement.isVisible() == replace
        else:
            until(lambda: js("document.querySelector('.find-widget')?.classList.contains('visible')"))
            if replace:
                assert js("document.querySelector('.find-widget .replace-part').getBoundingClientRect().height>0")
            # The widget slides down for 200 ms; clicking its initial geometry
            # can hit outside the view before the visible animation completes.
            QTest.qWait(250)
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(app.focusWidget(), 'UNDO_abc123')
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Return)
        until(lambda: snapshot()['selectedText'] == 'UNDO_abc123')
        if replace:
            stage = 'Ctrl+H: focus replacement'
            if editor._fallback:
                dialog = editor.find_dialog
                QTest.mouseClick(dialog.replacement, Qt.MouseButton.LeftButton)
            else:
                point = json.loads(js("JSON.stringify((()=>{const r=document.querySelector('.find-widget .replace-part textarea').getBoundingClientRect();return {x:r.x+30,y:r.y+r.height/2};})())"))
                QTest.mouseClick(editor.view.focusProxy() or editor.view, Qt.MouseButton.LeftButton, pos=QPoint(round(point['x']), round(point['y'])))
                try:
                    until(lambda: js("Boolean(document.activeElement.closest('.replace-part'))"))
                except AssertionError as exc:
                    details = js("JSON.stringify({active:document.activeElement.tagName,classes:document.activeElement.className,rect:[...document.querySelectorAll('.find-widget textarea')].map(node=>({value:node.value,x:node.getBoundingClientRect().x,y:node.getBoundingClientRect().y,w:node.getBoundingClientRect().width,h:node.getBoundingClientRect().height}))})")
                    raise AssertionError(f'Replace field focus failed: {point!r}; {details}') from exc
            QTest.keyClick(app.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(app.focusWidget(), 'REPLACED_456')
            stage = 'Ctrl+H: replace all'
            if editor._fallback:
                QTest.mouseClick(dialog.replace_buttons[1], Qt.MouseButton.LeftButton)
            else:
                point = json.loads(js("JSON.stringify((()=>{const r=document.querySelector('.find-widget .codicon-find-replace-all').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})())"))
                QTest.mouseClick(editor.view.focusProxy() or editor.view, Qt.MouseButton.LeftButton, pos=QPoint(round(point['x']), round(point['y'])))
            try:
                until(lambda: snapshot()['text'] == typed.replace('UNDO_abc123', 'REPLACED_456'))
            except AssertionError as exc:
                details = js("JSON.stringify({active:document.activeElement.outerHTML,inputs:[...document.querySelectorAll('.find-widget textarea')].map(node=>({value:node.value,classes:node.className}))})") if not editor._fallback else ''
                raise AssertionError(f'Replace did not update source: {snapshot()!r}; {details}') from exc
        stage = 'Escape: close find widget'
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Escape)
        if editor._fallback:
            until(lambda: not editor.find_dialog.isVisible())
        else:
            until(lambda: not js("document.querySelector('.find-widget')?.classList.contains('visible')"))
        editor.focus_editor()
        QTest.qWait(50)
    editor.load(window.project.entry_path)
    stage = 'reopen and save entry source'
    until(lambda: snapshot()['path'] == str(window.project.entry_path.resolve()))
    assert all(f'INPUT_abc123_{index}' in snapshot()['text'] for index in range(len(names)))
    editor.capture(lambda: editor.save())
    until(lambda: all(f'INPUT_abc123_{index}' in window.project.entry_path.read_text(encoding='utf-8') for index in range(len(names))))
    return {'ok': True, 'routines': records, 'shortcuts': {key: True for key in ['Ctrl+A', 'Ctrl+C', 'Ctrl+X', 'Ctrl+V', 'Ctrl+Z', 'Ctrl+Y', 'Ctrl+S', 'Ctrl+F', 'Ctrl+H']}, 'saved_reopened': True, 'source': str(window.project.entry_path)}
