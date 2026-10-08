# Architecture and Delivery Route

## Directory Boundaries

| Path | Ownership |
| --- | --- |
| `src/pcide` | Generic Python IDE, core services, desktop UI and runtime contracts |
| `src/hosts` | Native/.NET/Android host sources |
| `tests` | Core, subprocess, Qt UI, Monaco and build verification |
| `docs` | Memory, index, contracts, detailed evidence |
| `examples` | Controlled plugin/form/flow source examples |
| `third_party/monaco` | Microsoft Monaco 0.52.2 AMD distribution and MIT license |
| `downloads` | Downloaded archives/wheels only |
| `sdk` | Compiler and .NET SDK excluded from customer delivery; IDE carries TypeScript compiler assets only |
| `runtime/dev` | Isolated IDE development environment |
| `runtime/training` | Optional vision/training packages |
| `runtime/modules` | Prebuilt runtime modules, selected by project capability |
| `projects` | User script projects, UI descriptions and selected resources |
| `cache` | Bytecode, compilation, logs, test temp, session traces, training outputs |
| `build` | Verified standalone IDE and project EXE artifacts |

## Call Chains

1. Launch: `start_ide` -> `main.main` -> `Paths` + `Project.open/create` -> Qt `MainWindow`.
2. Editor: Qt WebEngine -> offline Monaco models -> Qt WebChannel -> source save/navigation/breakpoints.
3. Design: toolbox -> graphics scene controls -> model validation -> form JSON; property/event/tree selection uses the same control ID.
4. Run/debug: toolbar -> managed script subprocess -> Python worker (`bdb`) or Node worker -> session-bound JSON messages -> console/variables/stack/runtime form.
5. Events: runtime form event -> current script process -> handler -> console and typed control updates. Preview shares form serialization.
6. Flow: graphics nodes + serialized edges -> validated executor -> log/mock/automation/plugin operations with cancellation/deadline.
7. Plugins: registry -> manifest/architecture/dependency/permission checks -> separate host -> C ABI/Python/.NET/Android request -> structured result; unload ends the host process.
8. Vision: dataset/annotation panel -> YOLO label IO -> optional external training worker; models/caches/logs outside source; mocks visibly marked.
9. Build: project inputs + relative-path hashes + runtime ABI fingerprint -> Python pyc or fixed-Node Bytenode jsc cache -> prebuilt basic/vision/node runtime -> PyInstaller archive assembly or diagnostic directory -> payload hash/forbidden-file scan -> execute verification.
10. DEX: bounded binary index -> PC metadata; execution -> explicit ADB-forwarded WebSocket endpoint -> Android ART/ClassLoader. Disconnection fails; no local DLL fallback.

## Reuse Decisions

- Read-only inspected: legacy `ui_designer.py`, `property_editor.py`, `monaco_editor/{widget,bridge,host.html}`, `yolo_tool/label_io.py`, `console_panel.py`, `project_explorer.py`, `debugger.py`, packaging cache contracts.
- Reuse Monaco distribution verbatim with license. Qt bridge/model lifecycle, toolbox/property/event layout, YOLO normalized label format and frozen runtime cache design are extracted/adapted without cloud/account/device business modules.
- Tk bootstrap was a disposable prototype. It is replaced by the Qt entry because a text fallback labeled Monaco and a Python-dependent launcher do not meet acceptance.

## Iterations and Gates

| Stage | Gate |
| --- | --- |
| 1. Desktop/project/editor | Qt startup and actual offline Monaco readiness, new/open/save projects |
| 2. Form/events | drag, resize, copy, align, grid, load/save, event execution, bidirectional navigation |
| 3. Runtime/debug/flow | Python + JS + TS execution, stop, errors, timeout, breakpoints/stack/locals, replay and mocks |
| 4. Extension hosts | controlled C ABI + Python plugin, .NET context host, DEX browse/bridge, crash/reload cleanup |
| 5. Vision | dataset/label IO, real optional inference/training adapter, logs/test/export/model inventory |
| 6. Incremental EXE | cached runtime, selected project bytecode/resources, source-free payload scan, portable EXE execution, cache hit/invalidation |

Hardware, Android physical device, GPU training, code signing and another Windows machine are separately reported verification boundaries.
