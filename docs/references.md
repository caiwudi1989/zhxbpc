# References and Licenses

## Primary References

- [Qt Widgets menus example](https://doc.qt.io/qt-6/qtwidgets-mainwindows-menus-example.html): shared `QAction` design for main menus and context menus; used for project-tree operations.
- [Qt QFile](https://doc.qt.io/qt-6/qfile.html): rename/delete behavior and failure handling used by the project file-management contract.
- [精易 eIDE visual library](https://github.com/kuodafu/eide): public EasyLanguage IDE reference reviewed for code-tab/window-title synchronization and extension points; no source was copied.
- [Microsoft Monaco Editor](https://github.com/microsoft/monaco-editor): offline editor 0.52.2; `third_party/monaco/LICENSE.txt` (MIT).
- [Qt custom URL schemes](https://doc.qt.io/qt-6.8/qwebengineurlscheme.html): `pcide://editor` serves reviewed local assets and worker scripts without a local HTTP server.
- [Qt WebEngine JavaScript](https://doc.qt.io/qt-6.8/qwebenginepage.html): asynchronous JSON snapshot bridge; page lifetime is owned by the editor widget.
- [PyInstaller advanced topics](https://pyinstaller.org/en/stable/advanced-topics.html): pinned 6.16.0 CArchive reader/writer used for incremental single EXE assembly.
- [Bytenode](https://github.com/bytenode/bytenode): pinned 1.7.0, SHA512-verified npm package; V8 bytecode requires the bundled Node 24.19.0. License in `third_party/bytenode/LICENSE` (MIT). Source reflection and arbitrary third party packages are not guaranteed by bytecode compilation.
- [Microsoft .NET plugin tutorial](https://learn.microsoft.com/dotnet/core/tutorials/creating-app-with-plugin-support): isolated collectible AssemblyLoadContext and dependency resolver.
- [Android DEX format](https://source.android.com/docs/core/runtime/dex-format): memory-mapped class index; execution belongs to Android ART.
- [Java-WebSocket](https://github.com/TooTallNate/Java-WebSocket): pinned 1.6.0, Maven SHA1-verified download, MIT; SLF4J 2.0.16 (MIT).
- [RapidOCR](https://github.com/RapidAI/RapidOCR): installed `rapidocr-onnxruntime` 1.4.4, Apache-2.0; ONNX Runtime MIT and packaged OCR models require their upstream notices.
- [Ultralytics settings](https://docs.ultralytics.com/usage/cfg): real CPU training/export in the separate `runtime/training` environment. Installed 8.4.171 is AGPL-3.0 or commercial; the optional training environment is not included in customer EXEs. Commercial distribution requires following the applicable license.

## Runtime Notices

- PySide6 / Qt use LGPL-3.0, GPL-3.0 or commercial terms. Frozen distributions retain shared libraries and upstream notices; relinking and other LGPL obligations still apply.
- Python uses PSF; Node includes Node/V8 third party licenses; OpenCV Apache-2.0; Pillow HPND; NumPy BSD; PyYAML MIT; pyserial BSD; pywin32 PSF; comtypes MIT; hidapi package and underlying HIDAPI notices must be retained.
- PyInstaller uses GPL with bootloader exception. Its build libraries are present in the IDE for archive assembly; the exception does not replace obligations for all incorporated dependencies.
- `tools/collect_notices.py` records installed package metadata and copies available license files into `docs/licenses`. No code signing or license counsel review has been performed.

## Legacy Provenance

- Read-only input root: `D:\zhxbapp`; directly reviewed generic PC designer/editor/YOLO label contracts only. No user/account/game/cloud modules are imported.
- The independent tree, environments, SDK copies and delivery live in `F:\PC端软件`. Existing legacy edits were preserved. Detailed provenance and validation are in `architecture.md` and `archive/verification.md`.
