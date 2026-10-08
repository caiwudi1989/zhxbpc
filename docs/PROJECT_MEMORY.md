# Project Memory

- Date: 2026-10-07. Root: `F:\PC端软件`. The delivered target is a generic Windows Qt IDE with offline Monaco, Python/JavaScript/TypeScript execution and debugging, form/flow design, isolated extensions, vision adapters, DEX transport, and incremental standalone EXE packaging.
- Entry chain: `start_ide.ps1` / `start_ide.cmd` -> `src/pcide/main.py` -> `Paths` + `Project` -> Qt `MainWindow`. Frozen IDE: `build/PCIDE/PCIDE.exe`.
- Runtime chain: `src/pcide/core/runner.py` -> prebuilt console runtime -> Python `worker.py` or Node worker. Windows command input uses bounded `PeekNamedPipe` polling; one-shot runs do not create a blocking stdin thread, keep-alive/debug readers start only after safe initialization or at a debugger pause.
- Build chain: `core/builder.py` hashes project inputs and runtime profile, emits Python `.pyc` or Bytenode `.jsc`, assembles a fixed PyInstaller runtime, scans `payload`, and preserves old artifacts on failure. Profiles are `runtime/prebuilt/project-runtime*`.
- Extension/vision chain: `core/plugins.py` -> child hosts under `runtime/modules`; `core/vision.py` -> RapidOCR/ONNX/OpenCV. The self-contained .NET host path is propagated through `PCIDE_DOTNET_HOST` for frozen IDE child processes.
- Final evidence: `cache/logs/tests-full-release.log` (previous 29-test release gate, exit 0), `cache/logs/frozen-release.json` (isolated frozen IDE/customer/worker gate, `ok: true`), `cache/logs/delivery.json` (three example EXEs), `cache/logs/vision-verification.json` (real OCR and CPU ONNX execution), `cache/logs/freeze-runtime-final2.log`, and `cache/logs/freeze-ide-final2.log`. The 2026-10-08 source closeout reran `run_tests.ps1`: 34 tests, exit 0; runtime profiles were refreshed without rebuilding the IDE EXE.
- Verified locally: final frozen IDE startup, actual Monaco readiness, three language execution/events, breakpoints/step/locals/stack, timeout/cancel/error/disconnect/recovery, real OCR/ONNX, Python/C/.NET plugin execution, source-free payload scan, portable customer EXEs, and Windows child-process reaping.
- Boundaries: Android ART/device execution, serial/HID hardware I/O, GPU training, code signing, malicious-code OS sandboxing, and another clean Windows machine remain unverified. Synthetic YOLO training/inference proves execution/export only, not recognition quality. Bytecode/Bytenode is not encryption.

- 2026-10-07：完成 IDE 用户可见文案中文化，覆盖主界面、运行窗口、视觉面板、编辑器提示、默认模板及示例项目；29 项测试通过，冻结 IDE 与发布验收 ok。
- 2026-10-08：补齐独立窗口表单与运行时窗口管理；表单支持固定/最小/最大尺寸、最大化/最小化、锚点、停靠和自动填充；项目树递归显示任意扩展。新增 `core/data.py` 数据/API 合同（全局/窗口/模块/局部变量、常量、DLL/API 参数/返回值/调用约定/权限/依赖）及 Python/JavaScript/TypeScript 生成，`core/i18n.py` 提供中文显示名与英文内部 ID 双向映射；新增 `tests/test_contracts.py`。
- 2026-10-08 二轮收口：修正声明类型与生成字面量不一致、单维固定尺寸未锁定、固定尺寸越界校验；补齐 Python/JS/TS `ui.open/ui.close` 到运行时多窗口路由，并增加多窗口生命周期与生成代码语法测试。`run_tests.ps1` 34 项通过；三个 runtime profile 已刷新；随后重新冻结 IDE EXE 并通过冻结版 smoke/UI smoke。
- 2026-10-08 窗口设计视图修复：项目树双击 `.form.json` 统一走窗口切换并选中设计视图，源码文件才进入代码页；新增 UI 回归测试。`run_tests.ps1` 35 项通过，IDE EXE 已重新冻结并通过冻结版 smoke/UI smoke。
- 2026-10-08 新建窗口入口修复：窗口菜单和“界面”目录右键菜单均提供“新建窗口”，创建后直接加载新窗口设计视图；`run_tests.ps1` 36 项通过，IDE EXE 再次冻结并通过冻结版 smoke/UI smoke。
- 2026-10-08 全面项目树收口：统一支持文件/目录/窗口的新建、导入、打开、重命名、删除；项目根、主窗口、入口脚本、主流程和 `.pcide/project.json` 受保护；重命名/删除后同步当前设计窗口、源码编辑器和窗口菜单；新增窗口 `resize/close` 事件；37 项源测试门禁覆盖这些合同，冻结前需刷新三套 runtime。
- 2026-10-08 交付目录修复：首次只复制 `PCIDE.exe` 导致 `_internal/python312.dll` 缺失；已将完整 `_internal` 运行时复制到 `outputs`，从该目录直接执行 smoke/UI smoke 均退出 0。
- 2026-10-08 易语言布局与代码补全收口：`main.py` 将中央区域分为“界面设计/代码工作区”，左侧增加子程序导航，右侧加入支持库/属性停靠页，环境菜单保存项目运行时路径；`editor.py`/`editor.html` 接入项目变量、常量、API、控件和事件的 Monaco 补全、签名提示、代码片段、Ctrl+Space、折叠和格式化入口。冻结版 EXE 已重建，交付目录保留 `PCIDE.exe` 与 `_internal`。
- 2026-10-08 易语言布局复核收口：左侧分组夹固定为支持库、属性/窗口设置、变量常量；项目与子程序导航置于其下；中间分为界面设计和代码工作区；右侧独立控件箱；底部固定输出/调试面板；代码工作区标签位于下方并支持关闭与右键关闭；分组框/标签页控件具有可编辑属性并在设计器、运行时绘制。40 项测试、冻结版 smoke/UI smoke 及 outputs 目录 EXE-only smoke/UI smoke 均通过。
- 2026-10-08 代码编辑区颜色修复：`ui/editor.html` 的 Monaco 主题颜色全部改为带 `#` 的合法十六进制值，并显式固定编辑区、边距、当前行、行号和滚动条配色；此前无效颜色值被 Monaco 回退为纯红色。源代码截图、冻结版 smoke/UI smoke、40 项测试和 outputs EXE-only smoke/UI smoke 均通过。
- 2026-10-08 易语言布局与控件属性最终收口：新增 `core/control_catalog.py` 统一 27 类控件的分组、默认值、选择项、数值范围和表单校验；`designer.py` 控件箱按基本组件/数据与视图/容器与布局/高级控件分类并支持拖放；`properties.py` 根据实际选中控件显示对应属性，焦点离开、回车和下拉改变立即回写；`form_runtime.py` 同步应用尺寸、文本、颜色、字体、列表、方向、分组页、表格和高级控件属性；项目树/支持库/属性分组夹保持易语言式布局。40 项测试、运行时三 profile、IDE 冻结版 smoke/UI smoke 和 outputs 交付目录验证通过。
- 2026-10-08 最终回归：新增分类控件箱与属性即时回写 UI 用例；`run_tests.ps1 -q` 41 项通过（90.636 秒）。
- 2026-10-08 交付目录最终复核：`outputs\\PCIDE.exe` 的 smoke/UI smoke 均返回 exit 0，`_internal` 与 EXE 同级。
