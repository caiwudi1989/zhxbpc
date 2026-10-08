# Verification Evidence

## Final local Windows gate — 2026-10-07

All commands below ran from `F:\PC端软件` with the project development environment under `runtime/dev`; disposable workspaces were kept under `cache` and removed by the release gate.

- `& .\run_tests.ps1`: exit `0`; 29 tests passed in 83.304 seconds. This covers project/form/flow validation, Python/JS/TS run/debug and events, bounded output, timeouts/cancellation, plugin hosts, automation APIs, DEX fixtures, real Qt/Monaco UI operations, TypeScript worker diagnostic `2322`, and frozen build tests.
- `runtime/dev/Scripts/python.exe -B tools/freeze_runtime.py --profile all`: exit `0`; refreshed `runtime/prebuilt/project-runtime`, `project-runtime-vision`, and `project-runtime-node`. Evidence: `cache/logs/freeze-runtime-final2.log`.
- `runtime/dev/Scripts/python.exe -B tools/freeze_ide.py`: exit `0`; produced `build/PCIDE/PCIDE.exe`. Evidence: `cache/logs/freeze-ide-final2.log`.
- `runtime/dev/Scripts/python.exe -B tools/deliver_examples.py`: exit `0`; `HelloAutomation`, `JavaScriptDemo`, and `TypeScriptDemo` standalone EXEs ran with exit `0`; build and cached-build timings are in `cache/logs/delivery.json`.
- `runtime/dev/Scripts/python.exe -B tools/verify_release.py`: exit `0`; `cache/logs/frozen-release.json` has `ok: true`, `temporary_workspace_removed: true`, and an isolated workspace with no development Python, SDK, or source tree. The gate built and ran three language examples, a real RapidOCR/OpenCV ONNX project, and Python/C/.NET plugin project; checked payload members for source/SDK leakage; ran a frozen Monaco UI smoke with screenshot `cache/logs/frozen-ide.png`; and verified the customer EXE in an EXE-only directory.
- The same report records frozen worker lifecycle cases: native event with delayed NumPy import, cancellation, stdin disconnect, invalid command, partial-command forced termination (`alive_before_termination: true`), and an explicit crash. Each child was reaped; normal cancellation/disconnect returned `130`, invalid command returned `1`, timeout termination was forced by the owned Windows job, and crash returned `23`.
- `cache/logs/vision-verification.json`: real RapidOCR recognized `PCIDE 2026 TEST` at approximately `0.982` confidence; synthetic CPU YOLO training/export produced a real ONNX tensor `[1, 5, 8400]`. The record explicitly limits this to execution/export evidence, not recognition accuracy.

## Initial Bootstrap

- 2026-10-07: `compileall` returned 0; it created source-adjacent bytecode, which will be removed and all subsequent compilation redirected into `cache/bytecode`.
- `python -B -m unittest discover -s tests -v`: 7 cases; 6 passed/1 plugin ID validation error. Repaired legal underscore IDs and system DLL references.
- A .NET Framework launcher compilation probe ran with exit 0. This did not establish standalone runtime delivery and is not a release artifact.

## Unverified boundaries

- No Android device/ADB endpoint was available, so Android ART/DexClassLoader execution remains unverified; PC WebSocket fixture tests cover request ownership and disconnect errors only.
- Serial/HID tests cover loopback and device inventory, not hardware transmit/receive acceptance. GPU training, code signing, malicious-code OS sandboxing, and another clean Windows machine were not tested.

## 2026-10-09 最终收口验证

- `& .\run_tests.ps1 -q`: exit `0`; 56 tests passed, 1 environment-dependent test skipped, total `97.211` seconds (`cache/logs/full-tests-20261009-final.txt`). This includes editor fallback operations, project lifecycle/menu contracts, plugin install/repeat-install/uninstall/upgrade/rollback, Python/JavaScript/TypeScript/中文源码, build cache, UI, flow, vision and child-host lifecycle gates.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile node`: exit `0`, `60.093` seconds. The basic/vision/node manifests were compared against the current source fingerprints and all matched.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`, `62.047` seconds; final delivery is `build\PCIDE\PCIDE.exe` with the complete sibling `build\PCIDE\_internal` directory.
- Final frozen smoke commands all exit `0`: `--smoke`, `--ui-smoke --editor native`, and default `--ui-smoke`. Reports are `cache/logs/frozen-ide-smoke-r2.json`, `cache/logs/frozen-ui-native-r2.json`, and `cache/logs/frozen-ui-auto-r2.json`; the default restricted-token backend is `native` with `editor_ready: true`, avoiding Chromium/Mojo popups. Screenshots are `cache/logs/frozen-ui-native-r2.png` and `cache/logs/frozen-ui-auto-r2.png`.
- `runtime\dev\Scripts\python.exe -B tools\deliver_examples.py`: exit `0`; standalone customer EXEs for HelloAutomation, JavaScriptDemo, and TypeScriptDemo ran without the development Python. Latest first/cached timings are respectively `3.231/1.133`, `1.689/1.390`, and `1.587/1.393` seconds. An isolated measurement after the packaging optimization recorded first/incremental/unchanged as `2.398/2.226/1.114` seconds.
- `runtime\dev\Scripts\python.exe -B tools\verify_release.py`: exit `0` in `72.685` seconds; `cache/logs/frozen-release.json` reports `ok: true`, `temporary_workspace_removed: true`, five isolated language/vision/plugin projects, source/SDK-free customer payloads, and reaped native/cancel/disconnect/invalid/timeout/crash workers. The UI evidence records `ui_editor: native`, `ui_monaco: false` for this restricted host; supported desktops may use Monaco.
- Source entry smoke (`src/pcide/main.py --smoke` and `--ui-smoke --editor native`) exited `0`; an isolated `.zhxb` source run and standalone customer EXE also exited `0` (`cache/logs/zhxb-source-smoke-final.txt`, `cache/logs/zhxb-exe-smoke-final-r2.txt`).
- The final native UI smoke was additionally attempted through the Computer Use bridge, but this session exposed browser controls only and returned no native-app inventory. Therefore the verifiable UI evidence is the executable's own screenshot-backed Qt smoke, not a claim of external accessibility automation.

## 2026-10-07 中文化收口
- 修改范围：主界面、运行窗口、视觉面板、编辑器提示、模板与示例项目。
- 验证：run_tests.ps1 29 项通过；verify_release.py 输出 ok=true。

## 2026-10-08 窗口与程序数据收口

- `& .\run_tests.ps1`: exit `0`; 32 tests passed in 84.850 seconds. The added `tests/test_contracts.py` covers independent window files, bounded layout metadata, all variable scopes/constants, DLL/API metadata and code generation, and Chinese label/English ID round trips. Existing Qt/Monaco, runtime, plugin, DEX and build gates also passed.
- `runtime/dev/Scripts/python.exe -B tools/freeze_runtime.py --profile all`: exit `0`; the three prebuilt runtime profiles were refreshed after the final source changes. IDE EXE was not rebuilt in this closeout.
- Source-only boundaries: no physical Android device, HID hardware, GPU training, signing, or clean-machine deployment was claimed by these tests.

## 2026-10-08 二轮收口复核

- `& .\run_tests.ps1`: exit `0`; 34 tests passed in 85.402 seconds. This includes typed Python/JavaScript/TypeScript literal generation, fixed-width-only and fixed-height-only Qt constraints, runtime window aliases and multi-window open/close lifecycle, plus the existing build, worker, plugin, DEX, vision and Monaco gates.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed `runtime/prebuilt/project-runtime`, `project-runtime-vision`, and `project-runtime-node` after the runtime window API and generator fixes.
- `runtime\node\node.exe --check src\pcide\core\worker_js.cjs` and `worker_bytecode.cjs`: exit `0`; Python sources and tests passed `compileall` before disposable `__pycache__` cleanup.
- The source closeout itself did not rebuild the IDE EXE; it was rebuilt and checked in the following packaging step. Android ART/device, HID hardware, GPU training, code signing, and another clean Windows machine remain unverified boundaries.

## 2026-10-08 IDE EXE 重打包

- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the refreshed runtime profiles and current source.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-repack-smoke.json`: report confirms `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`, and the expected UI update.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-repack-ui.png --report cache\logs\ide-repack-ui-smoke.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 窗口双击设计视图修复

- `& .\run_tests.ps1`: exit `0`; 35 tests passed in 96.884 seconds. The added Qt regression covers project-tree double-click of `main.form.json`, confirms the design view is selected, and confirms the source editor is not the active pane.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the fix.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-window-fix-smoke.json`: exit `0`; frozen script, flow, UI update, and Monaco asset checks passed.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-window-fix-ui.png --report cache\logs\ide-window-fix-ui.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 新建窗口入口修复

- `& .\run_tests.ps1`: exit `0`; 36 tests passed in 90.535 seconds. The added Qt coverage verifies the window menu/context flow creates or selects a form and leaves the designer view active.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the discoverable new-window actions.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-new-window-smoke.json`: exit `0`; frozen script, flow, UI update, and Monaco asset checks passed.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-new-window-ui.png --report cache\logs\ide-new-window-ui.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 全面项目管理与窗口事件收口

- `& .\run_tests.ps1 -q`: exit `0`; 39 tests passed in `cache/logs/tests-full-closeout.log`. Added coverage for safe project file/ directory rename/delete, protected project paths, window menu rename/delete entries, and runtime `resize`/`close` events.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed all three prebuilt runtime profiles after the project-management and event-contract changes.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` at 2026-10-08 02:03.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-closeout-smoke2.json`: exit `0`; report confirms `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`, and UI event update.
- `build\PCIDE\PCIDE.exe --ui-smoke --report cache\logs\ide-closeout-ui2.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.
- Reviewed [Qt Widgets menus](https://doc.qt.io/qt-6/qtwidgets-mainwindows-menus-example.html), [Qt QFile](https://doc.qt.io/qt-6/qfile.html), and the public [精易 eIDE repository](https://github.com/kuodafu/eide); only interaction patterns were used, with no source copied.

## 2026-10-08 交付目录运行时修复

- Root cause: the first `outputs\PCIDE.exe` copy did not include its sibling `_internal` directory, so PyInstaller could not load `python312.dll`.
- Copied the complete `build\PCIDE\_internal` tree beside `outputs\PCIDE.exe`.
- From the actual outputs directory, `PCIDE.exe --smoke` exited `0`; `PCIDE.exe --ui-smoke` exited `0`; both reports resolve resources from `outputs\_internal`.
## 2026-10-08 易语言布局与补全收口

- 修改：中央工作区切换为“界面设计/代码工作区”；左侧项目树下增加子程序导航；右侧增加“支持库/属性”页；“环境 -> 项目环境”保存语言、Python 和 Node.js 路径到项目清单；支持库双击插入命令。
- 编辑器：Monaco 使用项目变量、常量、API、窗口控件与事件生成补全；支持 Ctrl+Space、`.`/`:`/中文句号触发、参数签名提示、代码片段、折叠和格式化入口；数据来源为当前项目 `.pcide/data.json` 与窗口表单。
- 验证：`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；定向窗口/Monaco 测试 3 项退出 `0`；三个 runtime profile 指纹有效；`tools/freeze_ide.py` 退出 `0`；冻结版 smoke/UI smoke 报告 `cache/logs/ide-layout-smoke.json`、`cache/logs/ide-layout-ui.json` 均确认 `frozen: true`、Monaco/脚本/流程通过；交付目录 `outputs` 中 EXE-only smoke/UI smoke 均退出 `0`。
- 限制：未宣称 Android 真机、HID 硬件、GPU、代码签名或另一台干净 Windows 机器验证；vision 预编译曾出现超时，随后单独重跑已成功刷新。
## 2026-10-08 易语言布局最终复核

- 布局：左侧支持库、属性/窗口设置、变量常量分组夹，下面是项目和子程序导航；中间是界面设计与代码工作区；右侧是控件箱；底部是输出/调试信息；设计器支持双击进入代码工作区，代码工作区标签在下方显示并可关闭或右键关闭。
- 控件：分组框和标签页已加入控件箱；属性面板支持分组页名称、当前页、边框样式；设计器和运行时均绘制对应外观。
- 验证：`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；`tools/freeze_ide.py` 退出 `0`；冻结版 `--smoke`、`--ui-smoke` 退出 `0`；交付目录 `outputs` 中 `PCIDE.exe` 与同级 `_internal` 的 EXE-only smoke/UI smoke 均退出 `0`。截图：`outputs\PCIDE-layout.png`。
- 边界：未宣称 Android 真机、HID 硬件、GPU、代码签名或另一台干净 Windows 机器验证。
## 2026-10-08 代码编辑区红底修复

- 根因：Monaco 主题的颜色值缺少 `#` 前缀，主题变量被解析为无效值并回退为 `#ff0000`，导致当前行、边距和概览区域出现红色。
- 修复：`src/pcide/ui/editor.html` 为语法色、编辑区、当前行、行号、边距、概览尺和滚动条全部使用合法颜色值，并增加宿主层白底保护样式。
- 验证：源代码编辑器截图 `cache/logs/ide-editor-theme-code.png` 已恢复白底和正常配色；`test_monaco_edit_save_models_navigation` 退出 `0`；`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；`tools/freeze_ide.py` 退出 `0`；冻结版 smoke/UI smoke 与 `outputs` 目录 EXE-only smoke/UI smoke 均退出 `0`。交付新增截图 `outputs\PCIDE-code-layout.png`。
## 2026-10-08 控件分类与属性实时回写

- `& .\run_tests.ps1 -q`: exit `0`; 40 tests passed in 96.277 seconds after wiring the shared control catalog and runtime property application.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed `project-runtime`, `project-runtime-vision`, and `project-runtime-node` after the control/property contract changes.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build\PCIDE\PCIDE.exe` with the categorized toolbox, left docking tabs, and reactive property panel.
- Frozen reports: `cache\logs\ide-window-chrome-smoke.json` has `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`; `cache\logs\ide-window-chrome-ui.json` has `qt: true`, `monaco: true`, `frozen: true`.
- Delivery reports: `outputs\smoke-final.json` has `script_exit: 0`, `flow: true`, `monaco_assets: true`; `outputs\ui-smoke-final.json` has `qt: true`, `monaco: true`, `frozen: true`; `outputs\PCIDE.exe` is delivered beside `outputs\_internal`.
- Boundaries unchanged: Android ART/device, HID hardware, GPU training, code signing, and another clean Windows machine remain unverified.
- 最终回归补充：`& .\run_tests.ps1 -q` exit `0`，41 tests passed in 90.636 seconds；新增用例覆盖控件箱四组、设计区选中后属性页切换、宽度与文本焦点提交。
- 交付目录复核：从 `outputs` 启动 `PCIDE.exe`，`--smoke` 和 `--ui-smoke` 均由 `Start-Process -Wait` 返回 exit `0`，报告资源路径均为 `outputs\\_internal`。

## 2026-10-08 Qt WebEngine 弹窗收口

- 根因：在当前受限 Windows token 中，Qt WebEngine/Chromium 创建 Mojo 命名管道返回 `拒绝访问 (0x5)`，进程在页面初始化前触发 `FATAL:named-platform-channel-pipe` 弹窗。
- 修复：`src/pcide/ui/editor.py` 在构造 `QWebEngineProfile` 之前识别受限宿主并切换到原生 `QPlainTextEdit`；`--editor native` 可显式选择回退，`--editor monaco` 仅在确认宿主支持 WebEngine 时启用 Monaco。
- 源码验证：`src/pcide/main.py --ui-smoke --editor native` 退出 `0`，报告 `editor_ready: true`；`tests.test_contracts` 与 `tests.test_ui` 共 23 项定向测试退出 `0`。
- 冻结验证：`build\\PCIDE\\PCIDE.exe --smoke`、`--ui-smoke --editor native` 和默认 `--ui-smoke` 均退出 `0`；冻结报告分别为 `cache/logs/frozen-closeout-smoke.json`、`cache/logs/frozen-closeout-ui.json` 和 `cache/logs/frozen-closeout-ui-auto.json`。
- 当前环境的完整门禁仍受屏幕抓取失败与 PyInstaller 单文件 `_MEI` 目录 ACL 限制；这些是测试宿主限制，不是源码启动错误。

## 2026-10-09 Monaco 空白回归修复

- 用户截图中的实际错误为 `Uncaught SyntaxError: Invalid regular expression`：`src/pcide/ui/editor.html` Python 投影正则使用 `\#`，在带 `u` 标志的 JavaScript 正则中属于非法 identity escape，页面脚本因此在创建 Monaco 模型前终止。
- 修复为未转义的 `#`，并加入 `tests.test_ui.UiTests.test_editor_python_projection_regex_is_unicode_safe`，防止该错误回归。
- `runtime/node/node.exe` 对源码和冻结版内联脚本均返回语法检查成功；源码 `--smoke`、冻结版 `--smoke`、源码/冻结版 `--ui-smoke --editor native` 均返回 exit `0`，报告中的 `editor_ready` 为 `true`。
- 已重建交付文件：`build\PCIDE\PCIDE.exe` 与同级完整 `build\PCIDE\_internal`。在当前受限 token 中强制 `--editor monaco` 仍会触发 Qt Chromium Mojo 权限错误，因此默认后端继续自动回退原生编辑器；这与本次 JavaScript 正则修复是两个独立问题。

## 2026-10-09 子程序信息区重叠修复

- 根因：`renderRoutines()` 用零基源码数组索引作为 Monaco 一基 `afterLineNumber`，元数据 view zone 被放在子程序声明前；固定高度又偏小，表格可能继续压到代码行。
- 修复：`src/pcide/ui/editor.html` 使用 `afterLineNumber:index+1`，并为表格边框、内边距和参数行预留高度；`tests.test_ui.UiTests.test_editor_routine_zone_is_after_declaration` 固定该布局契约。
- `runtime/node/node.exe` 源码内联脚本语法检查成功；冻结版 `--smoke` 与 `--ui-smoke --editor native` 均 exit `0`，`editor_ready: true`。当前受限 token 仍不能用真实 Chromium 做视觉截图，故 Monaco 视觉位置以代码契约和可用桌面环境验收为准。
