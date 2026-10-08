# PC Modules

| Module | Entry / Direct Dependencies | State |
| --- | --- | --- |
| Project | `Project.create/open/load_form/save_form` -> JSON schema, atomic IO | Implemented and validated |
| Editor | `ui/editor.py` -> `pcide://editor` -> offline Monaco 0.52.2/WebChannel | Actual Monaco frozen and UI-tested |
| Designer | graphics scene -> form model -> property/events/tree | Drag, resize, copy, undo/redo, save/load and event preview validated |
| Script/debug | `core/runner.py` -> owned console child -> Python bdb or Node inspector | Python/JS/TS run, debug, stop, timeout, error and pipe lifecycle validated |
| Flow | node graph -> `FlowRunner` -> bounded operations | Dependency, timeout, cancellation and local operations validated |
| Plugins | manifest -> `PluginRegistry` -> isolated Python/C/.NET/DEX hosts | Permission, crash, timeout, reload and frozen Python/C/.NET paths validated; Android ART remains device-gated |
| Vision | dataset/labels -> `VisionWorkbench` -> RapidOCR/OpenCV/optional training | Real OCR and ONNX execution/export validated; accuracy remains outside synthetic gate |
| Build | runtime fingerprint -> `.pyc`/`.jsc` cache -> fixed runtime -> payload archive | Directory/standalone incremental builds, source scan and portable customer EXEs validated |
| Windows/data contracts | `Project.window_paths/load_window/rename_path/delete_path` -> form schema -> `RuntimeWindowManager`; window menu/context menu -> new/open/rename/delete form -> designer view; project-tree file/dir actions -> validated filesystem mutation; `runtime_api.ui.open/close/set` -> window/control routing; `.pcide/data.json` -> `core.data` -> language generators | Independent form files, discoverable new-window entry, safe project-tree file operations with protected required paths, designer switching without opening source code, size/layout constraints, runtime open/close/update/resize/close-event lifecycle, recursive project tree, four variable scopes, constants, DLL/API metadata, and Chinese label/English ID mapping are source/Qt-tested |

Final command evidence and limits are recorded in `docs/archive/verification.md` and the JSON reports under `cache/logs`.

- 2026-10-07：用户界面、提示、弹窗和模板示例已中文化；冻结构建已重新生成并通过发布验收。
| IDE layout/completion | `main.py` -> workspace tabs, project tree/routines, support-library/property tabs, environment dialog; `ui/editor.py` -> project symbols -> Monaco completion/signature/folding | Implemented; source and frozen smoke/UI smoke validated |
| IDE layout closeout | `main.py` -> left support/property/data tabs + project/routine navigation, center designer/code workspace, right toolbox, bottom output; `properties.py`/`designer.py`/`form_runtime.py` -> Frame/Tabs properties and runtime rendering; `editor.py`/`editor.html` -> completion/signature/folding | Layout aligned to the supplied Yi-language reference; 40 source tests and frozen/delivery smoke gates passed |
| IDE editor theme | `ui/editor.html` -> Monaco `pcide-light` theme and editor surface | Fixed invalid color literals that caused Monaco theme variables to fall back to pure red; verified white editor surface and Yi-style line numbers/highlight in source capture and frozen/delivery smoke |
| Control catalog/property sync | `core/control_catalog.py` -> `project.py` schema validation -> `designer.py` toolbox -> `properties.py` -> `form_runtime.py` | 27 control types grouped into basic/data/container/advanced categories; selected-control properties, immediate commit on focus/Enter/combo changes, and runtime/design preview synchronization validated |
