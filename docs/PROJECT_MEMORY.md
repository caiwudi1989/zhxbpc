# Project Memory

## 2026-10-11 最新交付：子程序正文输入与 Ctrl 快捷键修复

- 用户运行窗口出现 `Cannot edit in read-only editor`。此前收缩逻辑把整个源码编辑器设为只读，旧门禁还把“不能输入”当成收缩要求；这是回归，启动/截图通过没有覆盖用户逐个展开并输入的实际操作。本轮解除 Monaco/native 的全局只读，收缩只控制可见范围；全收缩后输入先展开当前子程序，点击正文同步 Qt 与 Monaco 焦点，进入代码页恢复焦点。
- `editor.html` 修正正文 Ctrl+Z/Y：Monaco 的隐藏 textarea 不再误走 HTML 输入框撤销。`editor.py`/`native_edit.py` 补 native 查找/替换对话框、跨子程序定位、当前/全部替换及 Esc 返回正文；输入框与正文按实际焦点处理。新增 `ui/input_probe.py`，仅允许 cache 工程副本，逐个鼠标点入子程序后用真实 Qt 键盘和输入法提交事件写入，检查所属子程序、九组 Ctrl 操作、磁盘保存与重开。
- 最终源码回归：正常 Windows Monaco 7项全部通过（15.156秒）；native offscreen 7项为6通过/1仅 Monaco 几何用例跳过（4.684秒），进程 exit0。默认 HelloAutomation 副本的源码门禁与 staging/原路径冻结门禁均 exit0，四个子程序分别验证字母/数字、换行、中文提交、readOnly:false；Ctrl+A/C/X/V/Z/Y/S/F/H 验证实际复制/剪切/粘贴、撤销/重做、保存、查找定位和全部替换。
- 完整目录已提升到 `build/PCIDE/PCIDE.exe` + 同级 `_internal`，工作区 `..\..`；SHA-256 `43f8dd535c8c0865da193c41691f77f554a907ffdcb977017f99bd98c063934b`。旧版 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33` 保留在 `build/editor-input-previous-20261011`。staging/原路径均审计入口、74编译模块、483资源和三套 Runtime 实际代码/指纹一致；本轮没有修改 Runtime 指纹成员，无需重建 Runtime。两路径另实际启动 C++、中文窗口和 Python 工程 Monaco UI，均 exit0；用户工程全部文件摘要未改变。
- 证据为 `cache/logs/editor-input-{source,staging,primary}-ui-20261011.json`、`editor-input-{staging,primary}-artifact-20261011.json`、`editor-input-promotion-20261011.json` 和对应 PNG/TXT。桌面 Computer Use 因用户 Esc 停止后没有再调用；最终输入证据来自开发/冻结程序中的 Qt 鼠标、键盘和中文 commit 事件，未宣称实测 Windows 输入法候选窗口。未重跑历史全量、客户 EXE、设备/Android/生产视觉或干净机器；未创建子代理、未修改 D盘、未提交/推送。

## 2026-10-11 备份触发规则

- 已将“备份”定义为双远程源码备份：执行 `tools/backup_source.ps1`，提交当前源码到 `main`，创建或更新 `backup/YYYY-MM-DD`，并把两个分支推送到 GitHub `origin` 与 Gitee `gitee`。
- “备份”默认不接受仅本地提交或仅单平台推送；只有两个远程均成功后才清理 `cache/backup/` 和 `cache/backups/`。详细规则写入 `AGENTS.md` 与 `docs/backup-policy.md`。
- 用户无需再次提醒推送；备份流程必须主动重试双远程推送，成功后再报告完成，不能把本地提交当作备份完成。
- 每个远程推送最多自动重试 10 次；10 次全部失败才报告外部网络阻断并保留备份缓存。
- 每次备份同时生成并上传 `backup-archives/source-YYYY-MM-DD.zip` 日期源码压缩包，仅含源码、文档、测试、示例和项目配置。

## 2026-10-10 此前交付：页面继续复核与遗漏补齐

- 延续上一轮页面审查，按用户要求继续检查应加入的内容、重复入口和错放项目；主页面增加“当前操作提示”，共 14 页。完整清单、入口、合并/删减及实际边界见 `docs/规范/pages.md`，随 EXE 分发；下方记录保留此前各轮的真实范围。
- `main.py` 增加底部“提示 / 输出”、Ctrl+Alt+H 和页面/支持库命令/片段/控件选择的实际说明；输出可清空与导出，中央和底部仍共享一份有界日志。调用表与断点支持双击/回车恢复源码页，调用位置校验当前工程路径与行号。非窗口工程禁用设计动作和快捷键。
- 新 `core/menus.py` / `ui/menu_dialog.py` 提供真实窗口菜单树、同级/下级/分隔线、移动/删除、快捷键、状态/勾选与处理子程序；可创建或进入真实事件源码。菜单最多 256 项、8 层，拒绝重复标识/快捷键和非法字段/类型。`control_catalog.py` 校验定义，`form_runtime.py` 创建实际嵌套 QMenu/QAction、分发 menu_id/text/checked 并支持运行时更新；单项处理器优先，避免普通单击重复派发。菜单栏属性只保留专用层级编辑入口，旧顶层 items 仍兼容。
- `designer.py` 补完整对齐、等宽/高/大、等间距、容器居中及顶层/底层；右键共用主菜单动作，复制/粘贴/全选限定画布。子控件使用真实父级 QGraphicsItem 与相对坐标，复制容器保持后代位置，删除父容器保留孩子时画布位置不变。`main.py` 预览使用未保存的设计，单纯预览不分发脚本事件，F5/F4 正式运行才执行；修复删除后旧选中 ID 的 Qt 槽异常。
- 验证：较广 native 57 项为 56通过/1符号链接环境跳过（26.611秒）；后续修复旧选择异常后，功能/窗口回归 native 15 项全通过（10.033秒）、正常 Windows Monaco 同组15项全通过（19.496秒）。截图又发现排列子菜单对象被提前释放，改为显式 QMenu 父对象；修正后排列定向1项通过（1.497秒），5份最终 Monaco 实际截图全部完成并目视检查。没有把修正前的整组结果称为修正后全量。
- 三套 Runtime 已通过 `tools/freeze_runtime.py --profile all` 重建，新菜单模块纳入运行时源码身份。冻结 IDE 独立构建后，staging/原路径审计均 `ok:true`：入口、73编译模块、483资源、三套 Runtime 的指纹、实际编译代码、启动器与EXE一致。两个路径分别实际启动 C++、中文窗口、Python脚本与菜单窗口4种工程的 Monaco UI及脚本 smoke，均 exit0；14页适用性/可见性、提示、共享输出、帮助资源、原文和源码不变通过。
- 已提升完整目录到 `build/PCIDE/PCIDE.exe` + 同级 `_internal`，配置工作区 `..\..`。最终 SHA-256 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33`；原版本 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809` 保留在 `build/pages-followup-previous-20261010`。证据 `cache/logs/pages-followup-{promotion,staging-artifact,staging-ui,primary-artifact,primary-ui}-20261010.json`、`pages-followup-captures-20261010/capture.json`。
- 本轮没有声称 EC/FNE ABI、时钟定时事件、WebView浏览器、调试变量写入/实时断点、非HTTP transport 等既有未实现能力已完成；未重跑历史全量、独立客户发布、硬件/Android/外部引擎实机、生产OCR/YOLO或干净机器部署。未创建子代理，未修改D盘，未提交/推送。

## 2026-10-10 此前交付：页面内容逐项补齐与合并

- 按用户要求继续核对 13 个主页面/目录和配套设计、配置对话框；页面清单、加入/合并/删除记录和能力边界见 `docs/规范/pages.md`，参考易语言官方操作手册的工作夹、状态夹与窗口/程序编辑组织方式，未宣称全部易语言功能或二进制兼容。
- `main.py` 增加“视图”恢复入口并按工程模式隐藏/禁用不适用页面；代码关闭后文件/子程序/调用表/断点导航恢复。程序夹的入口和其他源码文件共用 `ui/routine_ranges.py` 扫描，补齐 Python async 和 JS/TS export/async 函数，排除注释/字符串；入口子程序只保留一份列表并正确返回入口文件，启动处理器别名保留。新建源码移到项目菜单，移除平台菜单重复 Unity 入口；中央/底部输出共享一份日志。
- 新 `ui/resource_panel.py` 提供真实资源列表、搜索、大小/类型、文本/图像预览、导入、复制相对路径、重命名/删除；二进制不进入源码编辑器。调试页补状态、断点列表/清除/导航，文件切换重载断点；变量和调用表保持只读快照。原生断点 ExtraSelection 的实际报错已修复。
- 属性页补独立组件选择器、中文事件候选、即时回写、日期时间值和真实窗口宽高保存；控件事件按运行时连接提供。流程页补编号/名称/参数编辑、明确方向、箭头、连线删除与编号引用同步。视觉页补实际标注表/逐条删除/无图片提示，并收紧工具栏留白。
- 数据库/API 对话框补结构化编辑、JSON 同步、生成预览、完整验证、用户源码保护和多文件写入失败回滚；按语言生成可执行元数据/客户端，原生语言仅保存定义。API 引号路径安全生成、函数名冲突拒绝、HTTP 方法校验、JS/TS 超时取消和单次共享导入已实测；Python/中文网络超时上限 60 秒，响应类型暂为声明，非 HTTP transport 尚需提供者。
- 新 `ui/configuration_dialogs.py` 将运行器不读取的项目环境字段改为真实执行入口和运行限制；平台能力显示八项配置、合同及工程登记/文件发现的只读提供者声明。欢迎、编译、示例、模块、参数、支持库加入/配置/帮助、系统工具、AI、DEX/Android 入口均已核对；表格列宽、项目名、AI 关闭按钮等一并整理。
- 验证：较广 native 回归 88 项为 83 通过/5 条件跳过（38.876 秒）；最终页面/生成/合同 native 38 项为 37 通过/1 符号链接环境跳过（13.027 秒）；Monaco 定向 30 项全部通过（40.635 秒）；最终 API 5 项全部通过。异步/导出导航、真实行号、去重和现有收缩范围的 native 定向 4 项通过（3.279 秒）。Node 实际执行 JS/转译 TS 并取消超时请求，SQLite 内存执行生成 CRUD，多文件故障注入证明回滚。30 份真实页面截图已检查，最终 API 预览已刷新；截图检查不代替生产视觉、硬件或外部服务验收。
- 最终完整目录为 `build/PCIDE/PCIDE.exe` + 同级 `_internal`；EXE SHA-256 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809`，工作区 `..\..`。原版本 `5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90` 保留在 `build/pages-review-previous-20261010`；导航修复前的版本保留在 `build/pages-review-before-navigation-20261010`。staging/原路径均实际审计入口、71 编译模块、483 资源和三套既有 Runtime 一致；本轮未修改 Runtime 指纹清单内源码，未重建 Runtime。两路径 C++/中文窗口/Python 脚本 Monaco 与脚本 smoke 均实际退出 0，适用页面/共享输出/帮助文档正确，工程入口源码摘要未变。证据 `pages-review-{staging,primary}-{artifact,ui}-20261010.json`、`pages-review-promotion-20261010.json`。
- EC/FNE ABI、时钟定时事件、WebView 浏览器交互、调试变量写入/运行中断点更新等既有边界在页内或帮助明确标注。本轮未重跑历史全量、客户 EXE 发布、生产 OCR/YOLO、硬件、Android/引擎实机或干净机器部署，未提交或推送修改。

## 2026-10-10 上轮交付：支持库目录与非脚本源码显示修复

- 用户截图打开的是 `Example_native_factory` C++ 工厂模式工程。此前把线程/资源管理/Win32 的六个代码片段放进“支持库”，且 Monaco 把 C++ `const/return` 投影为中文；两项均为实现错误。本轮以易语言官方支持库分类和帮助交互为参考，修正 PCIDE 自己的目录，未宣称易语言二进制兼容。
- `core/libraries.py` 提供实际可插入、可运行的核心命令分类、库定义类型和常量；`main.py` 按类别展示，选择条目即显示说明、调用格式、返回值和当前语言代码。窗口类型包含窗口与实际 27 类控件，可展开属性/事件/方法，属性使用真实默认值和选择项；时钟/WebView 的现有实现限制明确列出。C/C++/.NET/Unity/Godot/网页示例移入独立“代码片段”页，保留双击、拖放和帮助。
- `ui/editor.html` 的关键字投影只应用于 Python；C/C++/C#/HTML 等源码原样显示、捕获和保存。中文子程序视图按钮按当前文件语言启用，C++ 禁用；`.zhxb` 保留自己的原文语法，JS/TS 保留真实关键字。
- 定向门禁均 exit 0：支持库核心 11 项（7.209 秒）、native 开发/支持库/编辑器 18 项（9.065 秒）、正常 Windows Monaco 4 项（5.891 秒）、编辑器静态合同 2 项（1.164 秒）。核心用例实际执行计算、文件、SQLite、有界任务池和窗口代理，并编译所有可插入的中文目录示例。日志为 `cache/logs/support-catalog-{core,native,monaco,editor-contract}-20261010.txt`。
- 用户保存并关闭旧窗口后，已提升完整目录到 `build/PCIDE`，工作区配置为 `..\..`；原 EXE SHA-256 `ba2e0c2e9979800da554f115b3eee32c5ea76662858a81d1643b0569bfe4ee94` 保留在 `build/support-catalog-previous-20261010`。当前 EXE SHA-256 为 `5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90`，完整 `_internal` 同级；提升证据为 `support-catalog-promotion-20261010.json`。
- 原路径审计 `support-catalog-primary-artifact-20261010.json` 为 `ok:true`：入口、69 个编译模块、482 项资源和三套现有 Runtime 一致。本轮未修改 Runtime 清单内的核心代码，未重建 Runtime。原路径 C++ 与中文工程 Monaco UI smoke 均实际退出 0，`frozen/monaco/editor_ready:true`，C++ `native_source_display_matches:true`，两份工程源码摘要保持不变；报告、截图见 `support-catalog-primary-{cpp,zhxb}-monaco-20261010.*`，汇总见 `support-catalog-primary-ui-20261010.json`。
- EC/FNE 仍只能登记，官方编译/专用 ABI 桥接尚未实现。本轮未重跑此前全量、硬件、Android、生产视觉、独立客户 EXE 或另一台干净 Windows 验收；下方记录属于此前交付。使用说明与来源见 `docs/规范/libraries.md`，详细命令见 verification 最新节。

- 2026-10-10 迭代编译补强：编译设置对话框现在会持久化目标、配置和并行上限到 `.pcide/project.json`；C/C++ 原生缓存按每个源文件的传递本地 `#include` 依赖计算，无关头文件不会触发全量重编；CMake 复用配置缓存，.NET 已有离线 assets 时使用 `--no-restore`。相关实现为 `main.py`、`core/build_service.py`，并有原生无关头文件增量回归。

- Current development expansion: IDE 0.2.0 adds 19 explicit templates for scripts/forms, C/C++/Win32/CMake, C#/WinForms, browser apps and Unity/Godot. Shared factories own selection/build contracts; system environment and native static CRT are distinct from bundled script EXEs. 100 offline example projects are searchable and loaded as copies. Existing engines/SDKs are configured, never downloaded by these entry points.

- 2026-10-10 通用软件与游戏开发最终交付：`build/PCIDE/PCIDE.exe` 已由独立 staging 原子提升，当前 SHA-256 为 `ba2e0c2e9979800da554f115b3eee32c5ea76662858a81d1643b0569bfe4ee94`；本轮迭代审计为 `cache/logs/development-iteration-artifact-20261010.json`，最终发布门禁为 `cache/logs/frozen-release.json`，旧交付保留在 `build/development-previous-iteration-20261010`。欢迎页可选脚本、窗口、原生、C#、网页、Unity/Godot 类型与发布目标；Ctrl+B 提供增量/重新构建/静态 CRT/系统环境/CMake/.NET AOT/引擎导出入口。工作区工具路径可保存到 `runtime/toolchains.json`，项目路径优先，入口不下载环境。
- Unity/Godot 已有工程通过“游戏引擎 → 接入已有 Unity/Godot 工程”或“平台 → 接入 Unity 工程”创建绑定引用工程；F5、编辑器、Windows 构建、停止均由统一外部进程会话管理，外部资产不被导入流程覆盖。Unity 模板显示对象/协程/场景/资源 API，Job worker 数量跟随 1..4 并行设置。
- 原生/C# 控制台 F5 支持实时有界输出和底部输入栏；单次输入最多4096字符、队列最多16条，写入堵塞/超时回收进程，退出后输入自动禁用。编译期间检测输入增删和旧产物回滚；C/C++ 混合源、头文件缓存与静态 CRT 已实测。
- 系统环境 JavaScript/TypeScript 发布在构建阶段完成 TS 转换、程序数据、公开模块调用和局部初始化，交付不携带 TypeScript SDK；四语言系统环境交付均无解释器/Qt DLL/SDK 复制。冻结 IDE 显式收集常用 Python 标准库以覆盖动态导入，并将清单计入 Runtime 身份。
- 最终证据：`run_tests.ps1 -q` 为 139 项通过、4 项环境跳过；开发定向 UI 为49项通过/1项跳过；100例冻结验证 `ok:true`；四语言独立 EXE/系统环境交付 `cache/logs/development-delivery-20261010.json` 为 `ok:true`；PYZ/入口/69个核心模块/481项资源和三套 Runtime 审计 `cache/logs/development-promoted-artifact-20261010.json` 为 `ok:true`；最终 `cache/logs/frozen-release.json` 为 `ok:true`。Unity/Godot/CMake真实环境未配置，验证只覆盖工程与命令合同；Android、硬件、GPU、签名和另一台干净 Windows 仍需实机验收。

- Date: 2026-10-10. Root: `F:\PC端软件`. The delivered target is a generic Windows Qt IDE with offline Monaco, Python/中文源码/JavaScript/TypeScript execution and debugging, form/flow design, isolated extensions, vision adapters, DEX transport, and incremental standalone EXE packaging.
- Entry chain: `start_ide.ps1` / `start_ide.cmd` -> `src/pcide/main.py` -> `Paths` + `Project` -> Qt `MainWindow`. Frozen IDE: `build/PCIDE/PCIDE.exe`.
- Runtime chain: `src/pcide/core/runner.py` -> prebuilt console runtime -> Python `worker.py` or Node worker. Windows command input uses bounded `PeekNamedPipe` polling; one-shot runs do not create a blocking stdin thread, keep-alive/debug readers start only after safe initialization or at a debugger pause.
- Build chain: `core/builder.py` hashes project inputs and runtime profile, emits Python `.pyc` or Bytenode `.jsc`, assembles a fixed PyInstaller runtime, scans `payload`, and preserves old artifacts on failure. Profiles are `runtime/prebuilt/project-runtime*`.
- Extension/vision chain: `core/plugins.py` -> child hosts under `runtime/modules`; `core/vision.py` -> RapidOCR/ONNX/OpenCV. The self-contained .NET host path is propagated through `PCIDE_DOTNET_HOST` for frozen IDE child processes.
- Current source/UI evidence: Library admission/configuration/help, categorized data tables, source-backed parameters separate from locals, and scoped shortcuts are now delivered. Core gate: 40 cases, 39 passed and 1 environment skip; Monaco UI: 39 cases, 38 passed and 1 native-only skip. Native UI: 38 cases, 34 passed and 4 Monaco-only skips, plus 2 targeted DLL-table/signature cases passed. Three rebuilt Runtime profiles and their actual embedded core code match source; four language customer EXEs run with no development Python and empty PYTHONPATH. Primary script/native/auto/Monaco smoke and artifact audit pass after promotion to `build/PCIDE`. Evidence: `libraries-parameters-artifact-20261010.json`, `library-customers-20261010.json`; earlier full/vision/hardware gates are separate.
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
- 2026-10-08 平台化二开第一步：新增 `core/platform.py`，为数据库、API、脚本、AI、游戏、编译器、Runtime、Agent 提供版本化能力清单和 provider 合同；`Project` 自动规范化并持久化 `manifest.platform`，拒绝未知能力、重复 provider ID 和非法配置。依据 Qt 官方插件机制与 Python packaging entry points 的可扩展设计原则，未将 SDK 或第三方运行时嵌入 IDE 进程。
- 2026-10-08 平台化收口：新增 `core/product.py` 产品子系统目录、合同版本、阶段和能力解析，统一输出八大子系统的启用状态、provider 与摘要；新增 provider manifest 只读发现和工程 `platform_providers()` 查询，第三方代码不会在 IDE 进程内执行。
- 2026-10-08 AI Agent 架构增强：只读审阅 `D:\zhxbapp\pc_ide` 的 `agent_backend.py`、`openhands_backend.py`、`ai_capability_mcp.py`、`ai_project_tools.py` 与 AI 助手测试，提取通用设计并实现 `core/agent.py`。当前 Agent 具备会话状态机、事件时间线、可取消任务、计划步骤上限、工具合同、用户确认门、工作区路径边界、修改前 read、Python/JSON 语法门禁和变更记录；未复制 D 盘业务代码，也未修改 D 盘。
- 2026-10-08 AI 助手接入：新增 `core/agent_client.py` OpenAI-compatible/DeepSeek tool-calls 客户端，新增 `core/agent_tools.py` 项目列表、搜索、读取、写入、唯一替换和验证工具；主界面加入“AI → AI 编程助手”对话窗口，API Key 仅保存在本次会话，写入需要明确勾选并限制到批准路径。
- 2026-10-08 AI 助手执行链收口：Agent 支持多轮 tool-calls、模型响应事件、待确认写入状态和取消；工具 JSON schema、项目文本索引/搜索、读取前置、唯一替换、Python/JSON 校验和验证回调已统一，新增真实 fake-model smoke 验证连续读取工具调用。
- 2026-10-08 AI 助手界面收口：主工具栏和 AI 菜单均可打开项目级助手；支持兼容 OpenAI/DeepSeek API、模型、当前会话 Key、批准写入路径、写入开关、任务输出和取消；助手验证动作复用现有 bounded ScriptRunner。
- 2026-10-08 产品域收口：新增 `compiler.py` 中文源码 Lexer/Parser/IR/Python emitter；`database.py` schema/SQLite/CRUD；`api_center.py` HTTP API 合同与代码生成；`ai_runtime.py` 模型和推理会话合同；`game_sdk.py` 场景/摄像机/实体合同；`agent_roles.py` 六类 IDE Agent 角色；`plugin_market.py` 离线插件目录与 SHA-256 包校验。新项目自动创建 database/api/models/game/providers 目录，构建输入包含这些扩展域。
- 2026-10-08 Unity 游戏后端接入：新增 `core/unity.py`，支持只读识别 Unity 工程、读取 Unity 版本、场景摘要、生成 `MonoBehaviour` C# 桥脚本、写入明确的 `Assets/ZhxbPc/Generated` 目录和 bridge manifest；Game SDK 默认 provider 改为 Unity，保留 OpenGL/DirectX/Vulkan 等扩展后端。Unity 编辑器和构建器仍作为外部工具，不进入 IDE 进程。
- 2026-10-08 中文源码链路接入：项目语言新增 `zhxb`，新建项目生成 `.zhxb` 源码；运行时经中文编译器生成 Python 执行码，构建器生成 `.pyc` 并按 Python Runtime 打包，入口、脚本索引和新建源码入口均已覆盖。
- 2026-10-08 全域复核修复：中文编译器要求 `.版本 2`、使用稳定 SHA-256 函数名并支持 `输出/信息框`；数据库 schema 增加字段/索引/默认值严格校验；API 代码生成改用 `runtime_api.network`；插件包安装增加 Zip 越界、文件数和体积门禁；AI Runtime 增加现有 OCR/ONNX `VisionProvider`；Runtime API 新增有界 SQLite、HTTP 和 Game 事件代理；IDE 新增数据库设计器和 API 中心入口。
- 2026-10-08 Qt WebEngine 弹窗修复：受限 Windows token 创建 Chromium Mojo 命名管道会触发 `FATAL:named-platform-channel-pipe`/拒绝访问弹窗；`ui/editor.py` 现在在 Codex/禁用 WebEngine 环境自动使用原生 `QPlainTextEdit`，普通桌面仍可使用 Monaco，并支持 `--editor auto|native|monaco`。原生回退保留加载、保存、跳转、插入、快照和变更同步，避免 IDE 崩溃或弹窗。
- 2026-10-09 最终收口：原生编辑器补齐语法高亮、补全、撤销/重做、查找替换、格式化、断点与稳定跳转；项目/代码菜单补齐另存、导入、重命名、关闭、删除、查找替换、跳转和插件安装/卸载入口；项目复制拒绝符号链接、路径越界、超量文件和超大导入；插件市场增加升级失败回滚。运行时 `ui.set` 与事件消息通过 Qt 事件队列串行化，避免 UI 更新竞争。
- 2026-10-09 最终验证：`run_tests.ps1 -q` 为 56 项通过、1 项按环境跳过（97.211 秒，最终证据 `cache/logs/full-tests-20261009-final.txt`）；三套 Runtime 指纹一致，Node profile 在 60.093 秒内刷新；`freeze_ide.py` 以 62.047 秒生成 `build/PCIDE/PCIDE.exe`；冻结版脚本 smoke、原生 UI smoke 和默认 UI smoke 均 exit 0，默认后端在当前受限 token 自动选择 native。`verify_release.py` exit 0（72.685 秒），覆盖 Python/JavaScript/TypeScript、真实 OCR/ONNX、Python/C/.NET 插件、客户 EXE-only 目录及 worker 超时/取消/断开/崩溃回收。
- 2026-10-09 构建优化：独立 EXE 归档仅压缩小型文本/字节码，DLL/模型/媒体等高密度二进制直接流式写入，并将打包格式纳入指纹；隔离 HelloAutomation 测得首次 2.398 秒、增量 2.226 秒、无变化 1.114 秒。示例交付 `cache/logs/delivery.json` 中 Python/JS/TS 首次分别 3.231/1.689/1.587 秒，缓存分别 1.133/1.390/1.393 秒。
- 2026-10-09 Monaco 空白修复：`ui/editor.html` 的 Python 中文视图正则使用了 Unicode 模式下非法的 `\#` identity escape，导致 Chromium 在脚本解析阶段报 `Invalid regular expression`，代码模型未创建而显示空白。已改为合法的 `/#.../u`，新增静态回归测试并重建 `build/PCIDE/PCIDE.exe`；Node 内联脚本语法检查、源码/冻结版 smoke 和原生 UI smoke 均通过。
- 2026-10-09 子程序信息区重叠修复：Monaco view zone 原先使用零基 `index` 作为一基 `afterLineNumber`，把参数/返回值表插到了声明行上方；现改为 `index+1` 并扩大高度预算，避免表格与声明及函数体重叠。新增静态回归测试，源码内联脚本语法检查和冻结版 smoke/UI smoke 通过。
- 2026-10-09 子程序信息区交互收口：每个 Monaco 子程序信息区增加易语言式 `−/＋` 收缩按钮，折叠时保留子程序标题，展开时恢复返回值/参数表；按 Windows 字体实际布局测量并校正 view zone 高度，防止高 DPI 字体把表格挤出信息区。新增真实 Chromium UI 回归覆盖显示、尺寸和收缩/展开。
- 2026-10-09 子程序元数据收口：收缩按钮固定在信息区左侧，源码行隐藏 Monaco 默认折叠三角；子程序名称、返回值、备注可直接编辑；公开列双击显示红色 `✔` 并写入 `.pcide/routines.json`，其他源文件的补全索引可调用公开子程序。
- 2026-10-09 源码视图隐藏收口：Monaco 仅通过 `setHiddenAreas()` 隐藏导入行、`def/function/子程序` 声明行（含 `.子程序` 中文源码格式），不修改模型中的真实源码；中文源码 `.zhxb` 不再误套 Python/JavaScript 关键字投影，保存、运行和编译仍使用原文。
- 2026-10-10 启动子程序语义收口：窗口加载事件唯一对应易语言式 `_启动程序` 显示标题，按钮和其他子程序保持各自名称；启动标题与局部变量表可编辑并写入 `.pcide/routines.json`，返回值使用完整中文类型下拉框，公开使用复选框，视图区为标题行/设置行/局部变量表保留源码行号。

- 2026-10-09：新增 	ools/backup_source.ps1 与 docs/backup-policy.md，规定只备份源码/文档/测试/示例/配置，排除缓存、构建产物和运行环境；每次同步 main 与 ackup/YYYY-MM-DD 到 GitHub/Gitee。

- 2026-10-09：备份规则补充：GitHub/Gitee 双端推送成功后，仅删除 cache/backup/ 和 cache/backups/ 中的本地备份包与备份缓存；失败或本地演练不清理。

- 2026-10-10：固定“聊天框说备份”流程：提交源码后覆盖推送 GitHub/Gitee 的 `main`，覆盖推送 `backup/YYYY-MM-DD`，两端全部成功后才清理 `cache/backup/` 与 `cache/backups/`；任一失败保留缓存现场。

## 2026-10-10 中文 IDE 开发收口

- 已移除推断 ABI、固定长度文本指针读取和裸指针返回的临时 DLL 桥。`dll.py → PluginSession → plugin_host → dll_host` 仅在独立宿主加载客户 DLL，声明参数宽度/编码、检查 PE 位数、限制数量和每调用超时；实际 DLL 标量、超时、崩溃、卸载、恢复测试通过。
- `routines.py` 按文件/sourceName/id 对齐元数据；普通改名同步项目调用及窗口事件，保留字符串和注释，存在同名声明时拒绝歧义改名。主窗口 load 默认显示可编辑 `_启动程序`，修改显示标题保留实际 handler；次级窗口 load 保留自己的名称。
- 原生 `routine_panel.py/native_edit.py` 提供可编辑子程序表和所选代码体；Monaco 元数据表、公开勾选、备注、局部增删、收缩展开、切文件保存和 TypeScript 诊断通过真实 WebEngine 回归。隐藏声明/导入不删除真实源码；原生断点按源码 block 编号定位，JS/TS 保持原始关键字供语言服务诊断。
- `source.py/project_sources.py/source_contract.cjs` 共用源运行与字节码构建合同；四语言公开函数跨文件调用、元数据局部初始化和程序数据实际执行。Python/中文源码支持共享全局/常量保护、类型初始化、静态局部及声明参数/返回校验。中文真/假/空按 token 转换，事件参数独立为 keyword-only，控制流和原语句行号已有回归。
- 数据表保存绑定当前 Project，项目切换不再写入旧项目；改名/复制/删除/非法值回滚/作用域和左侧导航同步。自定义类型成员/API 参数使用实际编辑对话框。27 类控件使用专属绘制图标，分类菜单实际添加、图标/文字模式与拖放保留。
- `modules.py/module_dialog.py` 提供 `.pcide/modules.json` 精确版本、src 相对路径、公开接口、依赖与循环校验，Python/中文源码真实限定调用；更新在下次创建 worker 时加载。运行中热替换和 Node 版本模块表未开放。
- 构建输入包含 data/routines/modules；字节码身份包含 Runtime/编译器/Node 转换器指纹。四语言冻结用例验证改元数据后缓存失效。基础设施冻结/Node 编译使用有限日志、超时、取消和 Job 清理；协议写入堵塞会终止宿主，kill 后 wait 有限。
- 四语言普通客户项目 first/incremental/unchanged 秒数：Python `1.797/1.391/1.015`；中文 `1.500/1.766/1.015`；JavaScript `3.281/3.344/1.422`；TypeScript `2.672/2.359/1.406`。四个真正单文件 EXE 均在缺失开发 Python 的环境下退出 0，并输出跨文件公开函数结果 `9`。该小项目测量满足本轮 10 秒目标，不承诺所有项目或 IDE/Runtime 全冻结 10 秒。
- 最终交付为 `build/PCIDE/PCIDE.exe` 与完整同级 `build/PCIDE/_internal`；当前源码、原生冻结、默认受限回退、正常桌面 Monaco UI smoke 均退出 0，截图已检查。未提交、备份或推送本轮修改；未访问或修改 `D:\zhxbapp`，未声称完成 D 盘独立完整性审计。
- 最后发布门禁 `tools/verify_release.py` exit 0，`76.202` 秒，证据 `verify-release-20261010-bounded-final.txt` / `frozen-release.json`（`ok:true`、隔离工作区已删除）；真实 OCR/CPU ONNX、Python/C/.NET 插件和六类 worker 生命周期全部通过。发布工具修正中文 `.pyc` 识别并使用有界子进程日志；四语言最终载荷审计 `closeout-final-audit-20261010.json` 为 `ok:true`。`closeout-process-inventory-20261010.json` 为 `[]`；五处源码/测试 `__pycache__` 与两处调试缓存已确认路径后清理，证据 `closeout-cleanup-20261010.json`。
- 当前能力边界集中记录在 `docs/规范/routine-runtime.md`：中文语法子集、Node 静态局部/DLL、跨位数及指针/文本返回/结构体/输出参数尚未开放；普通语言继承遵循其运行时。子进程隔离/公开表不是恶意代码 OS 沙箱；Android 真机、串口/HID 硬件、GPU、签名和另一台干净 Windows 仍未验收。

## 2026-10-10 用户截图后的代码编辑区修正

- 用户指出旧代码区仍未做好；旧实现把名称显示两次、设置/参数/局部表宽度不同，且 view zone 使用大幅固定预留高度，只增不减。现在名称仅显示在可编辑声明行，三角在名称左侧，源码声明号通过 Monaco marginDomNode 放在真实左侧 gutter；各表统一全宽，空局部变量只留一条添加入口。
- ResizeObserver 按实际 frame 高度增减 view zone；添加/删除局部、收缩/展开和窗口宽度变化均重新测量。原生表采用最大内容高度策略，空局部表隐藏，消除固定空表和伸展留白。
- 临时元数据支持绝对/相对文件匹配，发布时清理同一文件/源码名称的旧记录；折叠、插入源码行、切文件都保留刚编辑的名称/备注/局部。输入区域保留原生 DOM 焦点；新测试使用真实 Qt 鼠标/键盘事件，而非仅 JavaScript 改 value。
- 两后端整组 UI 回归通过；冻结脚本/native/受限 auto/正常 Monaco smoke 通过，实际截图已检查。`editor-layout-code-area-20261010.png` 是源码编辑控件直接截图；其 HTML 和最终冻结 HTML 的 SHA-256 完全一致，见 `editor-layout-artifact-20261010.json`。
- 原路径首次冻结因用户旧 IDE 占用 DLL 而失败；已补回当次清理掉的 116 个缺失资产，独立打包验证后，在用户明确保存关闭旧窗口后替换原目录。`freeze_ide.py` 增加 build 内独立输出及运行 EXE 写权限前置检查，避免下一次先清理运行时再发现占用。
- 最终仍为 `build/PCIDE/PCIDE.exe` 和同级 `_internal`；EXE SHA-256 `f4d5e131dea32aa2dd4a2bad913077c61b1fc02b65a51473274fd247c428ae91`。本次只改编辑器 UI、测试与冻结工具，未改 Runtime 指纹输入；没有把此前全量/发布耗时冒充本次重跑。
- 新版原路径验证成功后，已清理本次临时旧交付快照和空 staging 目录；`editor-layout-cleanup-20261010.json` 记录源码旁字节码为空，`editor-layout-final-processes-20261010.json` 为 `[]`，最终 `editor-layout-diff-check-20261010.txt` exit 0。

## 2026-10-10 三项编辑器修复

- 收缩现在包含子程序代码体与设置区，展开完整恢复；名称行保留，后续子程序与顶层启动输出不被吞掉。Python 缩进/多行字符串、Node 注释/字符串/模板/正则中的括号和中文源码都已有实际视图检查。完整模型与保存内容保持不变；此前仅检查元数据 content.hidden 的证据不代表真实代码体折叠。
- 正文输入和换行复用现有表格，移动行只更新锚点；隐藏范围相同不重复设置，元数据刷新同一模型不抢焦点。实际 Qt 键盘文字/回车加 DOM MutationObserver 验证表格替换次数为 0。原生面板与文档可见性也仅更新改变部分。
- 控件双击、子程序导航改为首个代码位置；收缩中的目标先展开，普通调试跳转也展开目标。新建 Node 事件用多行代码体。编辑专用 `ui/routine_ranges.py` 不改变 Runtime 指纹输入。
- 两后端各 31 项 UI 回归通过；原交付路径冻结脚本、native、受限 auto、正常桌面 Monaco smoke 均通过。实际展开/收缩截图为 `editor-interaction-expanded-20261010.png` / `editor-interaction-collapsed-20261010.png`；源码截图与冻结 HTML SHA-256 相同。冻结模块及入口编译代码与源码核对，三套 Runtime 指纹保持一致。
- 最终 EXE 为 `build/PCIDE/PCIDE.exe`，SHA-256 `c3ed7af5dde3d19413e782962f5118df224f8e89bdabd4c41ce5079f716af6ec`，完整 `_internal` 同级。本轮没有重跑此前 84 项全量、客户 EXE 重建或生产视觉/硬件/干净机器门禁。
- 自动审批拒绝递归删除旧交付回退副本及探针缓存，已保留 `build/editor-interaction-previous-20261010`；新版已成功提升并验证，无须该清理即可使用。最终清单/保留状态及 diff-check 见 `editor-interaction-final-processes-20261010.json`、`editor-interaction-cleanup-20261010.json`、`editor-interaction-diff-check-20261010.txt`。

## 2026-10-10 收缩后残留启动代码修正

- 用户截图中所有子程序已经收缩，仍露出“脚本已就绪”和空白。本轮在中文视图中将当前文件的顶层初始化和分隔空白归给显式绑定的启动处理器，随其收缩/展开；没有启动处理器的普通文件仍保留独立顶层代码。没有移动或删除真实源码，没有改变执行语义。
- Monaco 拒绝隐藏全部模型行；全收缩时保留末行作为显示锚点，源码/光标/高亮不可见且正文只读，避免对隐藏源码误输入。展开恢复编辑；普通跳转到初始化行也会展开启动程序。原生选中启动程序时同时显示初始化，收缩时保护隐藏正文。不可见表格的零高度测量不再覆盖已有高度。
- 新增 Python/JS/TS 有末尾空行和无末尾空行的真实视图/键盘/保存检查；正文输入零表格替换、控件双击正文定位继续通过。两后端各32项UI回归通过。源码截图 `editor-startup-scope-collapsed-20261010.png` 仅剩四个连续名称行，`editor-startup-scope-capture-20261010.json` 的 `visible_code` 为空，源码与用户文件一致。
- 最终交付 `build/PCIDE/PCIDE.exe`，完整 `_internal` 同级；EXE SHA-256 `2c564f90b68ce6ecf082a4d915e0ff9206621779c21876ac55f2daf513ca5d81`，HTML SHA-256 `8fa0f807a597f5d35847810d0cedae0bf4d12a447ea6985bad156537552527cc`。保留 `build/editor-startup-scope-previous-20261010` 与此前回退副本。本轮未重跑此前全量Runtime/客户发布门禁。

## 2026-10-10 公开列单个勾选

- 用户要求公开列只显示一个勾选：Monaco去掉复选框旁的额外`✔`，保留红色复选框；原生去掉“公开 ✔”中的额外符号，保留普通“公开”标签和复选框。勾选及元数据保存合同不变。
- 复用现有Monaco公开字段用例与原生元数据保存用例，各1项通过；实际截图`editor-public-single-check-collapsed-20261010.png`已确认每行一个勾选。本轮为低影响显示修正，没有新增测试或重跑此前32项整组UI门禁。
- 独立冻结后提升`build/PCIDE`，保留`build/editor-public-single-check-previous-20261010`；EXE SHA-256 `7af7a78c96c613211aacfb78b413c146b8a384d9376f4a80ff06c3aaaee0df1e`，HTML SHA-256 `cff31d86f97691b23085f9f0e61f7557227a0c5ff381543d282aa973f283e158`。验证证据见verification最新节。

## 2026-10-10 支持库、数据表、参数与快捷键交付

- `core/libraries.py` 提供真实系统核心/窗口命令目录、独立库类型/常量、`.pcide/libraries.json` 校验和格式化调用示例；左侧支持库不再混入项目变量。加入、配置、搜索、使用帮助入口位于左侧和扩展菜单。参考易语言公开官方界面/模块文档、Microsoft .NET 插件和 Android DEX 文档，来源见 `docs/规范/libraries.md`，未复制外部实现。
- 四语言源码加入 src，语法检查后选择公开接口。Python/中文源码复用精确模块引用表；Node 使用实际 require 调用。普通 DLL 需明确导出/ABI/约定并由独立宿主执行；参数有实际编辑表。plugin.json/ZIP/pcplugin 复制入口和依赖，检查路径、摘要、依赖和权限；worker 中 `plugins.call` 返回真实结果，每调用 finally 关闭宿主。源码复制不覆盖，参考表写入失败恢复旧元数据；模块导入只追加新引用，保留引用表尚未保存的已有编辑。
- 数据表按类别显示相关列；添加项可填写规范中文类型、作用域、所属窗口/模块/子程序、数组维数、静态和备注；类型成员支持数组，删除中间行后组合框仍写入正确条目。左侧程序夹区分全局/窗口/程序集/局部变量、常量、类型和DLL命令；作用域补全使用 owner.id。
- `routine_signatures.py` / `parameter_dialog.py` 从真实签名读取参数并保存回源码，保留 Python 参数形式，中文声明参数与显式局部独立解析。中文编译器版本4：无默认值的参数必填，有第三列默认值才可省略；禁止必填位置参数在可省略参数之后。显式源码局部只读显示，源码视图编辑；元数据局部仍真实参与运行/构建。参数改名后仍需同步正文和调用处，未伪称自动修改引用。
- `Ctrl+Alt+P` 编辑参数，`Ctrl+Alt+V` 添加局部，`Ctrl+K` 收缩当前，`Ctrl+Alt+[`/`]` 全收缩/全展开，`Ctrl+/` 注释，`Ctrl+E` 切换设计/代码；`Ctrl+W` 关闭当前代码页，关闭项目改为 `Ctrl+Alt+W`。撤销按当前文本/代码/设计路由；设计复制/删除使用局部快捷键作用域。F1提供完整说明。
- 最终核心40项为39通过/1环境跳过（13.620秒）；Monaco39项为38通过/1原生专属跳过（65.208秒）；native38项为34通过/4Monaco专属跳过（15.918秒），随后DLL参数表/参数源码保存2项均通过（1.279秒）。三个Runtime已完整刷新；实际嵌入核心代码与源码一致，非仅核对manifest指纹。相关日志见verification最新节。
- 四语言最新冻结IDE构建和真正单文件客户EXE均实际输出42；Python还输出封装宿主标记LIBRARY_HOST_OK及DLL结果0。验证环境配置不存在的开发Python、空PYTHONPATH，客户载荷无项目源码/SDK；本机隔离测试不代表另一台干净机器验收。证据 `library-customers-20261010.json` 绑定最终IDE摘要。
- 最终交付 `build/PCIDE/PCIDE.exe` 和完整同级 `_internal`；EXE SHA-256 `7cbf56abba6212e282be8c5e3cb90919469e99eac3a9249bec11c34889bfea74`，HTML SHA-256 `e0a9617a8dc008f467adc6274d2ea3b77a79fceec6d1ea093d871534dae91223`。staging与原路径script/native/受限auto/正常桌面Monaco smoke及编译代码审计均成功；保留 `build/libraries-parameters-previous-20261010` 和此前回退副本，不删除历史探针缓存。
- EC/FNE可以登记保存但仍待官方编译/专用ABI桥接；DEX需先部署到Android并配置宿主，真机未验收；裸PYD/.NET程序集要求plugin.json包装。Node插件/DLL代理、Node静态局部/精确版本表、指针/结构体/输出参数/文本返回尚未开放。本轮未重跑此前全量、生产视觉、硬件或干净机器发布门禁；未提交、备份、推送或访问D盘。
